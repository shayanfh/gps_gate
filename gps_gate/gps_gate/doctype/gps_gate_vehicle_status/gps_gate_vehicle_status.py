# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class GPSGateVehicleStatus(Document):

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
def sync_vehicle_status(docname):
    """
    Fetch the latest status for this vehicle from GPS Gate and update the record.

    Args:
        docname: Name of the GPS Gate Vehicle Status document (= GPS Gate User name)

    Returns:
        dict: Result with status and message
    """
    from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError

    doc = frappe.get_doc("GPS Gate Vehicle Status", docname)
    gps_user = frappe.get_doc("GPS Gate User", doc.gps_gate_user)
    gps_user_id = gps_user.gps_gate_id or int(gps_user.name)

    try:
        client = get_gps_gate_client()
        data = client.get_user_status(gps_user_id)
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(title="Vehicle Status Sync Error", message=frappe.get_traceback())
        frappe.throw(_("Failed to fetch vehicle status: {0}").format(str(e)))

    if not data:
        frappe.throw(_("No data returned from GPS Gate for this vehicle."))

    _update_doc_from_data(doc, data)
    doc.last_synced_on = now()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": _("Vehicle status synced from GPS Gate")}


def _update_doc_from_data(doc, data):
    from gps_gate.apis.sync_user import sanitize_datetime

    pos = data.get("position") or {}
    vel = data.get("velocity") or {}
    utc_raw = data.get("utc") or ""

    doc.user_name = data.get("name")
    doc.username = data.get("username")
    doc.latitude = pos.get("latitude")
    doc.longitude = pos.get("longitude")
    doc.altitude = pos.get("altitude")
    doc.speed = vel.get("groundSpeed")
    doc.heading = vel.get("heading")
    doc.device_time = sanitize_datetime(utc_raw)
    doc.server_time = sanitize_datetime(data.get("deviceActivity"))
    doc.online_status = "Offline" if utc_raw.startswith("0001-01-01") else "Online"
    doc.variables_data = frappe.as_json(data.get("variables") or [])
    doc.raw_response = frappe.as_json(data)
