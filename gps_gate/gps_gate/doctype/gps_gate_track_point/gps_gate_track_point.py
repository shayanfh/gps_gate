# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
from datetime import date as dt, timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class GPSGateTrackPoint(Document):

    def before_save(self):
        if self.latitude and self.longitude:
            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(self.longitude), float(self.latitude)]
                    }
                }]
            })


# ── internal helper ────────────────────────────────────────────────────────────

def _sync_user_date_tracks(gps_gate_user_name, gps_user_id, date_str, client):
    """
    Sync track points for ONE user on ONE date.
    Skips records that already exist (dedup by user + utc timestamp).
    Returns dict: {synced, skipped, total, errors}
    """
    from gps_gate.apis.sync_user import sanitize_datetime

    try:
        tracks = client.get_user_tracks(gps_user_id, date_str)
    except Exception:
        frappe.log_error(title="Track Fetch Error", message=frappe.get_traceback())
        return {"synced": 0, "skipped": 0, "total": 0, "errors": [date_str]}

    if not tracks:
        return {"synced": 0, "skipped": 0, "total": 0, "errors": []}

    synced = skipped = 0
    errors = []

    for t in tracks:
        try:
            utc = sanitize_datetime(t.get("utc"))
            if not utc:
                continue

            existing = frappe.db.get_value(
                "GPS Gate Track Point",
                {"gps_gate_user": gps_gate_user_name, "track_time": utc},
                "name"
            )
            if existing:
                skipped += 1
                continue

            pos = t.get("position") or {}
            vel = t.get("velocity") or {}

            doc = frappe.new_doc("GPS Gate Track Point")
            doc.gps_gate_user = gps_gate_user_name
            doc.track_time = utc
            doc.track_info_id = t.get("trackInfoId")
            doc.latitude = pos.get("latitude")
            doc.longitude = pos.get("longitude")
            doc.altitude = pos.get("altitude")
            doc.speed = vel.get("groundSpeed")
            doc.heading = vel.get("heading")
            doc.is_valid = 1 if t.get("valid") else 0
            doc.server_utc = sanitize_datetime(t.get("serverUtc"))
            doc.raw_response = frappe.as_json(t)
            doc.last_synced_on = now()
            doc.insert(ignore_permissions=True)
            synced += 1

        except Exception:
            errors.append(str(t.get("utc")))
            frappe.log_error(title="Track Point Insert Error", message=frappe.get_traceback())

    return {"synced": synced, "skipped": skipped, "total": len(tracks), "errors": errors}


# ── whitelisted endpoints ───────────────────────────────────────────────────────

@frappe.whitelist()
def sync_tracks_for_date(gps_gate_user, date):
    """
    Sync track points for a SINGLE GPS Gate user on a single date.
    Called from the form view.
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    gps_user = frappe.get_doc("GPS Gate User", gps_gate_user)
    gps_user_id = gps_user.gps_gate_id or int(gps_user.name)

    try:
        client = get_gps_gate_client()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))

    result = _sync_user_date_tracks(gps_gate_user, gps_user_id, date, client)
    frappe.db.commit()

    return {
        "status": "success" if not result["errors"] else "partial",
        **result,
        "message": _("Synced {0} of {1} track points ({2} already existed)").format(
            result["synced"], result["total"], result["skipped"]
        )
    }


@frappe.whitelist()
def sync_tracks_batch(from_date, to_date=None, gps_gate_user=None):
    """
    Sync track points across a date range.
    If gps_gate_user is empty/None → syncs ALL GPS Gate Users.
    Called from the list view.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD). Defaults to from_date (single day)
        gps_gate_user: GPS Gate User doc name, or None/empty for all users
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    try:
        client = get_gps_gate_client()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))

    # Resolve user list
    if gps_gate_user:
        gps_user_doc = frappe.get_doc("GPS Gate User", gps_gate_user)
        users = [{"name": gps_user_doc.name,
                  "gps_gate_id": gps_user_doc.gps_gate_id or int(gps_user_doc.name)}]
    else:
        rows = frappe.get_all(
            "GPS Gate User",
            filters={"gps_gate_id": ["is", "set"]},
            fields=["name", "gps_gate_id"]
        )
        users = [{"name": r.name, "gps_gate_id": r.gps_gate_id} for r in rows]

    if not users:
        return {"status": "success", "message": _("No GPS Gate Users found"), "synced": 0}

    # Build date range
    start = dt.fromisoformat(from_date)
    end = dt.fromisoformat(to_date) if to_date else start

    total_synced = total_skipped = total_points = 0
    user_errors = []

    current = start
    while current <= end:
        date_str = str(current)
        for u in users:
            try:
                r = _sync_user_date_tracks(u["name"], u["gps_gate_id"], date_str, client)
                total_synced += r["synced"]
                total_skipped += r["skipped"]
                total_points += r["total"]
                if r["errors"]:
                    user_errors.append(f'{u["name"]} / {date_str}')
            except Exception:
                user_errors.append(f'{u["name"]} / {date_str}')
                frappe.log_error(title="Batch Track Sync Error", message=frappe.get_traceback())
        current += timedelta(days=1)

    frappe.db.commit()

    days = (end - start).days + 1
    return {
        "status": "success" if not user_errors else "partial",
        "synced": total_synced,
        "skipped": total_skipped,
        "total": total_points,
        "users": len(users),
        "days": days,
        "message": _("Synced {0} track points across {1} user(s) over {2} day(s)").format(
            total_synced, len(users), days
        )
    }
