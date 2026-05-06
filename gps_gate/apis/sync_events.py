# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

"""
GPS Gate Events Sync Module

This module provides functionality to sync event rules and events from GPS Gate to ERPNext.
Uses the centralized GPS Gate API client for all API interactions.
"""

import frappe
from frappe.utils import now
from frappe.utils import getdate
from datetime import timedelta
from frappe.utils import now, get_datetime, format_datetime
from frappe import _
from frappe.utils import add_days, today
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

        # Remove timezone info for MySQL compatibility
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)

        return dt
    except Exception:
        return None


def format_date_for_api(date_value):
    """
    Format a date for GPS Gate API (YYYY-MM-DD format).
    
    Args:
        date_value: date object, datetime object, or string
        
    Returns:
        str: Date formatted as YYYY-MM-DD
    """
    if isinstance(date_value, str):
        # If already in correct format, return as is
        if len(date_value) == 10 and date_value[4] == '-' and date_value[7] == '-':
            return date_value
        # Otherwise parse and format
        date_value = get_datetime(date_value)
    
    return date_value.strftime("%Y-%m-%d")

@frappe.whitelist(allow_guest=False)
def sync_gps_gate_event_rules():
    """
    Fetch event rules from GPS Gate and sync them into ERPNext.
    Creates new records for event rules that don't exist, updates existing ones.
    
    Returns:
        dict: Sync result with status and count of synced records
    """
    try:
        client = get_gps_gate_client()
        event_rules = client.get_event_rules()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(
            title="GPS Gate Event Rules Sync Failed",
            message=frappe.get_traceback()
        )
        frappe.throw(_("Unable to connect to GPS Gate API: {0}").format(str(e)))

    if not event_rules:
        return {
            "status": "success",
            "synced_records": 0,
            "message": _("No event rules found in GPS Gate")
        }

    synced = 0
    errors = []

    for rule in event_rules:
        try:
            rule_id = rule.get("id")
            if not rule_id:
                continue

            # Check existing record
            doc_name = frappe.db.get_value(
                "GPS Gate Event Rule",
                {"event_rule_id": rule_id},
                "name"
            )

            if doc_name:
                doc = frappe.get_doc("GPS Gate Event Rule", doc_name)
            else:
                doc = frappe.new_doc("GPS Gate Event Rule")

            # Update fields
            doc.event_rule_id = rule_id
            doc.event_rule_name = rule.get("name") or rule.get("Name") or f"Rule {rule_id}"
            doc.description = rule.get("description") or rule.get("Description") or ""
            doc.is_enabled = 0 if rule.get("disabled", True) else 1
            doc.event_type = rule.get("eventType") or rule.get("type") or ""
            
            # Sync metadata
            doc.last_synced_on = now()
            doc.sync_status = "Success"
            doc.sync_error = ""
            doc.raw_response = frappe.as_json(rule)

            doc.save(ignore_permissions=True)
            synced += 1

        except Exception as e:
            error_msg = f"Error syncing event rule {rule.get('name', rule.get('id'))}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(
                title="GPS Gate Event Rule Sync Error",
                message=frappe.get_traceback()
            )

    frappe.db.commit()

    result = {
        "status": "success" if not errors else "partial",
        "synced_records": synced,
        "total_rules": len(event_rules)
    }

    if errors:
        result["errors"] = errors
        result["error_count"] = len(errors)

    return result

def scheduled_sync_gps_gate_events():
    """
    Scheduled job wrapper - roz 12:01 AM chalti hai
    Automatically previous day ki date pass karti hai
    """
    

    yesterday = add_days(today(), -1)
    
    sync_gps_gate_events(
        from_date=str(yesterday),
        to_date=str(yesterday)
    )

@frappe.whitelist()
def sync_gps_gate_events(from_date=None, to_date=None):
    """
    Start GPS Gate event sync for all users using background jobs
    Accepts from_date and to_date and enqueues jobs for each date individually
    """

    if not from_date or not to_date:
        return {"status": "error", "message": "from_date and to_date are required"}

    from frappe.utils import add_days, getdate

    start_date = getdate(from_date)
    end_date = getdate(to_date)

    # Generate list of all dates in the range
    total_days = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=i) for i in range(total_days)]

    users = frappe.get_all("GPS Gate User",filters={"user_type_id": 450}, pluck="name")
    if not users:
        return {"status": "no_users_found"}

    chunk_size = 50
    total_users = len(users)
    jobs_created = 0

    for date in dates:
        for i in range(0, total_users, chunk_size):
            user_chunk = users[i:i + chunk_size]

            # Direct function pass (recommended)
            frappe.enqueue(
                process_user_batch,
                queue="long",
                users=user_chunk,
                date=date.strftime("%Y-%m-%d"),
                job_name=f"gpsgate-sync-{date}-{i}"
            )

            jobs_created += 1

    return {
        "status": "started",
        "total_users": total_users,
        "chunk_size": chunk_size,
        "total_dates": total_days,
        "jobs_created": jobs_created
    }
    

