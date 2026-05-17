import frappe
from frappe.utils import now
from frappe import _
from datetime import datetime

from gps_gate.gps_gate_api import GPSGateClient, GPSGateAPIError


# Maps GPS Gate custom field names → Vehicle fieldnames
_CUSTOM_FIELD_MAP = {
    "Vehicle Model":        "custom_vehicle_model",
    "Vehicle Brand":        "custom_vehicle_brand",
    "Chassis":              "custom_chassis",
    "Installation Location":"custom_installation_location",
    "Position":             "custom_position",
    "Installation Date":    "custom_installation_date",
    "Last Maintenance Date":"custom_last_maintenance_date",
    "Department":           "custom_department",
    "Level 2":              "custom_level_2",
    "Last Maintenance KM":  "custom_last_maintenance_km",
}

_DATE_FIELDS = {"custom_installation_date", "custom_last_maintenance_date"}
_FLOAT_FIELDS = {"custom_last_maintenance_km"}


def _get_device_type_id():
    """Return the GPS Gate userTemplateID (as int) for the 'Device' user type."""
    type_id = frappe.db.get_value(
        "GPS User Types", {"user_type_name": "Device"}, "user_type_id"
    )
    if not type_id:
        frappe.throw(_("User type 'Device' not found in GPS User Types. Please sync user types first."))
    return int(type_id)


def _parse_gps_date(value):
    """Parse GPS Gate date strings (e.g. '20-May-2024') to 'YYYY-MM-DD'."""
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _apply_accumulators(doc, accumulators):
    """Map accumulators onto the Vehicle doc. accumulatorTypeId=1 → odometer (m → km)."""
    for acc in (accumulators or []):
        if acc.get("accumulatorTypeId") == 1:
            raw = acc.get("value") or 0
            doc.custom_current_odometer = round(raw / 1000, 2)
            break


def _apply_custom_fields(doc, custom_fields):
    """Map GPS Gate custom fields onto the Vehicle doc."""
    for cf in (custom_fields or []):
        fieldname = _CUSTOM_FIELD_MAP.get(cf.get("name"))
        if not fieldname:
            continue
        value = cf.get("value") or ""
        if fieldname in _DATE_FIELDS:
            value = _parse_gps_date(value)
        elif fieldname in _FLOAT_FIELDS:
            try:
                value = float(value) if value else 0.0
            except (ValueError, TypeError):
                value = 0.0
        doc.set(fieldname, value)


def _fill_mandatory_fields(doc):
    """Fill any mandatory Vehicle fields that are empty with 'X'."""
    meta = frappe.get_meta("Vehicle")
    for field in meta.fields:
        if field.reqd and not doc.get(field.fieldname):
            doc.set(field.fieldname, "X")


def _set_vehicle_fields(doc, u, first_device_id, client):
    """Apply all GPS Gate data (user + accumulators + custom fields) onto doc."""
    gps_user_id = u.get("id")

    doc.custom_gpsgate_user_id = gps_user_id
    doc.custom_gpsgate_device_id = first_device_id
    doc.custom_last_telematics_sync = now()

    try:
        accumulators = client.get_user_accumulators(gps_user_id)
        _apply_accumulators(doc, accumulators)
    except Exception:
        frappe.log_error(
            title=f"Vehicle Sync - Accumulators Error (user {gps_user_id})",
            message=frappe.get_traceback()
        )

    try:
        custom_fields = client.get_user_custom_fields(gps_user_id)
        _apply_custom_fields(doc, custom_fields)
    except Exception:
        frappe.log_error(
            title=f"Vehicle Sync - Custom Fields Error (user {gps_user_id})",
            message=frappe.get_traceback()
        )

    _fill_mandatory_fields(doc)


@frappe.whitelist()
def sync_vehicles_from_gps_gate():
    """
    Fetch GPS Gate users whose userTemplateID matches the 'Device' type,
    then create or update Vehicle records with accumulators and custom fields.
    """
    try:
        client = GPSGateClient()
        users = client.get_users()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
        return
    except Exception:
        frappe.log_error(title="Vehicle Sync - API Error", message=frappe.get_traceback())
        frappe.throw(_("Unable to connect to GPS Gate API"))
        return

    device_type_id = _get_device_type_id()
    device_users = [u for u in users if u.get("userTemplateID") == device_type_id]

    created = 0
    updated = 0
    errors = []

    for u in device_users:
        try:
            gps_user_id = u.get("id")
            if not gps_user_id:
                continue

            username = u.get("username") or str(gps_user_id)
            devices = u.get("devices") or []
            first_device_id = str(devices[0].get("id")) if devices else ""

            vehicle_name = frappe.db.get_value(
                "Vehicle", {"custom_gpsgate_user_id": gps_user_id}, "name"
            )

            if vehicle_name:
                doc = frappe.get_doc("Vehicle", vehicle_name)
                _set_vehicle_fields(doc, u, first_device_id, client)
                doc.save(ignore_permissions=True)
                updated += 1
            else:
                existing_by_plate = frappe.db.get_value(
                    "Vehicle", {"license_plate": username}, "name"
                )
                if existing_by_plate:
                    doc = frappe.get_doc("Vehicle", existing_by_plate)
                    _set_vehicle_fields(doc, u, first_device_id, client)
                    doc.save(ignore_permissions=True)
                    updated += 1
                else:
                    doc = frappe.new_doc("Vehicle")
                    doc.license_plate = username
                    _set_vehicle_fields(doc, u, first_device_id, client)
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
        "total_device_users": len(device_users),
        "errors": errors,
    }
