# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
from datetime import date as dt, timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, get_datetime

CHUNK_SIZE = 1000


class GPSGateTripInfo(Document):

    def before_save(self):
        if self.start_time and self.end_time:
            try:
                delta = get_datetime(self.end_time) - get_datetime(self.start_time)
                self.duration = int(delta.total_seconds())
            except Exception:
                pass

        has_start = self.start_latitude and self.start_longitude
        has_end = self.end_latitude and self.end_longitude

        if has_start and has_end:
            slat, slng = float(self.start_latitude), float(self.start_longitude)
            elat, elng = float(self.end_latitude), float(self.end_longitude)
            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"point_type": "start"},
                        "geometry": {"type": "Point", "coordinates": [slng, slat]}
                    },
                    {
                        "type": "Feature",
                        "properties": {"point_type": "end"},
                        "geometry": {"type": "Point", "coordinates": [elng, elat]}
                    },
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[slng, slat], [elng, elat]]
                        }
                    }
                ]
            })
        elif has_start:
            slat, slng = float(self.start_latitude), float(self.start_longitude)
            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {"point_type": "start"},
                    "geometry": {"type": "Point", "coordinates": [slng, slat]}
                }]
            })


# ── internal helper ─────────────────────────────────────────────────────────────

def _sync_user_date_trips(gps_gate_user_name, gps_user_id, date_str, client):
    """
    Sync trips for ONE user on ONE date.
    Saves in chunks of CHUNK_SIZE to prevent timeouts.
    Returns dict: {synced, updated, total, errors}
    """
    from gps_gate.apis.sync_user import sanitize_datetime

    try:
        trips = client.get_user_trip_infos(gps_user_id, date_str)
    except Exception:
        frappe.log_error(title="Trip Fetch Error", message=frappe.get_traceback())
        return {"synced": 0, "updated": 0, "total": 0, "errors": [date_str]}

    if not trips:
        return {"synced": 0, "updated": 0, "total": 0, "errors": []}

    synced = updated = 0
    errors = []
    chunk_count = 0

    for trip in trips:
        try:
            trip_id = trip.get("trackInfoId")
            if not trip_id:
                continue

            start_tp = trip.get("startTrackPoint") or {}
            end_tp = trip.get("endTrackPoint") or {}
            start_pos = start_tp.get("position") or {}
            end_pos = end_tp.get("position") or {}
            start_vel = start_tp.get("velocity") or {}
            end_vel = end_tp.get("velocity") or {}

            existing = frappe.db.get_value(
                "GPS Gate Trip Info", {"track_info_id": trip_id}, "name"
            )

            if existing:
                doc = frappe.get_doc("GPS Gate Trip Info", existing)
                updated += 1
            else:
                doc = frappe.new_doc("GPS Gate Trip Info")
                doc.gps_gate_user = gps_gate_user_name
                doc.track_info_id = trip_id
                synced += 1

            doc.is_idle = 1 if trip.get("isIdle") else 0
            doc.distance = trip.get("totalDistance")
            doc.start_time = sanitize_datetime(start_tp.get("utc"))
            doc.end_time = sanitize_datetime(end_tp.get("utc"))
            doc.start_latitude = start_pos.get("latitude")
            doc.start_longitude = start_pos.get("longitude")
            doc.start_altitude = start_pos.get("altitude")
            doc.start_speed = start_vel.get("groundSpeed")
            doc.start_heading = start_vel.get("heading")
            doc.end_latitude = end_pos.get("latitude")
            doc.end_longitude = end_pos.get("longitude")
            doc.end_altitude = end_pos.get("altitude")
            doc.end_speed = end_vel.get("groundSpeed")
            doc.end_heading = end_vel.get("heading")
            doc.raw_response = frappe.as_json(trip)
            doc.last_synced_on = now()
            doc.save(ignore_permissions=True)
            chunk_count += 1

            # commit every CHUNK_SIZE saves to release DB locks
            if chunk_count >= CHUNK_SIZE:
                frappe.db.commit()
                chunk_count = 0

        except Exception:
            errors.append(str(trip.get("trackInfoId")))
            frappe.log_error(title="Trip Info Save Error", message=frappe.get_traceback())

    if chunk_count > 0:
        frappe.db.commit()

    return {"synced": synced, "updated": updated, "total": len(trips), "errors": errors}


# ── background worker ────────────────────────────────────────────────────────────

def _run_trips_batch_job(from_date, to_date, gps_gate_user=""):
    """
    Background worker: sync trips across users and date range.
    Enqueued by sync_trips_batch — never call directly from the browser.
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    try:
        client = get_gps_gate_client()
    except GPSGateAPIError as e:
        frappe.log_error(title="Batch Trip Sync — Client Error", message=str(e.message))
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
    total_synced = total_updated = 0

    current = start
    while current <= end:
        date_str = str(current)
        for u in users:
            try:
                r = _sync_user_date_trips(u["name"], u["gps_gate_id"], date_str, client)
                total_synced += r["synced"]
                total_updated += r["updated"]
            except Exception:
                frappe.log_error(
                    title="Batch Trip Sync Error",
                    message=f"User: {u['name']} | Date: {date_str}\n{frappe.get_traceback()}"
                )
        current += timedelta(days=1)

    days = (end - start).days + 1
    frappe.log_error(
        title="Batch Trip Sync — Done",
        message=f"Created {total_synced}, updated {total_updated} across {len(users)} user(s) over {days} day(s)"
    )


# ── whitelisted endpoints ────────────────────────────────────────────────────────

@frappe.whitelist()
def sync_trips_for_date(gps_gate_user, date):
    """
    Sync trips for a SINGLE user on a single date.
    Runs synchronously — called from the form view.
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    gps_user = frappe.get_doc("GPS Gate User", gps_gate_user)
    gps_user_id = gps_user.gps_gate_id or int(gps_user.name)

    try:
        client = get_gps_gate_client()
        result = _sync_user_date_trips(gps_gate_user, gps_user_id, date, client)
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
        return  # unreachable — throw always raises

    return {
        "status": "success" if not result["errors"] else "partial",
        **result,
        "message": _("Created {0}, updated {1} of {2} trips").format(
            result["synced"], result["updated"], result["total"]
        )
    }


@frappe.whitelist()
def sync_trips_batch(from_date, to_date=None, gps_gate_user=None):
    """
    Queue a background job to sync trips across a date range.
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
        "gps_gate.gps_gate.doctype.gps_gate_trip_info.gps_gate_trip_info._run_trips_batch_job",
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
