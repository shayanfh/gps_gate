import frappe
from frappe import _


def on_update(doc, method=None):
    _validate_vehicle_type_company(doc)

    old_doc = getattr(doc, "_doc_before_save", None)
    if not old_doc:
        return

    old_type = old_doc.get("custom_vehicle_type")
    new_type = doc.custom_vehicle_type

    if old_type == new_type:
        return

    has_logs = frappe.db.exists("Vehicle Service Log", {"vehicle": doc.name})
    if has_logs:
        return

    frappe.db.delete("Vehicle Service Schedule", {"vehicle": doc.name})


def _validate_vehicle_type_company(doc):
    """Ensure the selected Vehicle Type belongs to the same company as the vehicle."""
    if not doc.custom_vehicle_type or not doc.custom_company:
        return

    vt_company = frappe.db.get_value("Vehicle Type", doc.custom_vehicle_type, "company")
    if vt_company and vt_company != doc.custom_company:
        frappe.throw(
            _(
                "Vehicle Type '{0}' belongs to company '{1}', but this vehicle is assigned to '{2}'."
            ).format(doc.custom_vehicle_type, vt_company, doc.custom_company)
        )
