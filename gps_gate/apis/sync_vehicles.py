import frappe
from frappe.utils import now
from frappe import _

from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError


@frappe.whitelist()
def sync_vehicles_from_gps_gate():
    """
    Fetch GPS Gate users that have at least one device and sync them to Vehicle doctype.
    Matches on custom_gpsgate_user_id first, then license_plate = username.
    Creates new Vehicle records for unmatched users.
    """
    try:
        client = get_gps_gate_client()
        users = client.get_users()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception:
        frappe.log_error(title="Vehicle Sync - API Error", message=frappe.get_traceback())
        frappe.throw(_("Unable to connect to GPS Gate API"))

    users_with_devices = [u for u in users if u.get("devices")]

    created = 0
    updated = 0
    errors = []

    for u in users_with_devices:
        try:
            gps_user_id = u.get("id")
            if not gps_user_id:
                continue

            username = u.get("username") or str(gps_user_id)
            devices = u.get("devices") or []
            first_device_id = str(devices[0].get("id")) if devices else ""

            vehicle_name = frappe.db.get_value(
                "Vehicle",
                {"custom_gpsgate_user_id": gps_user_id},
                "name"
            )

            if vehicle_name:
                doc = frappe.get_doc("Vehicle", vehicle_name)
                doc.custom_gpsgate_device_id = first_device_id
                doc.custom_last_telematics_sync = now()
                doc.save(ignore_permissions=True)
                updated += 1
            else:
                existing_by_plate = frappe.db.get_value(
                    "Vehicle",
                    {"license_plate": username},
                    "name"
                )
                if existing_by_plate:
                    doc = frappe.get_doc("Vehicle", existing_by_plate)
                    doc.custom_gpsgate_user_id = gps_user_id
                    doc.custom_gpsgate_device_id = first_device_id
                    doc.custom_last_telematics_sync = now()
                    doc.save(ignore_permissions=True)
                    updated += 1
                else:
                    doc = frappe.new_doc("Vehicle")
                    doc.license_plate = username
                    doc.custom_gpsgate_user_id = gps_user_id
                    doc.custom_gpsgate_device_id = first_device_id
                    doc.custom_last_telematics_sync = now()
                    doc.insert(ignore_permissions=True)
                    created += 1

        except Exception:
            errors.append(u.get("username") or str(u.get("id")))
            frappe.log_error(
                title="Vehicle Sync Error",
                message=frappe.get_traceback()
            )

    frappe.db.commit()

    return {
        "created": created,
        "updated": updated,
        "total_with_devices": len(users_with_devices),
        "errors": errors
    }
