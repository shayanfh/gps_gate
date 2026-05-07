# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleServiceSchedule(Document):
    def before_save(self):
        if self.status not in ("Completed", "Cancelled"):
            self.status = _evaluate_status(self)


def _evaluate_status(schedule):
    from frappe.utils import getdate, today

    today_date = getdate(today())
    based_on = schedule.based_on or "Whichever Comes First"
    overdue = False

    if based_on in ("Date", "Whichever Comes First"):
        if schedule.due_date and today_date > getdate(schedule.due_date):
            overdue = True
    if based_on in ("Odometer", "Whichever Comes First"):
        if (
            schedule.due_odometer
            and schedule.current_odometer
            and schedule.current_odometer >= schedule.due_odometer
        ):
            overdue = True
    if based_on in ("Engine Hours", "Whichever Comes First"):
        if (
            schedule.due_engine_hours
            and schedule.current_engine_hours
            and schedule.current_engine_hours >= schedule.due_engine_hours
        ):
            overdue = True

    if overdue:
        return "Overdue"

    due_soon = False
    if based_on in ("Date", "Whichever Comes First"):
        if schedule.due_date and schedule.warning_before_days:
            days_remaining = (getdate(schedule.due_date) - today_date).days
            if 0 <= days_remaining <= schedule.warning_before_days:
                due_soon = True
    if based_on in ("Odometer", "Whichever Comes First"):
        if schedule.due_odometer and schedule.current_odometer and schedule.warning_before_km:
            km_remaining = schedule.due_odometer - schedule.current_odometer
            if 0 <= km_remaining <= schedule.warning_before_km:
                due_soon = True
    if based_on in ("Engine Hours", "Whichever Comes First"):
        if (
            schedule.due_engine_hours
            and schedule.current_engine_hours
            and schedule.warning_before_engine_hours
        ):
            hrs_remaining = schedule.due_engine_hours - schedule.current_engine_hours
            if 0 <= hrs_remaining <= schedule.warning_before_engine_hours:
                due_soon = True

    return "Due Soon" if due_soon else "OK"


@frappe.whitelist()
def mark_cancelled(docname):
    frappe.db.set_value("Vehicle Service Schedule", docname, "status", "Cancelled")
    frappe.db.commit()
    return {"status": "success"}


@frappe.whitelist()
def refresh_all_schedules():
    """Re-evaluate status for all open schedules."""
    from gps_gate.apis.maintenance import evaluate_vehicle_maintenance

    vehicles = frappe.get_all("Vehicle", filters={"name": ["is", "set"]}, fields=["name"])
    for v in vehicles:
        try:
            evaluate_vehicle_maintenance(v.name)
        except Exception:
            frappe.log_error(title="Schedule Refresh Error", message=frappe.get_traceback())
    frappe.db.commit()
    return {"status": "success", "message": f"Refreshed schedules for {len(vehicles)} vehicles"}
