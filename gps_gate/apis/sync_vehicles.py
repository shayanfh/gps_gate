import json
from datetime import datetime
import logging

import frappe
from frappe import _
from frappe.utils import now, cint

from gps_gate.gps_gate_api import GPSGateClient, GPSGateAPIError


_SYNC_CANCEL_KEY = "gps_gate_vehicle_sync_cancel"

def _set_cancel_flag(value):
    frappe.db.set_default(_SYNC_CANCEL_KEY, str(value))
    frappe.db.commit()


def _get_cancel_flag():
    # Commit first to start a new transaction and get a fresh snapshot.
    # MySQL REPEATABLE READ would otherwise return the stale value from the
    # transaction's start, missing commits from the web-worker cancel request.
    frappe.db.commit()
    result = frappe.db.sql(
        "SELECT `defvalue` FROM `tabDefaultValue` WHERE `defkey` = %s AND `parent` = '__default'",
        (_SYNC_CANCEL_KEY,),
    )
    return result[0][0] if result else "0"


def _clear_cancel_flag():
    frappe.db.set_default(_SYNC_CANCEL_KEY, "0")
    frappe.db.commit()


_CUSTOM_FIELD_MAP = {
    "Vehicle Model": "model",
    "Vehicle Brand": "custom_vehicle_brand",
    "Chassis": "custom_chassis",
    "Installation Location": "custom_installation_location",
    "Position": "custom_position",
    "Installation Date": "custom_installation_date",
    "Last Maintenance Date": "custom_last_maintenance_date",
    "Department": "custom_department",
    "Level 2": "custom_level_2",
    "Last Maintenance KM": "custom_last_maintenance_km",
}


_DATE_FIELDS = {
    "custom_installation_date",
    "custom_last_maintenance_date",
}


_FLOAT_FIELDS = {
    "custom_last_maintenance_km",
}


_FIELD_DEFAULTS = {
    "uom": "Litre",
}


_default_vehicle_type_cache = None


def _is_sync_cancelled(context=""):
    value = _get_cancel_flag()

    cancelled = value == "1"

    log = frappe.logger("vehicle_sync", allow_site=True, file_count=5)
    log.setLevel(logging.DEBUG)

    log.warning(
        f"🔎 DB cancel check context={context} "
        f"site={getattr(frappe.local, 'site', None)} "
        f"user={frappe.session.user if getattr(frappe.local, 'session', None) else None} "
        f"raw_value={value!r} cancelled={cancelled}"
    )

    return cancelled

def _emit(user, current, total, label="", status="running", **extra):
    msg = {
        "status": status,
        "current": current,
        "total": total,
        "label": label,
    }
    msg.update(extra)

    frappe.publish_realtime(
        "vehicle_sync_progress",
        msg,
        user=user,
    )


def _get_device_type_id():
    type_id = frappe.db.get_value(
        "GPS User Types",
        {"user_type_name": "Device"},
        "user_type_id",
    )

    if not type_id:
        frappe.throw(
            _("User type 'Device' not found in GPS User Types. Please sync user types first.")
        )

    return int(type_id)


def _parse_gps_date(value):
    if not value:
        return None

    value = value.strip()

    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _apply_accumulators(doc, accumulators, log):
    applied = False
    for acc in accumulators or []:
        if acc.get("accumulatorTypeId") == 1:
            raw = acc.get("value") or 0
            od = round(raw / 1000, 2)
            doc.custom_gpsgate_odometer = od
            if doc.is_new():
                doc.last_odometer = 0
            log.info(f"  odometer (from accumulator): {od} km (raw={raw})")
            applied = True
            break
    if not applied:
        log.info("No odometer accumulator found; using existing odometer value.")


def _apply_custom_fields(doc, custom_fields):
    for cf in custom_fields or []:
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


def _get_default_vehicle_type():
    global _default_vehicle_type_cache

    if not _default_vehicle_type_cache:
        _default_vehicle_type_cache = frappe.db.get_value(
            "Vehicle Type",
            {"is_active": 1},
            "name",
            order_by="creation asc",
        )

    return _default_vehicle_type_cache


def _fill_mandatory_fields(doc):
    meta = frappe.get_meta("Vehicle")

    for field in meta.fields:
        if not field.reqd:
            continue

        if doc.get(field.fieldname):
            continue

        if field.fieldname == "custom_vehicle_type":
            default_type = _get_default_vehicle_type()

            if default_type:
                doc.set(field.fieldname, default_type)

        elif field.fieldname in _FIELD_DEFAULTS:
            doc.set(field.fieldname, _FIELD_DEFAULTS[field.fieldname])

        elif field.fieldtype not in ("Link", "Select", "Table", "Table MultiSelect"):
            doc.set(field.fieldname, "X")


