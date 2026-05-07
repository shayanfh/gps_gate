# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
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


@frappe.whitelist()
def sync_tracks_for_date(gps_gate_user, date):
    """
    Fetch all track points for a GPS Gate user on a given date and sync to ERPNext.
    Creates new records; skips existing ones (matched by user + utc timestamp).

    Args:
        gps_gate_user: GPS Gate User document name
        date: Date string in YYYY-MM-DD format

    Returns:
        dict: Result with synced count and total
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError
    from gps_gate.apis.sync_user import sanitize_datetime

    gps_user = frappe.get_doc("GPS Gate User", gps_gate_user)
    gps_user_id = gps_user.gps_gate_id or int(gps_user.name)

    try:
        client = get_gps_gate_client()
        tracks = client.get_user_tracks(gps_user_id, date)
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(title="Track Point Sync Error", message=frappe.get_traceback())
        frappe.throw(_("Failed to fetch tracks: {0}").format(str(e)))

    if not tracks:
        return {"status": "success", "synced": 0, "total": 0,
                "message": _("No track points found for this date")}

    synced = 0
    skipped = 0
    errors = []

    for t in tracks:
        try:
            utc = sanitize_datetime(t.get("utc"))
            if not utc:
                continue

            # Deduplicate by user + GPS UTC timestamp
            existing = frappe.db.get_value(
                "GPS Gate Track Point",
                {"gps_gate_user": gps_gate_user, "track_time": utc},
                "name"
            )
            if existing:
                skipped += 1
                continue

            pos = t.get("position") or {}
            vel = t.get("velocity") or {}

            doc = frappe.new_doc("GPS Gate Track Point")
            doc.gps_gate_user = gps_gate_user
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

    frappe.db.commit()

    result = {
        "status": "success" if not errors else "partial",
        "synced": synced,
        "skipped": skipped,
        "total": len(tracks),
        "message": _("Synced {0} of {1} track points ({2} already existed)").format(
            synced, len(tracks), skipped
        )
    }
    if errors:
        result["errors"] = errors[:10]
    return result
