# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleServiceLog(Document):
    def on_submit(self):
        # 1. Mark referenced schedule as Completed
        if self.schedule_reference:
            frappe.db.set_value(
                "Vehicle Service Schedule", self.schedule_reference, "status", "Completed"
            )
        # 2. Create next schedule
        _create_next_schedule(self)
        frappe.db.commit()

    def on_cancel(self):
        # Revert schedule status to Due Soon / Overdue
        if self.schedule_reference:
            from gps_gate.gps_gate.doctype.vehicle_service_schedule.vehicle_service_schedule import (
                _evaluate_status,
            )

            schedule = frappe.get_doc("Vehicle Service Schedule", self.schedule_reference)
            schedule.status = _evaluate_status(schedule)
            schedule.save(ignore_permissions=True)
        frappe.db.commit()


def _create_next_schedule(log_doc):
    """Create the next Vehicle Service Schedule after a service is logged."""
    from frappe.utils import add_days

    vehicle = frappe.get_doc("Vehicle", log_doc.vehicle)
    vehicle_type_name = vehicle.get("custom_vehicle_type")
    if not vehicle_type_name:
        return
    vehicle_type = frappe.get_doc("Vehicle Type", vehicle_type_name)
    rule = next(
        (r for r in vehicle_type.service_rules if r.service_type == log_doc.service_type), None
    )
    if not rule or not rule.auto_create_schedule:
        return

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
    schedule.service_type = log_doc.service_type
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
    schedule.source_rule = rule.service_type
    schedule.raw_rule_json = frappe.as_json(rule.as_dict())
    schedule.insert(ignore_permissions=True)