def _raise_if_cancelled():
    if _is_sync_cancelled():
        raise frappe.ValidationError("Vehicle sync cancelled by user.")


def _sync_single_vehicle(u, client, log):
    """
    Fetch data, save one Vehicle, commit immediately.

    Returns:
    - "created"
    - "updated"
    - "cancelled"
    """
    if _is_sync_cancelled():
        return "cancelled"

    gps_user_id = u.get("id")
    name = u.get("name") or str(gps_user_id)

    log.info(f"--- syncing user_id={gps_user_id} name={name}")

    devices = u.get("devices") or []
    first_device_id = str(devices[0].get("id")) if devices else ""

    if _is_sync_cancelled():
        return "cancelled"

    vehicle_name = frappe.db.get_value(
        "Vehicle",
        {"custom_gpsgate_user_id": gps_user_id},
        "name",
    )

    if vehicle_name:
        doc = frappe.get_doc("Vehicle", vehicle_name)
        action = "updated"
    else:
        existing = frappe.db.get_value(
            "Vehicle",
            {"license_plate": name},
            "name",
        )

        if existing:
            doc = frappe.get_doc("Vehicle", existing)
            action = "updated"
        else:
            doc = frappe.new_doc("Vehicle")
            doc.license_plate = name
            action = "created"

    if _is_sync_cancelled():
        return "cancelled"

    doc.custom_gpsgate_user_id = gps_user_id
    doc.custom_gpsgate_device_id = first_device_id
    doc.custom_last_telematics_sync = now()

    try:
        accumulators = client.get_user_accumulators(gps_user_id)

        if _is_sync_cancelled():
            return "cancelled"

        _apply_accumulators(doc, accumulators, log)
       
    except Exception:
        tb = frappe.get_traceback()
        log.warning(f"  accumulators failed: {tb}")
        frappe.log_error(
            title=f"Vehicle Sync - Accumulators user {gps_user_id}",
            message=tb,
        )

    if _is_sync_cancelled():
        return "cancelled"

    try:
        custom_fields = client.get_user_custom_fields(gps_user_id)

        if _is_sync_cancelled():
            return "cancelled"

        _apply_custom_fields(doc, custom_fields)

    except Exception:
        tb = frappe.get_traceback()
        log.warning(f"  custom_fields failed: {tb}")
        frappe.log_error(
            title=f"Vehicle Sync - Custom Fields user {gps_user_id}",
            message=tb,
        )

    if _is_sync_cancelled():
        return "cancelled"

    _fill_mandatory_fields(doc)

    if _is_sync_cancelled():
        return "cancelled"

    if action == "created":
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    frappe.db.commit()

    log.info(f"  {action}: {doc.name}")
    return action


