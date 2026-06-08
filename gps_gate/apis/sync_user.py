# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

"""
GPS Gate User Sync Module

This module provides functionality to sync users from GPS Gate to ERPNext.
Uses the centralized GPS Gate API client for all API interactions.
"""

import frappe
from frappe.utils import now
from frappe import _

from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError


def sanitize_datetime(value):
    """
    Converts GPS Gate datetime to MySQL-safe naive datetime.
    - Removes timezone (+00:00)
    - Skips dummy dates like 0001-01-01
    
    Args:
        value: Datetime string from GPS Gate API
        
    Returns:
        datetime or None: Sanitized datetime object
    """
    if not value:
        return None

    value = str(value)

    # GPS Gate dummy datetime
    if value.startswith("0001-01-01"):
        return None

    try:
        dt = frappe.utils.get_datetime(value)

        # IMPORTANT: remove timezone info
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)

        return dt
    except Exception:
        return None


@frappe.whitelist(allow_guest=False)
def sync_gps_gate_users():
    """
    Fetch users from GPS Gate and sync them into ERPNext.
    Creates new records for users that don't exist, updates existing ones.
    
    Returns:
        dict: Sync result with status and count of synced records
    """
    try:
        client = get_gps_gate_client()
        users = client.get_users()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(
            title="GPS Gate User Sync Failed",
            message=frappe.get_traceback()
        )
        frappe.throw(_("Unable to connect to GPS Gate API: {0}").format(str(e)))

    synced = 0
    errors = []

    for u in users:
        try:
            gps_user_id = u.get("id")
            if not gps_user_id:
                continue

            # Check existing record
            doc_name = frappe.db.get_value(
                "GPS Gate User",
                {"gps_gate_id": gps_user_id},
                "name"
            )

            if doc_name:
                doc = frappe.get_doc("GPS Gate User", doc_name)
            else:
                doc = frappe.new_doc("GPS Gate User")
            
            # Set flag to skip GPS Gate sync (we're syncing FROM GPS Gate)
            doc._skip_gps_gate_sync = True

            # Basic User Info
            doc.gps_gate_id = gps_user_id
            # doc.gps_gate_id = gps_user_id
            doc.username = u.get("username")
            doc.first_name = u.get("name")
            doc.last_name = u.get("surname")
            doc.full_name = f"{u.get('name', '')} {u.get('surname', '')}".strip()
            doc.email = u.get("email")
            doc.driver_id = u.get("driverID")
            doc.user_type_id = u.get("userTemplateID")
            doc.orignal_application_id = u.get("originalApplicationID")
            doc.description = u.get("description")

            # Tracking / Location
            track = u.get("trackPoint") or {}
            position = track.get("position") or {}

            doc.last_latitude = position.get("latitude")
            doc.last_longitude = position.get("longitude")
            doc.last_altitude = position.get("altitude")
            doc.is_location_valid = track.get("valid")

            doc.last_utc_time = sanitize_datetime(track.get("utc"))
            doc.device_activity = sanitize_datetime(u.get("deviceActivity"))
            doc.calculated_speed = u.get("calculatedSpeed")
            doc.last_transport = u.get("lastTransport")

            # Meta / Sync Info
            doc.raw_response = frappe.as_json(u)
            doc.last_synced_on = now()
            doc.is_created_on_gps_gate = 1
            doc.sync_status = "Success"
            doc.sync_error = ""

            # Devices (Child Table)
            doc.set("gps_gate_device", [])

            for d in u.get("devices", []):
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

            # Save document
            doc.save(ignore_permissions=True)
            synced += 1
            
        except Exception as e:
            error_msg = f"Error syncing user {u.get('username', u.get('id'))}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(
                title="GPS Gate User Sync Error",
                message=frappe.get_traceback()
            )

    frappe.db.commit()

    result = {
        "status": "success" if not errors else "partial",
        "synced_records": synced,
        "total_users": len(users)
    }
    
    if errors:
        result["errors"] = errors
        result["error_count"] = len(errors)
    
    return result


@frappe.whitelist(allow_guest=False)
def get_gps_gate_user_types():
    """
    Fetch available user types from GPS Gate.
    Useful for populating dropdowns or validating user type IDs.
    
    Returns:
        list: List of user type dictionaries
    """
    try:
        client = get_gps_gate_client()
        return client.get_user_types()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(
            title="GPS Gate User Types Fetch Failed",
            message=frappe.get_traceback()
        )
        frappe.throw(_("Unable to fetch user types from GPS Gate: {0}").format(str(e)))




@frappe.whitelist()
def get_gps_gate_user_types1():
    """
    Sync GPS Gate User Types from GPS Gate to ERPNext.
    Creates new records for user types that don't exist, updates existing ones.
    
    Returns:
        dict: Sync result with created, updated, and skipped counts
    """
    try:
        client = get_gps_gate_client()
        user_types = client.get_user_types()

        created = 0
        updated = 0
        errors = []

        for ut in user_types:
            try:
                gps_id = str(ut.get("id"))
                name = ut.get("name") or ut.get("displayName") or f"Type {gps_id}"

                if not gps_id:
                    continue

                # Check if already exists by user_type_id
                existing_name = frappe.db.get_value(
                    "GPS User Types",
                    {"user_type_id": gps_id},
                    "name"
                )

                # Fallback: if not found by ID, search by user_type_name and update ID
                if not existing_name:
                    existing_name = frappe.db.get_value(
                        "GPS User Types",
                        {"user_type_name": name},
                        "name"
                    )
                    if existing_name:
                        # Rename doc to new ID (autoname=field:user_type_id)
                        frappe.rename_doc("GPS User Types", existing_name, gps_id, ignore_permissions=True)
                        existing_name = gps_id

                if existing_name:
                    # Update existing record
                    doc = frappe.get_doc("GPS User Types", existing_name)
                    doc.user_type_id = gps_id
                    doc.user_type_name = name
                    doc.description = ut.get("description") or ""
                    doc.is_synced = 1
                    doc.sync_status = "Success"
                    doc.last_synced_on = frappe.utils.now()
                    doc.raw_response = frappe.as_json(ut)
                    doc.save(ignore_permissions=True)
                    updated += 1
                else:
                    # Create new record
                    doc = frappe.get_doc({
                        "doctype": "GPS User Types",
                        "user_type_id": gps_id,
                        "user_type_name": name,
                        "description": ut.get("description") or "",
                        "is_synced": 1,
                        "sync_status": "Success",
                        "last_synced_on": frappe.utils.now(),
                        "raw_response": frappe.as_json(ut)
                    })
                    doc.insert(ignore_permissions=True)
                    created += 1
                    
            except Exception as e:
                error_msg = f"Error syncing user type {ut.get('name', ut.get('id'))}: {str(e)}"
                errors.append(error_msg)
                frappe.log_error(
                    title="GPS Gate User Type Sync Error",
                    message=frappe.get_traceback()
                )

        frappe.db.commit()

        result = {
            "status": "success" if not errors else "partial",
            "created": created,
            "updated": updated,
            "total": len(user_types)
        }
        
        if errors:
            result["errors"] = errors
            result["error_count"] = len(errors)

        return result

    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception:
        frappe.log_error(
            title="GPS Gate User Types Sync Failed",
            message=frappe.get_traceback()
        )
        frappe.throw(_("Unable to sync user types from GPS Gate"))