def process_user_batch(users, date):
    """
    Process a batch of users and fetch events
    """

    try:

        client = get_gps_gate_client()

        date_formatted = format_date_for_api(date)

        rules = frappe.get_all(
            "GPS Gate Event Rule",
            filters={"is_enabled": 1},
            pluck="event_rule_id"
        )

        if not rules:
            frappe.log_error("No GPS Gate Event Rules found", "GPS Gate Sync")
            return

        for user in users:

            for rule in rules:

                try:

                    events = client.get_events(
                        date_formatted,
                        user,
                        rule
                    )

                    if events:
                        save_gps_gate_events(events)

                except Exception:

                    frappe.log_error(
                        frappe.get_traceback(),
                        f"GPS Gate Fetch Error - User {user} Rule {rule}"
                    )

    except Exception:

        frappe.log_error(
            frappe.get_traceback(),
            "GPS Gate Batch Processing Failed"
        )

def save_gps_gate_events(events):
    """
    Insert events into ERPNext
    """

    synced = 0

    for event in events:

        try:

            event_id = event.get("id")

            if not event_id:
                continue

            # Prevent duplicate
            if frappe.db.exists(
                "GPS Gate Event",
                {"event_id": str(event_id)}
            ):
                continue

            doc = frappe.new_doc("GPS Gate Event")

            # Basic Info
            doc.event_id = str(event_id)
            doc.event_rule_name = event.get("ruleName") or event.get("eventRuleName") or ""
            doc.application_id = str(event.get("applicationId") or "")
            doc.expression_evaluator_id = str(event.get("expressionEvaluatorId") or "")
            doc.comment = event.get("comment") or ""
            doc.support_ui = 1 if event.get("supportUi") else 0
            doc.event_stage = event.get("eventStage") or 0

            # Link Event Rule
            rule_id_to_link = event.get("expressionEvaluatorId")

            if rule_id_to_link:
                linked_rule = frappe.db.get_value(
                    "GPS Gate Event Rule",
                    {"event_rule_id": rule_id_to_link},
                    "name"
                )

                if linked_rule:
                    doc.event_rule = linked_rule

            # Link User
            user_id = event.get("userId") or event.get("assetId")

            if user_id:
                linked_user = frappe.db.get_value(
                    "GPS Gate User",
                    {"name": user_id},
                    "name"
                )

                if linked_user:
                    doc.gps_gate_user = linked_user

            # Status Flags
            doc.ongoing = 1 if event.get("ongoing") else 0
            doc.closed = 1 if event.get("closed") else 0

            # Event Time
            bounding_box = event.get("boundingBox") or {}

            event_time = (
                event.get("time")
                or event.get("triggerTime")
                or event.get("utc")
                or bounding_box.get("maxTime")
            )

            doc.event_time = sanitize_datetime(event_time)
            doc.event_time_utc = sanitize_datetime(
                event.get("utc") or bounding_box.get("maxTime")
            )

            doc.min_time = sanitize_datetime(bounding_box.get("minTime"))
            doc.max_time = sanitize_datetime(bounding_box.get("maxTime"))

            # Start Position
            start_pos = event.get("startPosition") or {}

            doc.start_latitude = start_pos.get("latitude")
            doc.start_longitude = start_pos.get("longitude")
            doc.start_altitude = start_pos.get("altitude")

            # End Position
            end_pos = event.get("endPosition") or {}

            doc.end_latitude = end_pos.get("latitude")
            doc.end_longitude = end_pos.get("longitude")
            doc.end_altitude = end_pos.get("altitude")

            # Current Position
            position = event.get("position") or event.get("trackPoint", {}).get("position") or {}

            doc.latitude = position.get("latitude")
            doc.longitude = position.get("longitude")
            doc.altitude = position.get("altitude")

            # Movement
            doc.speed = event.get("speed") or event.get("calculatedSpeed")
            doc.heading = event.get("heading") or event.get("course")
            doc.address = event.get("address") or ""

            # Bounding Box
            doc.bb_min_x = bounding_box.get("minX")
            doc.bb_max_x = bounding_box.get("maxX")
            doc.bb_min_y = bounding_box.get("minY")
            doc.bb_max_y = bounding_box.get("maxY")
            doc.bb_min_z = bounding_box.get("minZ")
            doc.bb_max_z = bounding_box.get("maxZ")

            # Event Details
            doc.event_message = (
                event.get("message")
                or event.get("description")
                or doc.event_rule_name
            )

            doc.event_data = frappe.as_json(event)
            doc.raw_response = frappe.as_json(event)

            # Sync Metadata
            doc.last_synced_on = now()
            doc.acknowledged = 0
            
            # ✅ Event Arguments (Child Table) — yahan add karo
            arguments = event.get("arguments") or []

            for arg in arguments:
                doc.append("event_arguments", {
                    "eventid": str(arg.get("eventID") or ""),
                    "variable": arg.get("variable") or "",
                    "value": arg.get("value") or "",
                    "sivalue": arg.get("siValue") or "",
                    "argumentid": str(arg.get("argumentID") or "")
                })

            doc.save(ignore_permissions=True)

            synced += 1

        except Exception:

            frappe.log_error(
                frappe.get_traceback(),
                f"GPS Gate Event Save Error {event.get('id')}"
            )

    frappe.db.commit()

    return synced


