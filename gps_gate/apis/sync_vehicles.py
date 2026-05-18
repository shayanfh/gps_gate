import frappe
from frappe.utils import now
from frappe import _
from datetime import datetime

from gps_gate.gps_gate_api import GPSGateClient, GPSGateAPIError


_CUSTOM_FIELD_MAP = {
    "Vehicle Model":         "model",
    "Vehicle Brand":         "custom_vehicle_brand",
    "Chassis":               "custom_chassis",
    "Installation Location": "custom_installation_location",
    "Position":              "custom_position",
    "Installation Date":     "custom_installation_date",
    "Last Maintenance Date": "custom_last_maintenance_date",
    "Department":            "custom_department",
    "Level 2":               "custom_level_2",
    "Last Maintenance KM":   "custom_last_maintenance_km",
}

_DATE_FIELDS  = {"custom_installation_date", "custom_last_maintenance_date"}
_FLOAT_FIELDS = {"custom_last_maintenance_km"}


def _get_device_type_id():
    type_id = frappe.db.get_value(
        "GPS User Types", {"user_type_name": "Device"}, "user_type_id"
    )
    if not type_id:
        frappe.throw(_("User type 'Device' not found in GPS User Types. Please sync user types first."))
    return int(type_id)


def _parse_gps_date(value):
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _apply_accumulators(doc, accumulators, log):
    for acc in (accumulators or []):
        if acc.get("accumulatorTypeId") == 1:
            raw = acc.get("value") or 0
            doc.custom_current_odometer = round(raw / 1000, 2)
            log.info(f"  odometer: {doc.custom_current_odometer} km")
            break


def _apply_custom_fields(doc, custom_fields):
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


_FIELD_DEFAULTS = {
    "uom": "Litre",
}

_default_vehicle_type_cache = None


def _get_default_vehicle_type():
    global _default_vehicle_type_cache
    if not _default_vehicle_type_cache:
        _default_vehicle_type_cache = frappe.db.get_value(
            "Vehicle Type", {"is_active": 1}, "name", order_by="creation asc"
        )
    return _default_vehicle_type_cache


def _fill_mandatory_fields(doc):
    meta = frappe.get_meta("Vehicle")
    for field in meta.fields:
        if not field.reqd or doc.get(field.fieldname):
            continue
        if field.fieldname == "custom_vehicle_type":
            default_type = _get_default_vehicle_type()
            if default_type:
                doc.set(field.fieldname, default_type)
        elif field.fieldname in _FIELD_DEFAULTS:
            doc.set(field.fieldname, _FIELD_DEFAULTS[field.fieldname])
        elif field.fieldtype not in ("Link", "Select", "Table", "Table MultiSelect"):
            doc.set(field.fieldname, "X")


def _sync_single_vehicle(u, client, log):
    """Fetch data, save one Vehicle, commit immediately. Returns 'created'|'updated'."""
    gps_user_id = u.get("id")
    username    = u.get("username") or str(gps_user_id)

    log.info(f"--- syncing user_id={gps_user_id} username={username}")

    devices        = u.get("devices") or []
    first_device_id = str(devices[0].get("id")) if devices else ""

    vehicle_name = frappe.db.get_value(
        "Vehicle", {"custom_gpsgate_user_id": gps_user_id}, "name"
    )

    if vehicle_name:
        doc = frappe.get_doc("Vehicle", vehicle_name)
        action = "updated"
    else:
        existing = frappe.db.get_value("Vehicle", {"license_plate": username}, "name")
        if existing:
            doc = frappe.get_doc("Vehicle", existing)
            action = "updated"
        else:
            doc = frappe.new_doc("Vehicle")
            doc.license_plate = username
            action = "created"

    doc.custom_gpsgate_user_id  = gps_user_id
    doc.custom_gpsgate_device_id = first_device_id
    doc.custom_last_telematics_sync = now()

    try:
        accumulators = client.get_user_accumulators(gps_user_id)
        _apply_accumulators(doc, accumulators, log)
    except Exception:
        tb = frappe.get_traceback()
        log.warning(f"  accumulators failed: {tb}")
        frappe.log_error(title=f"Vehicle Sync - Accumulators (user {gps_user_id})", message=tb)

    try:
        custom_fields = client.get_user_custom_fields(gps_user_id)
        _apply_custom_fields(doc, custom_fields)
    except Exception:
        tb = frappe.get_traceback()
        log.warning(f"  custom_fields failed: {tb}")
        frappe.log_error(title=f"Vehicle Sync - Custom Fields (user {gps_user_id})", message=tb)

    _fill_mandatory_fields(doc)

    if action == "created":
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    # commit after every vehicle so progress is visible in real-time
    frappe.db.commit()
    log.info(f"  {action}: {doc.name}")
    return action


def _run_sync():
    """Background job — called by frappe.enqueue."""
    log = frappe.logger("vehicle_sync", allow_site=True, file_count=5)
    log.info("===== Vehicle sync started =====")

    try:
        client = GPSGateClient()
    except GPSGateAPIError as e:
        log.error(f"GPSGateClient init failed: {e.message}")
        frappe.log_error(title="Vehicle Sync - Client Error", message=str(e.message))
        return

    log.info("Fetching all users from GPS Gate...")
    try:
        users = client.get_users()
    except Exception:
        tb = frappe.get_traceback()
        log.error(f"get_users failed:\n{tb}")
        frappe.log_error(title="Vehicle Sync - get_users Error", message=tb)
        return

    log.info(f"Total users fetched: {len(users)}")

    device_type_id = _get_device_type_id()
    device_users = [u for u in users if u.get("userTemplateID") == device_type_id]
    log.info(f"Device users to sync: {len(device_users)}")

    created = updated = 0
    errors  = []

    for i, u in enumerate(device_users, 1):
        gps_user_id = u.get("id")
        log.info(f"[{i}/{len(device_users)}] user_id={gps_user_id}")
        try:
            action = _sync_single_vehicle(u, client, log)
            if action == "created":
                created += 1
            else:
                updated += 1
        except Exception:
            tb = frappe.get_traceback()
            label = u.get("username") or str(gps_user_id)
            errors.append(label)
            log.error(f"  FAILED {label}:\n{tb}")
            frappe.log_error(title=f"Vehicle Sync Error - user {gps_user_id}", message=tb)

    log.info(f"===== Done: created={created}, updated={updated}, errors={len(errors)} =====")


@frappe.whitelist()
def sync_vehicles_from_gps_gate():
    """Enqueue the vehicle sync as a long background job."""
    frappe.enqueue(
        "gps_gate.apis.sync_vehicles._run_sync",
        queue="long",
        timeout=3600,
        job_id="gps_gate_vehicle_sync",
        deduplicate=True,
    )
    return {"status": "queued"}


@frappe.whitelist()
def bulk_set_vehicle_type(vehicles, vehicle_type):
    """Set custom_vehicle_type for a list of Vehicle names."""
    import json

    frappe.has_permission("Vehicle", "write", throw=True)

    if isinstance(vehicles, str):
        vehicles = json.loads(vehicles)

    if not frappe.db.exists("Vehicle Type", vehicle_type):
        frappe.throw(_("Vehicle Type '{0}' does not exist.").format(vehicle_type))

    for name in vehicles:
        frappe.db.set_value("Vehicle", name, "custom_vehicle_type", vehicle_type)

    frappe.db.commit()
    return {"updated": len(vehicles)}
