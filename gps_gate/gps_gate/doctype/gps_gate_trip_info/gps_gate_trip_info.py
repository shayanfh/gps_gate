# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, get_datetime


class GPSGateTripInfo(Document):

    def before_save(self):
        # Calculate duration from start/end times
        if self.start_time and self.end_time:
            try:
                delta = get_datetime(self.end_time) - get_datetime(self.start_time)
                self.duration = int(delta.total_seconds())
            except Exception:
                pass

        # Build map with LineString from start to end
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


@frappe.whitelist()
def sync_trips_for_date(gps_gate_user, date):
    """
    Fetch all trips for a GPS Gate user on a given date and sync to ERPNext.
    Creates new records; updates existing ones matched by track_info_id.

    Args:
        gps_gate_user: GPS Gate User document name
        date: Date string in YYYY-MM-DD format

    Returns:
        dict: Result with synced/updated counts and total
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError
    from gps_gate.apis.sync_user import sanitize_datetime

    gps_user = frappe.get_doc("GPS Gate User", gps_gate_user)
    gps_user_id = gps_user.gps_gate_id or int(gps_user.name)

    try:
        client = get_gps_gate_client()
        trips = client.get_user_trip_infos(gps_user_id, date)
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(title="Trip Info Sync Error", message=frappe.get_traceback())
        frappe.throw(_("Failed to fetch trips: {0}").format(str(e)))

    if not trips:
        return {"status": "success", "synced": 0, "updated": 0, "total": 0,
                "message": _("No trips found for this date")}

    synced = 0
    updated = 0
    errors = []

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
                doc.gps_gate_user = gps_gate_user
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

        except Exception:
            errors.append(str(trip.get("trackInfoId")))
            frappe.log_error(title="Trip Info Save Error", message=frappe.get_traceback())

    frappe.db.commit()

    total = len(trips)
    result = {
        "status": "success" if not errors else "partial",
        "synced": synced,
        "updated": updated,
        "total": total,
        "message": _("Created {0}, updated {1} of {2} trips").format(synced, updated, total)
    }
    if errors:
        result["errors"] = errors[:10]
    return result