def _determine_event_severity(event):
    """
    Determine event severity based on event data.
    
    Args:
        event: Event data dictionary
        
    Returns:
        str: Severity level (Info, Warning, Critical)
    """
    # Check for explicit severity
    severity = event.get("severity") or event.get("priority")
    if severity:
        severity_lower = str(severity).lower()
        if severity_lower in ["critical", "high", "3"]:
            return "Critical"
        elif severity_lower in ["warning", "medium", "2"]:
            return "Warning"
        else:
            return "Info"
    
    # Try to determine from event rule name
    rule_name = (event.get("eventRuleName") or event.get("ruleName") or "").lower()
    
    critical_keywords = ["crash", "accident", "sos", "panic", "emergency", "collision"]
    warning_keywords = ["overspeed", "speeding", "geofence", "idle", "harsh", "fatigue"]
    
    for keyword in critical_keywords:
        if keyword in rule_name:
            return "Critical"
    
    for keyword in warning_keywords:
        if keyword in rule_name:
            return "Warning"
    
    return "Info"


# ========== ACKNOWLEDGE EVENTS ==========

@frappe.whitelist(allow_guest=False)
def acknowledge_events(event_names):
    """
    Acknowledge multiple events at once.
    
    Args:
        event_names: List of GPS Gate Event document names
        
    Returns:
        dict: Result with count of acknowledged events
    """
    if isinstance(event_names, str):
        event_names = frappe.parse_json(event_names)
    
    if not event_names:
        return {"status": "error", "message": _("No events specified")}
    
    acknowledged_count = 0
    
    for event_name in event_names:
        try:
            frappe.db.set_value("GPS Gate Event", event_name, "acknowledged", 1)
            acknowledged_count += 1
        except Exception as e:
            frappe.log_error(
                title="GPS Gate Event Acknowledge Error",
                message=f"Error acknowledging event {event_name}: {str(e)}"
            )
    
    frappe.db.commit()
    
    return {
        "status": "success",
        "acknowledged_count": acknowledged_count,
        "message": _("{0} events acknowledged").format(acknowledged_count)
    }


# ========== AUTO SYNC SCHEDULER ==========

def sync_events_scheduled():
    """
    Scheduled task to automatically sync events from GPS Gate.
    Syncs events for today's date.
    
    This function is meant to be called by the Frappe scheduler.
    """
    settings = frappe.get_single("GPS Gate Settings")
    
    if not settings.enable:
        return
    
    # Get today's date in YYYY-MM-DD format
    today = frappe.utils.today()
    
    try:
        result = sync_gps_gate_events(
            date=today
        )
        
        frappe.log_error(
            title="GPS Gate Events Auto Sync",
            message=f"Synced {result.get('synced_records', 0)} events for date {today}"
        )
        
    except Exception as e:
        frappe.log_error(
            title="GPS Gate Events Auto Sync Failed",
            message=frappe.get_traceback()
        )
