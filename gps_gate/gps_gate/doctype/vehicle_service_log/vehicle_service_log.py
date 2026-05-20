# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import logging
import frappe
from frappe import _
from frappe.model.document import Document

log = frappe.logger("vehicle_service_log", allow_site=True, file_count=5)
log.setLevel(logging.DEBUG)
logger = log

class VehicleServiceLog(Document):
    def validate(self):
        if not self.service_type:
            frappe.throw(_("Please select at least one Service Type."))

    def on_update(self):
        _sync_to_gps_gate(self)

    def on_submit(self):
        # Mark each referenced schedule as Completed
        for row in self.schedule_reference:
            frappe.db.set_value(
                "Vehicle Service Schedule", row.schedule_reference, "status", "Completed"
            )
        # Create next schedule for each service type
        _create_next_schedule(self)
        frappe.db.commit()

    def on_cancel(self):
        # Revert each referenced schedule status to Due Soon / Overdue
        if self.schedule_reference:
            from gps_gate.gps_gate.doctype.vehicle_service_schedule.vehicle_service_schedule import (
                _evaluate_status,
            )
            for row in self.schedule_reference:
                schedule = frappe.get_doc("Vehicle Service Schedule", row.schedule_reference)
                schedule.status = _evaluate_status(schedule)
                schedule.save(ignore_permissions=True)
        frappe.db.commit()


def _sync_to_gps_gate(log_doc):
    """Push last maintenance date and odometer to GPS Gate custom fields."""
    import traceback

    try:
        gps_gate_user_id = frappe.db.get_value("Vehicle", log_doc.vehicle, "custom_gpsgate_user_id")

        logger.info(
            f"[GPS Gate Sync] Vehicle={log_doc.vehicle} | GPS Gate User ID={gps_gate_user_id} | "
            f"service_date={log_doc.service_date} | service_odometer={log_doc.service_odometer}"
        )

        if not gps_gate_user_id:
            logger.warning(f"[GPS Gate Sync] Skipped — no GPS Gate User ID on vehicle {log_doc.vehicle}")
            return

        from gps_gate.gps_gate_api import GPSGateClient
        client = GPSGateClient()

        if log_doc.service_date:
            logger.info(f"[GPS Gate Sync] Updating 'Last Maintenance Date' → {log_doc.service_date}")
            client.update_user_custom_field(gps_gate_user_id, "Last Maintenance Date", str(log_doc.service_date))
            logger.info("[GPS Gate Sync] 'Last Maintenance Date' updated successfully")

        if log_doc.service_odometer is not None:
            logger.info(f"[GPS Gate Sync] Updating 'Last Maintenance KM' → {log_doc.service_odometer}")
            client.update_user_custom_field(gps_gate_user_id, "Last Maintenance KM", log_doc.service_odometer)
            logger.info("[GPS Gate Sync] 'Last Maintenance KM' updated successfully")

    except Exception as e:
        frappe.log_error(
            title="GPS Gate Sync Error (Service Log)",
            message=f"{str(e)}\n\n{traceback.format_exc()}"
        )


def _create_next_schedule(log_doc):
    """Create the next Vehicle Service Schedule for each service type after a service is logged."""
    from frappe.utils import add_days

    vehicle = frappe.get_doc("Vehicle", log_doc.vehicle)
    vehicle_type_name = vehicle.get("custom_vehicle_type")
    if not vehicle_type_name:
        return
    vehicle_type = frappe.get_doc("Vehicle Type", vehicle_type_name)

    for st_row in log_doc.service_type:
        service_type = st_row.service_type
        rule = next(
            (r for r in vehicle_type.service_rules if r.service_type == service_type), None
        )
        if not rule or not rule.auto_create_schedule:
            continue

        due_date = (
            add_days(log_doc.service_date, rule.interval_days)
            if rule.interval_days and log_doc.service_date
            else None
        )
        due_odometer = (
            (log_doc.service_odometer or 0) + rule.interval_km if rule.interval_km else None
        )
        due_engine_hours = (
            (log_doc.service_engine_hours or 0) + rule.interval_engine_hours
            if rule.interval_engine_hours
            else None
        )

        schedule = frappe.new_doc("Vehicle Service Schedule")
        schedule.vehicle = log_doc.vehicle
        schedule.vehicle_type = vehicle_type_name
        schedule.service_type = service_type
        schedule.based_on = rule.based_on
        schedule.last_service_date = log_doc.service_date
        schedule.last_service_odometer = log_doc.service_odometer
        schedule.last_service_engine_hours = log_doc.service_engine_hours
        schedule.due_date = due_date
        schedule.due_odometer = due_odometer
        schedule.due_engine_hours = due_engine_hours
        schedule.current_odometer = vehicle.get("custom_current_odometer") or 0
        schedule.current_engine_hours = vehicle.get("custom_current_engine_hours") or 0
        schedule.warning_before_km = rule.warning_before_km
        schedule.warning_before_days = rule.warning_before_days
        schedule.warning_before_engine_hours = rule.warning_before_engine_hours
        schedule.source_rule = service_type
        schedule.raw_rule_json = frappe.as_json(rule.as_dict())
        schedule.insert(ignore_permissions=True)