def _run_sync(triggered_by=None):
    log = frappe.logger("vehicle_sync", allow_site=True, file_count=5)
    log.setLevel(logging.DEBUG)

    log.warning("🚀 _run_sync started")
    log.warning(
        f"🚀 site={getattr(frappe.local, 'site', None)} "
        f"triggered_by={triggered_by}"
    )

    log.warning(f"🚀 cancel flag BEFORE clear value={_get_cancel_flag()!r}")

    _clear_cancel_flag()

    log.warning(f"🚀 cancel flag AFTER clear value={_get_cancel_flag()!r}")

    def pub(**kw):
        _emit(triggered_by, **kw)

    log.info("===== Vehicle sync started =====")

    try:
        client = GPSGateClient()

    except GPSGateAPIError as e:
        log.error(f"GPSGateClient init failed: {e.message}")
        frappe.log_error(
            title="Vehicle Sync - Client Error",
            message=str(e.message),
        )

        pub(
            current=0,
            total=0,
            status="error",
            label=str(e.message),
        )
        return

    log.info("Fetching all users from GPS Gate...")

    try:
        users = client.get_users()

    except Exception:
        tb = frappe.get_traceback()
        log.error(f"get_users failed:\n{tb}")
        frappe.log_error(
            title="Vehicle Sync - get_users Error",
            message=tb,
        )

        pub(
            current=0,
            total=0,
            status="error",
            label="Failed to fetch users",
        )
        return

    if _is_sync_cancelled():
        log.info("Sync cancelled before filtering users.")

        pub(
            current=0,
            total=0,
            status="cancelled",
            label="Cancelled",
            created=0,
            updated=0,
            errors=0,
        )
        _clear_cancel_flag()
        return

    log.info(f"Total users fetched: {len(users)}")

    try:
        device_type_id = _get_device_type_id()

    except Exception:
        tb = frappe.get_traceback()
        log.error(f"Device type lookup failed:\n{tb}")
        frappe.log_error(
            title="Vehicle Sync - Device Type Error",
            message=tb,
        )

        pub(
            current=0,
            total=0,
            status="error",
            label="Device user type not found",
        )
        return

    log.info(f"Device type ID to match: {device_type_id!r} (type={type(device_type_id).__name__})")
    if users:
        sample_ids = [u.get("userTemplateID") for u in users[:5]]
        log.info(f"Sample userTemplateID values (first 5): {sample_ids!r}")

    device_users = [
        u for u in users
        if cint(u.get("userTemplateID")) == device_type_id
    ]

    total = len(device_users)

    log.info(f"Device users to sync: {total}")

    pub(
        current=0,
        total=total,
        label="Starting…",
        status="running",
    )

    created = 0
    updated = 0
    errors = []

    for i, u in enumerate(device_users, 1):
        if _is_sync_cancelled():
            log.info("Sync cancelled by user before next vehicle.")

            pub(
                current=i - 1,
                total=total,
                status="cancelled",
                label="Cancelled",
                created=created,
                updated=updated,
                errors=len(errors),
            )
            return

        label = u.get("name") or str(u.get("description"))

        pub(
            current=i,
            total=total,
            label=label,
            status="running",
            created=created,
            updated=updated,
            errors=len(errors),
        )

        gps_user_id = u.get("id")

        log.info(f"[{i}/{total}] user_id={gps_user_id}")

        try:
            action = _sync_single_vehicle(u, client, log)

            if action == "cancelled":
                log.info("Sync cancelled by user during vehicle sync.")

                pub(
                    current=i - 1,
                    total=total,
                    status="cancelled",
                    label="Cancelled",
                    created=created,
                    updated=updated,
                    errors=len(errors),
                )
                return

            if action == "created":
                created += 1
            else:
                updated += 1

        except Exception:
            tb = frappe.get_traceback()
            errors.append(label)

            log.error(f"  FAILED {label}:\n{tb}")

            frappe.log_error(
                title=f"Vehicle Sync Error - user {gps_user_id}",
                message=tb,
            )

    pub(
        current=total,
        total=total,
        status="done",
        label="Done",
        created=created,
        updated=updated,
        errors=len(errors),
    )

    log.info(
        f"===== Done: created={created}, updated={updated}, errors={len(errors)} ====="
    )


@frappe.whitelist()
def sync_vehicles_from_gps_gate():
    """
    Enqueue the vehicle sync as a long background job.
    """
    if not frappe.db.exists("Vehicle Type", {"is_active": 1}):
        frappe.throw(
            _("Please add at least one active Vehicle Type before syncing vehicles.")
        )

    _clear_cancel_flag()

    frappe.enqueue(
        "gps_gate.apis.sync_vehicles._run_sync",
        queue="long",
        timeout=3600,
        job_id="gps_gate_vehicle_sync",
        deduplicate=True,
        triggered_by=frappe.session.user,
    )

    return {"status": "queued"}


@frappe.whitelist()
def cancel_vehicle_sync():
    log = frappe.logger("vehicle_sync", allow_site=True, file_count=5)
    log.setLevel(logging.DEBUG)

    log.warning("🛑 cancel_vehicle_sync called")
    log.warning(
        f"🛑 cancel request site={getattr(frappe.local, 'site', None)} "
        f"user={frappe.session.user}"
    )

    log.warning(f"🛑 cancel flag BEFORE set value={_get_cancel_flag()!r}")

    _set_cancel_flag("1")

    log.warning(f"🛑 cancel flag AFTER set value={_get_cancel_flag()!r}")

    frappe.publish_realtime(
        "vehicle_sync_progress",
        {
            "status": "cancelling",
            "label": "Cancel requested...",
        },
        user=frappe.session.user,
    )

    return {"status": "cancel_requested"}

@frappe.whitelist()
def bulk_set_vehicle_type(vehicles, vehicle_type):
    """
    Set custom_vehicle_type for a list of Vehicle names.
    """
    frappe.has_permission("Vehicle", "write", throw=True)

    if isinstance(vehicles, str):
        vehicles = json.loads(vehicles)

    if not vehicles:
        frappe.throw(_("No vehicles selected."))

    if not frappe.db.exists("Vehicle Type", vehicle_type):
        frappe.throw(_("Vehicle Type '{0}' does not exist.").format(vehicle_type))

    for name in vehicles:
        frappe.db.set_value(
            "Vehicle",
            name,
            "custom_vehicle_type",
            vehicle_type,
        )

    frappe.db.commit()

    return {"updated": len(vehicles)}