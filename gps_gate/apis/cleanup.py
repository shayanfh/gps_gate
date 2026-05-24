import frappe


@frappe.whitelist()
def cleanup_maintenance_data():
    """
    Deletes all Vehicle Service Logs, Vehicle Service Schedules, and Vehicles.

    Order matters:
      1. Service Logs  (submitted ones are cancelled first)
      2. Service Schedules
      3. Vehicles

    Only callable by System Manager.
    """
    frappe.only_for("System Manager")

    result = {
        "logs_deleted": 0,
        "schedules_deleted": 0,
        "vehicles_deleted": 0,
        "errors": [],
    }

    # ── 1. Vehicle Service Logs ──────────────────────────────────────────────
    logs = frappe.get_all(
        "Vehicle Service Log",
        fields=["name", "docstatus"],
        order_by="creation desc",
    )

    for row in logs:
        try:
            if row.docstatus == 1:
                doc = frappe.get_doc("Vehicle Service Log", row.name)
                doc.cancel()
                frappe.db.commit()

            frappe.delete_doc(
                "Vehicle Service Log",
                row.name,
                force=True,
                ignore_permissions=True,
            )
            frappe.db.commit()
            result["logs_deleted"] += 1

        except Exception:
            frappe.db.rollback()
            result["errors"].append(
                {"doctype": "Vehicle Service Log", "name": row.name, "error": frappe.get_traceback()}
            )

    # ── 2. Vehicle Service Schedules ─────────────────────────────────────────
    schedules = frappe.get_all("Vehicle Service Schedule", pluck="name")

    for name in schedules:
        try:
            frappe.delete_doc(
                "Vehicle Service Schedule",
                name,
                force=True,
                ignore_permissions=True,
            )
            frappe.db.commit()
            result["schedules_deleted"] += 1

        except Exception:
            frappe.db.rollback()
            result["errors"].append(
                {"doctype": "Vehicle Service Schedule", "name": name, "error": frappe.get_traceback()}
            )

    # ── 3. Vehicles ──────────────────────────────────────────────────────────
    vehicles = frappe.get_all("Vehicle", pluck="name")

    for name in vehicles:
        try:
            frappe.delete_doc(
                "Vehicle",
                name,
                force=True,
                ignore_permissions=True,
            )
            frappe.db.commit()
            result["vehicles_deleted"] += 1

        except Exception:
            frappe.db.rollback()
            result["errors"].append(
                {"doctype": "Vehicle", "name": name, "error": frappe.get_traceback()}
            )

    frappe.logger("cleanup").info(
        f"Cleanup done — logs={result['logs_deleted']}, "
        f"schedules={result['schedules_deleted']}, "
        f"vehicles={result['vehicles_deleted']}, "
        f"errors={len(result['errors'])}"
    )

    return result
