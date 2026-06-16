# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleType(Document):
    def validate(self):
        self._validate_unique_name_per_company()

    def _validate_unique_name_per_company(self):
        duplicate = frappe.db.get_value(
            "Vehicle Type",
            {
                "vehicle_type_name": self.vehicle_type_name,
                "company": self.company,
                "name": ["!=", self.name],
            },
            "name",
        )
        if duplicate:
            frappe.throw(
                _(
                    "Vehicle Type '{0}' already exists for company '{1}'."
                ).format(self.vehicle_type_name, self.company)
            )


@frappe.whitelist()
def generate_schedules(docname):
    """Generate Vehicle Service Schedules for all vehicles of this type."""
    from gps_gate.apis.maintenance import generate_schedules_for_vehicle

    vehicle_type = frappe.get_doc("Vehicle Type", docname)
    vehicles = frappe.get_all(
        "Vehicle",
        filters={"custom_vehicle_type": docname, "custom_company": vehicle_type.company},
        fields=["name"],
    )
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
