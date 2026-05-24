import frappe
from frappe.utils import now_datetime, add_to_date

from gps_gate.apis.maintenance import (
    generate_schedules_for_vehicle,
    evaluate_vehicle_maintenance,
)


NOTIFICATION_STATUSES = ["Due Soon", "Overdue"]
NOTIFICATION_ROLE = "Maintenance Manager"

# اگر نمی‌خوای هر ساعت برای یک schedule نوتیفیکیشن تکراری بره،
# این عدد مشخص می‌کنه حداقل چند ساعت فاصله بین notificationها باشد.
NOTIFICATION_REPEAT_AFTER_HOURS = 24


def hourly_vehicle_maintenance_job():
    """
    This job runs every hour.

    It:
    1. Finds all Vehicles with custom_vehicle_type.
    2. Generates missing Vehicle Service Schedules.
    3. Evaluates existing schedules.
    4. Creates Notification Log records for Due Soon / Overdue schedules.
    """

    log = frappe.logger("vehicle_maintenance_job", allow_site=True, file_count=5)

    log.info("===== Hourly vehicle maintenance job started =====")

    vehicles = frappe.get_all(
        "Vehicle",
        filters={
            "custom_vehicle_type": ["is", "set"],
        },
        fields=[
            "name",
            "license_plate",
            "custom_vehicle_type",
        ],
    )

    log.info(f"Vehicles found: {len(vehicles)}")

    total_created = 0
    total_evaluated = 0
    vehicle_errors = 0

    for vehicle in vehicles:
        try:
            created = generate_schedules_for_vehicle(vehicle.name)
            evaluated = evaluate_vehicle_maintenance(vehicle.name)

            total_created += created or 0
            total_evaluated += evaluated or 0

            frappe.db.commit()

            log.info(
                f"Vehicle {vehicle.name}: created={created}, evaluated={evaluated}"
            )

        except Exception:
            vehicle_errors += 1

            tb = frappe.get_traceback()

            log.error(f"Maintenance job failed for vehicle {vehicle.name}:\n{tb}")

            frappe.log_error(
                title=f"Vehicle Maintenance Job Error - {vehicle.name}",
                message=tb,
            )

            frappe.db.rollback()

    notification_count = 0

    try:
        notification_count = create_maintenance_notifications()
        frappe.db.commit()

    except Exception:
        tb = frappe.get_traceback()

        log.error(f"Maintenance notification job failed:\n{tb}")

        frappe.log_error(
            title="Vehicle Maintenance Notification Job Error",
            message=tb,
        )

        frappe.db.rollback()

    log.info(
        "===== Hourly vehicle maintenance job finished: "
        f"vehicles={len(vehicles)}, "
        f"created={total_created}, "
        f"evaluated={total_evaluated}, "
        f"vehicle_errors={vehicle_errors}, "
        f"notifications={notification_count} ====="
    )


def create_maintenance_notifications():
    """
    Creates Notification Log records for Due Soon / Overdue schedules.

    It avoids spam by checking `custom_last_notification_sent_at`.
    """

    users = get_maintenance_notification_users()

    if not users:
        return 0

    schedules = get_schedules_requiring_notification()

    created_count = 0

    for schedule in schedules:
        for user in users:
            if notification_already_exists_for_user(schedule.name, user):
                continue

            create_notification_log_for_schedule(schedule, user)
            created_count += 1

        frappe.db.set_value(
            "Vehicle Service Schedule",
            schedule.name,
            "custom_last_notification_sent_at",
            now_datetime(),
            update_modified=False,
        )

    return created_count


def get_maintenance_notification_users():
    """
    Returns active users who should receive maintenance notifications.

    For now it uses System Manager.
    Later you can change NOTIFICATION_ROLE to Maintenance Manager
    if you create that role.
    """

    users = frappe.get_all(
        "Has Role",
        filters={
            "role": NOTIFICATION_ROLE,
            "parenttype": "User",
        },
        pluck="parent",
    )

    active_users = []

    for user in users:
        if user == "Guest":
            continue

        enabled = frappe.db.get_value("User", user, "enabled")

        if enabled:
            active_users.append(user)

    return active_users


def get_schedules_requiring_notification():
    """
    Returns schedules that are Due Soon or Overdue and should notify users.

    Notification is sent if:
    - custom_last_notification_sent_at is empty
    OR
    - last notification was more than NOTIFICATION_REPEAT_AFTER_HOURS ago
    """

    repeat_after = add_to_date(
        now_datetime(),
        hours=-NOTIFICATION_REPEAT_AFTER_HOURS,
        as_datetime=True,
    )

    schedules = frappe.get_all(
        "Vehicle Service Schedule",
        filters={
            "status": ["in", NOTIFICATION_STATUSES],
        },
        fields=[
            "name",
            "vehicle",
            "vehicle_type",
            "service_type",
            "status",
            "due_date",
            "due_odometer",
            "current_odometer",
            "current_engine_hours",
            "custom_last_notification_sent_at",
        ],
    )

    result = []

    for schedule in schedules:
        last_sent_at = schedule.get("custom_last_notification_sent_at")

        if not last_sent_at:
            result.append(schedule)
            continue

        if last_sent_at <= repeat_after:
            result.append(schedule)

    return result


def notification_already_exists_for_user(schedule_name, user):
    """
    Extra protection against duplicate notifications in the same run.

    This checks if there is already an unread Notification Log
    for this schedule and this user.
    """

    return frappe.db.exists(
        "Notification Log",
        {
            "for_user": user,
            "document_type": "Vehicle Service Schedule",
            "document_name": schedule_name,
            "read": 0,
        },
    )


def create_notification_log_for_schedule(schedule, user):
    subject = get_notification_subject(schedule)
    message = get_notification_message(schedule)

    notification = frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": subject,
            "email_content": message,
            "for_user": user,
            "type": "Alert",
            "document_type": "Vehicle Service Schedule",
            "document_name": schedule.name,
        }
    )

    notification.insert(ignore_permissions=True)

    # Optional realtime alert if the user is online.
    frappe.publish_realtime(
        "msgprint",
        {
            "message": subject,
            "title": "Vehicle Maintenance",
            "indicator": "orange" if schedule.status == "Due Soon" else "red",
        },
        user=user,
    )


def get_notification_subject(schedule):
    vehicle_title = get_vehicle_title(schedule.vehicle)

    if schedule.status == "Overdue":
        return f"Overdue Maintenance: {vehicle_title}"

    if schedule.status == "Due Soon":
        return f"Maintenance Due Soon: {vehicle_title}"

    return f"Vehicle Maintenance: {vehicle_title}"


def get_notification_message(schedule):
    vehicle_title = get_vehicle_title(schedule.vehicle)

    parts = [
        f"Vehicle: {vehicle_title}",
        f"Service Type: {schedule.service_type or '-'}",
        f"Status: {schedule.status or '-'}",
    ]

    if schedule.due_date:
        parts.append(f"Due Date: {schedule.due_date}")

    if schedule.due_odometer:
        parts.append(f"Due Odometer: {schedule.due_odometer}")

    if schedule.current_odometer:
        parts.append(f"Current Odometer: {schedule.current_odometer}")

    return "<br>".join(parts)


def get_vehicle_title(vehicle_name):
    license_plate = frappe.db.get_value("Vehicle", vehicle_name, "license_plate")

    if license_plate:
        return f"{vehicle_name} / {license_plate}"

    return vehicle_name