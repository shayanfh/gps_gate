# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleType(Document):
    pass


@frappe.whitelist()
def generate_schedules(docname):
    """Generate Vehicle Service Schedules for all vehicles of this type."""
    from gps_gate.apis.maintenance import generate_schedules_for_vehicle

    vehicle_type = frappe.get_doc("Vehicle Type", docname)
    vehicles = frappe.get_all("Vehicle", filters={"custom_vehicle_type": docname}, fields=["name"])
    created = 0
    for v in vehicles:
        created += generate_schedules_for_vehicle(v.name)
    frappe.db.commit()
    return {
        "status": "success",
        "created": created,
        "vehicles": len(vehicles),
        "message": f"Generated {created} schedules across {len(vehicles)} vehicle(s)"
    }
