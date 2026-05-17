# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import hashlib
import json
from datetime import date as dt, timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

INSERT_CHUNK = 50   # commit every N inserts — small enough to avoid lock timeout


class GPSGateTrackPoint(Document):

    def autoname(self):
        self.name = make_track_point_name({
            "gps_gate_user": self.gps_gate_user,
            "track_time": self.track_time,
        })

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


# ── internal helpers ────────────────────────────────────────────────────────────

def make_track_point_name(record):
    raw = "|".join([
        str(record.get("gps_gate_user") or ""),
        str(record.get("track_time") or ""),
    ])
    return "GPS-TP-" + hashlib.sha1(raw.encode()).hexdigest()[:24]


def _build_map_location(lat, lng):
    if not lat or not lng:
        return None
    return json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": {
            "type": "Point", "coordinates": [float(lng), float(lat)]
        }}]
    })


def _sync_user_date_tracks(gps_gate_user_name, gps_user_id, date_str, client):
    """
    Sync track points for ONE user on ONE date.

    Key optimisations to avoid Lock wait timeout:
    1. Pre-fetch ALL existing timestamps in a single query (no per-row SELECT inside loop)
    2. Build the full insert list in memory (no DB access in the loop at all)
    3. Insert in small chunks of INSERT_CHUNK and commit after each chunk
    4. Skip before_save/after_insert hooks via flags (map_location built inline)
    """
    from gps_gate.apis.sync_user import sanitize_datetime

    try:
        tracks = client.get_user_tracks(gps_user_id, date_str)
    except Exception:
        frappe.log_error(title="Track Fetch Error", message=frappe.get_traceback())
        return {"synced": 0, "skipped": 0, "total": 0, "errors": [date_str]}

    if not tracks:
        return {"synced": 0, "skipped": 0, "total": 0, "errors": []}

    # ── Step 1: one bulk SELECT to know which timestamps already exist ──────────
    rows = frappe.db.sql(
        "SELECT track_time FROM `tabGPS Gate Track Point` WHERE gps_gate_user = %s",
        (gps_gate_user_name,),
        as_list=True
    )
    existing_set = {str(r[0]) for r in rows if r[0]}
    frappe.db.commit()   # release any implicit read lock before we start inserting

    # ── Step 2: build insert list in memory ────────────────────────────────────
    synced_at = now()
    to_insert = []
    skipped = 0
    errors = []

    for t in tracks:
        try:
            utc = sanitize_datetime(t.get("utc"))
            if not utc:
                continue
            if str(utc) in existing_set:
                skipped += 1
                continue

            pos = t.get("position") or {}
            vel = t.get("velocity") or {}
            lat = pos.get("latitude")
            lng = pos.get("longitude")

            to_insert.append({
                "gps_gate_user": gps_gate_user_name,
                "track_time": utc,
                "track_info_id": t.get("trackInfoId"),
                "latitude": lat,
                "longitude": lng,
                "altitude": pos.get("altitude"),
                "speed": vel.get("groundSpeed"),
                "heading": vel.get("heading"),
                "is_valid": 1 if t.get("valid") else 0,
                "server_utc": sanitize_datetime(t.get("serverUtc")),
                "raw_response": frappe.as_json(t),
                "last_synced_on": synced_at,
                "map_location": _build_map_location(lat, lng),
            })
        except Exception:
            errors.append(str(t.get("utc")))
            frappe.log_error(title="Track Point Prepare Error", message=frappe.get_traceback())

    # ── Step 3: insert in small chunks, commit after each ─────────────────────
    synced = 0
    for i in range(0, len(to_insert), INSERT_CHUNK):
        chunk = to_insert[i:i + INSERT_CHUNK]
        for record in chunk:
            try:
                doc = frappe.new_doc("GPS Gate Track Point")
                doc.update(record)
                doc.name = make_track_point_name(record)  # bypass tabSeries lock
                doc.flags.ignore_permissions = True
                doc.flags.ignore_links = True
                doc.flags.ignore_mandatory = True
                doc.insert()
                synced += 1
            except frappe.DuplicateEntryError:
                frappe.db.rollback()
                skipped += 1
            except Exception:
                frappe.db.rollback()
                errors.append(str(record.get("track_time")))
                frappe.log_error(title="Track Point Insert Error", message=frappe.get_traceback())
        frappe.db.commit()   # release locks after every INSERT_CHUNK rows

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
