# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now
import json
from gps_gate.gps_gate_api import GPSGateClient, GPSGateAPIError, get_gps_gate_client


class GPSGateUser(Document):
    """GPS Gate User Document Controller"""
    
    def _handle_sync_error(self, error_message, operation="sync"):
        """
        Handle and record sync errors.
        
        Args:
            error_message: The error message to record
            operation: The operation that failed (create, update, delete)
        """
        try:
            # Use db_set to avoid triggering hooks
            frappe.db.set_value("GPS Gate User", self.name, {
                "sync_status": "Failed",
                "sync_error": f"{operation.upper()} Error: {error_message}"
            }, update_modified=False)
            
            # Update instance attributes
            self.sync_status = "Failed"
            self.sync_error = f"{operation.upper()} Error: {error_message}"
        except Exception:
            # Ignore errors when updating error status
            pass
    # GPS Gate User ka before_save hook


    def before_save(self):
        if self.last_latitude and self.last_longitude:
            self.map_location = json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            float(self.last_longitude),  # GeoJSON: lng first
                            float(self.last_latitude)
                        ]
                    }
                }]
            })

@frappe.whitelist()
def fetch_user_from_gps_gate(docname):
    """
    Fetch the latest user data from GPS Gate and update the local record.
    
    Args:
        docname: Name of the GPS Gate User document
        
    Returns:
        dict: Result of the fetch operation
    """
    doc = frappe.get_doc("GPS Gate User", docname)
    
    if not doc.gps_gate_id:
        frappe.throw(_("This user does not have a GPS Gate User ID. Cannot fetch data."))
    
    try:
        client = get_gps_gate_client()
        user_data = client.get_user(doc.gps_gate_id)
        
        if not user_data:
            frappe.throw(_("User not found on GPS Gate"))
        
        # Update local record with GPS Gate data
        _update_doc_from_gps_gate_data(doc, user_data)
        doc.last_synced_on = now()
        doc.sync_status = "Success"
        doc.sync_error = ""
        doc._skip_gps_gate_sync = True
        doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        return {"status": "success", "message": _("User data fetched from GPS Gate")}
        
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(title="GPS Gate User Fetch Error", message=frappe.get_traceback())
        frappe.throw(_("Failed to fetch user from GPS Gate: {0}").format(str(e)))


def _update_doc_from_gps_gate_data(doc, data):
    """
    Update a GPS Gate User document with data from the GPS Gate API.
    
    Args:
        doc: GPS Gate User document
        data: User data dictionary from GPS Gate API
    """
    from gps_gate.apis.sync_user import sanitize_datetime
    
    doc.user_id = data.get("id")
    doc.username = data.get("username")
    doc.first_name = data.get("name")
    doc.last_name = data.get("surname")
    doc.full_name = f"{data.get('name', '')} {data.get('surname', '')}".strip()
    doc.email = data.get("email")
    doc.driver_id = data.get("driverID")
    doc.user_template_id = data.get("userTemplateID")
    doc.orignal_application_id = data.get("originalApplicationID")
    doc.description = data.get("description")
    
    # Tracking / Location
    track = data.get("trackPoint") or {}
    position = track.get("position") or {}
    
    doc.last_latitude = position.get("latitude")
    doc.last_longitude = position.get("longitude")
    doc.last_altitude = position.get("altitude")
    doc.is_location_valid = track.get("valid")
    
    doc.last_utc_time = sanitize_datetime(track.get("utc"))
    doc.device_activity = sanitize_datetime(data.get("deviceActivity"))
    doc.calculated_speed = data.get("calculatedSpeed")
    doc.last_transport = data.get("lastTransport")
    
    # Raw response
    doc.raw_response = frappe.as_json(data)
    
    # Mark as created on GPS Gate
    doc.is_created_on_gps_gate = 1
    doc.gps_gate_id = data.get("id")
    
    # Devices
    doc.set("gps_gate_device", [])
    for d in data.get("devices", []):
        doc.append("gps_gate_device", {
            "device_id": d.get("id"),
            "device_name": d.get("name"),
            "imei": d.get("imei"),
            "protocol_id": d.get("protocolID"),
            "protocol_version_id": d.get("protocolVersionID"),
            "msisdn": (d.get("msisdn") or {}).get("raw"),
            "hide_position": d.get("hidePosition"),
            "owner_id": d.get("ownerID"),
            "created_on": sanitize_datetime(d.get("created"))
        })
