# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
from datetime import date as dt, timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

CHUNK_SIZE = 1000


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


# ── internal helper ─────────────────────────────────────────────────────────────

def _sync_user_date_tracks(gps_gate_user_name, gps_user_id, date_str, client):
    """
    Sync track points for ONE user on ONE date.
    Saves in chunks of CHUNK_SIZE to prevent timeouts.
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
    chunk_count = 0

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
            chunk_count += 1

            # commit every CHUNK_SIZE inserts to release DB locks
            if chunk_count >= CHUNK_SIZE:
                frappe.db.commit()
                chunk_count = 0

        except Exception:
            errors.append(str(t.get("utc")))
            frappe.log_error(title="Track Point Insert Error", message=frappe.get_traceback())

    # final commit for the remaining records
    if chunk_count > 0:
        frappe.db.commit()

    return {"synced": synced, "skipped": skipped, "total": len(tracks), "errors": errors}


# ── background worker ────────────────────────────────────────────────────────────

def _run_tracks_batch_job(from_date, to_date, gps_gate_user=""):
    """
    Background worker: sync track points across users and date range.
    Enqueued by sync_tracks_batch — never call directly from the browser.
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    try:
        client = get_gps_gate_client()
    except GPSGateAPIError as e:
        frappe.log_error(title="Batch Track Sync — Client Error", message=str(e.message))
        return

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
        return

    start = dt.fromisoformat(from_date)
    end = dt.fromisoformat(to_date)
    total_synced = total_skipped = 0

    current = start
    while current <= end:
        date_str = str(current)
        for u in users:
            try:
                r = _sync_user_date_tracks(u["name"], u["gps_gate_id"], date_str, client)
                total_synced += r["synced"]
                total_skipped += r["skipped"]
            except Exception:
                frappe.log_error(
                    title="Batch Track Sync Error",
                    message=f"User: {u['name']} | Date: {date_str}\n{frappe.get_traceback()}"
                )
        current += timedelta(days=1)

    days = (end - start).days + 1
    frappe.log_error(
        title="Batch Track Sync — Done",
        message=f"Synced {total_synced}, skipped {total_skipped} across {len(users)} user(s) over {days} day(s)"
    )


# ── whitelisted endpoints ────────────────────────────────────────────────────────

@frappe.whitelist()
def sync_tracks_for_date(gps_gate_user, date):
    """
    Sync track points for a SINGLE user on a single date.
    Runs synchronously — called from the form view.
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    gps_user = frappe.get_doc("GPS Gate User", gps_gate_user)
    gps_user_id = gps_user.gps_gate_id or int(gps_user.name)

    try:
        client = get_gps_gate_client()
        result = _sync_user_date_tracks(gps_gate_user, gps_user_id, date, client)
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
        return  # unreachable — throw always raises

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
    Queue a background job to sync track points across a date range.
    Returns immediately — processing happens in the background.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD). Defaults to from_date
        gps_gate_user: GPS Gate User doc name, or None/empty for all users
    """
    to_date = to_date or from_date
    gps_gate_user = gps_gate_user or ""

    days = (dt.fromisoformat(to_date) - dt.fromisoformat(from_date)).days + 1

    frappe.enqueue(
        "gps_gate.gps_gate.doctype.gps_gate_track_point.gps_gate_track_point._run_tracks_batch_job",
        queue="long",
        timeout=7200,
        from_date=from_date,
        to_date=to_date,
        gps_gate_user=gps_gate_user
    )

    user_label = gps_gate_user if gps_gate_user else _("all users")
    return {
        "status": "queued",
        "message": _("Sync started in background for {0} over {1} day(s). Refresh the list in a few minutes.").format(
            user_label, days
        )
    }
