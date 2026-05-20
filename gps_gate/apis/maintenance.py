# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

"""
Fleet Maintenance Logic
=======================

Shared functions for generating and evaluating Vehicle Service Schedules.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate


OPEN_SCHEDULE_STATUSES = ["OK", "Due Soon", "Overdue"]


def _get_vehicle_odometer(vehicle):
    """
    Vehicle standard field is `odometer`.
    Fallback to custom_current_odometer only for old data compatibility.
    """
    return vehicle.get("last_odometer") or vehicle.get("custom_current_odometer") or 0


def _get_vehicle_engine_hours(vehicle):
    """
    Keep this fallback for future engine-hour support.
    If you do not use engine hours, it will remain 0.
    """
    return vehicle.get("custom_current_engine_hours") or 0


def _fetch_gpsgate_initial_maintenance(vehicle):
    """
    Read GPS Gate last-maintenance snapshot from the Vehicle record.
    These fields are synced from GPS Gate custom fields during vehicle sync.

    Returns:
        (date, km) tuple if data exists, otherwise (None, None)
    """
    gpsgate_date = vehicle.get("custom_last_maintenance_date")
    gpsgate_km = vehicle.get("custom_last_maintenance_km") or 0
    if gpsgate_date:
        return gpsgate_date, gpsgate_km
    return None, None


def _log_has_service_type(vehicle_name, service_type):
    """Return True if a submitted Vehicle Service Log for the vehicle includes the given service type."""
    parent_names = frappe.get_all(
        "Vehicle Service Log",
        filters={"vehicle": vehicle_name, "docstatus": 1},
        pluck="name",
    )
    if not parent_names:
        return False
    return bool(frappe.db.exists(
        "Vehicle Service Log Service Type",
        {
            "service_type": service_type,
            "parent": ["in", parent_names],
            "parenttype": "Vehicle Service Log",
        },
    ))


def _get_last_log_for_service_type(vehicle_name, service_type):
    """Return the most recent submitted log dict that includes the given service type, or None."""
    parent_names = frappe.get_all(
        "Vehicle Service Log Service Type",
        filters={
            "service_type": service_type,
            "parenttype": "Vehicle Service Log",
        },
        pluck="parent",
    )
    if not parent_names:
        return None
    return frappe.db.get_value(
        "Vehicle Service Log",
        {
            "name": ["in", parent_names],
            "vehicle": vehicle_name,
            "docstatus": 1,
        },
        ["service_date", "service_odometer", "service_engine_hours"],
        as_dict=True,
        order_by="service_date desc",
    )


def _create_initial_service_logs(vehicle, vehicle_type, init_date, init_km):
    """
    For each active rule in the vehicle type, create a submitted initial
    Vehicle Service Log seeded from GPS Gate last-maintenance data.

    Called once when a vehicle has no service logs at all but GPS Gate
    provides a last-maintenance date and KM as a starting point.

    Returns:
        int: count of logs created
    """
    created = 0

    for rule in vehicle_type.service_rules:
        if not rule.auto_create_schedule:
            continue

        if _log_has_service_type(vehicle.name, rule.service_type):
            continue

        try:
            log = frappe.new_doc("Vehicle Service Log")
            log.vehicle = vehicle.name
            log.append("service_type", {"service_type": rule.service_type})
            log.service_date = init_date
            log.service_odometer = init_km
            log.service_engine_hours = 0
            log.remarks = "Initial log seeded from GPS Gate last maintenance data."
            log.insert(ignore_permissions=True)
            log.submit()
            created += 1
        except Exception:
            frappe.log_error(
                title="GPS Gate Initial Service Log Error",
                message=frappe.get_traceback(),
            )

    return created


def generate_schedules_for_vehicle(vehicle_name):
    """
    Generate Vehicle Service Schedules for one vehicle based on its Vehicle Type rules.

    Skips rules that already have an open schedule.

    Returns:
        int: count of created schedules
    """

    vehicle = frappe.get_doc("Vehicle", vehicle_name)

    vehicle_type_name = vehicle.get("custom_vehicle_type")
    if not vehicle_type_name:
        return 0

    vehicle_type = frappe.get_doc("Vehicle Type", vehicle_type_name)

    if not vehicle_type.is_active:
        return 0

    # If this vehicle has no service logs at all, try to seed initial logs
    # from the GPS Gate last-maintenance snapshot (synced onto the Vehicle record).
    has_any_log = frappe.db.exists(
        "Vehicle Service Log",
        {"vehicle": vehicle_name, "docstatus": 1},
    )
    if not has_any_log:
        init_date, init_km = _fetch_gpsgate_initial_maintenance(vehicle)
        if init_date:
            _create_initial_service_logs(vehicle, vehicle_type, init_date, init_km)

    created = 0

    for rule in vehicle_type.service_rules:
        if not rule.auto_create_schedule:
            continue

        existing = frappe.db.exists(
            "Vehicle Service Schedule",
            {
                "vehicle": vehicle_name,
                "service_type": rule.service_type,
                "status": ["in", OPEN_SCHEDULE_STATUSES],
            },
        )

        if existing:
            continue

        last_log = _get_last_log_for_service_type(vehicle_name, rule.service_type)

        if last_log:
            last_date = last_log.service_date
            last_odometer = last_log.service_odometer or 0
            last_engine_hours = last_log.service_engine_hours or 0
        else:
            last_date = vehicle.get("purchase_date") or getdate(vehicle.creation)
            last_odometer = _get_vehicle_odometer(vehicle)
            last_engine_hours = _get_vehicle_engine_hours(vehicle)

        due_date = add_days(last_date, rule.interval_days) if rule.interval_days else None
        due_odometer = last_odometer + rule.interval_km if rule.interval_km else None

        due_engine_hours = (
            last_engine_hours + rule.interval_engine_hours
            if rule.interval_engine_hours
            else None
        )

        schedule = frappe.new_doc("Vehicle Service Schedule")

        schedule.vehicle = vehicle_name
        schedule.vehicle_type = vehicle_type_name
        schedule.service_type = rule.service_type
        schedule.based_on = rule.based_on

        schedule.last_service_date = last_date
        schedule.last_service_odometer = last_odometer
        schedule.last_service_engine_hours = last_engine_hours

        schedule.due_date = due_date
        schedule.due_odometer = due_odometer
        schedule.due_engine_hours = due_engine_hours

        schedule.current_odometer = _get_vehicle_odometer(vehicle)
        schedule.current_engine_hours = _get_vehicle_engine_hours(vehicle)

        schedule.warning_before_km = rule.warning_before_km
        schedule.warning_before_days = rule.warning_before_days
        schedule.warning_before_engine_hours = rule.warning_before_engine_hours

        schedule.source_rule = rule.service_type
        schedule.raw_rule_json = frappe.as_json(rule.as_dict())

        schedule.insert(ignore_permissions=True)
        created += 1

    return created


def evaluate_vehicle_maintenance(vehicle_name):
    """
    Re-evaluate status for all open Vehicle Service Schedules of one vehicle.

    Updates current_odometer and current_engine_hours from the Vehicle record.

    Returns:
        int: count of updated schedules
    """

    from gps_gate.gps_gate.doctype.vehicle_service_schedule.vehicle_service_schedule import (
        _evaluate_status,
    )

    vehicle = frappe.get_doc("Vehicle", vehicle_name)

    current_odometer = _get_vehicle_odometer(vehicle)
    current_engine_hours = _get_vehicle_engine_hours(vehicle)

    schedules = frappe.get_all(
        "Vehicle Service Schedule",
        filters={
            "vehicle": vehicle_name,
            "status": ["in", OPEN_SCHEDULE_STATUSES],
        },
        fields=["name"],
    )

    updated = 0

    for s in schedules:
        schedule = frappe.get_doc("Vehicle Service Schedule", s.name)

        schedule.current_odometer = current_odometer
        schedule.current_engine_hours = current_engine_hours

        new_status = _evaluate_status(schedule)

        if schedule.status != new_status:
            schedule.status = new_status
            updated += 1

        schedule.save(ignore_permissions=True)

    return updated