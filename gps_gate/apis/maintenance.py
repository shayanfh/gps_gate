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
    return vehicle.get("odometer") or vehicle.get("custom_current_odometer") or 0


def _get_vehicle_engine_hours(vehicle):
    """
    Keep this fallback for future engine-hour support.
    If you do not use engine hours, it will remain 0.
    """
    return vehicle.get("custom_current_engine_hours") or 0


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

        last_log = frappe.db.get_value(
            "Vehicle Service Log",
            {
                "vehicle": vehicle_name,
                "service_type": rule.service_type,
                "docstatus": 1,
            },
            ["service_date", "service_odometer", "service_engine_hours"],
            as_dict=True,
            order_by="service_date desc",
        )

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