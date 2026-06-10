import frappe


def on_update(doc, method=None):
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
