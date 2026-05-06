# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

"""
GPS Gate Groups Sync Module

This module provides functionality to sync groups from GPS Gate to ERPNext.
Uses the centralized GPS Gate API client for all API interactions.
"""

import frappe
from frappe.utils import now
from frappe import _

from gps_gate.gps_gate_api import get_gps_gate_client, GPSGateAPIError


@frappe.whitelist(allow_guest=False)
def sync_gps_gate_groups():
    """
    Fetch groups from GPS Gate and sync them into ERPNext.
    Creates new records for groups that don't exist, updates existing ones.
    
    Returns:
        dict: Sync result with status and count of synced records
    """
    try:
        client = get_gps_gate_client()
        groups = client.get_groups()
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(
            title="GPS Gate Groups Sync Failed",
            message=frappe.get_traceback()
        )
        frappe.throw(_("Unable to connect to GPS Gate API: {0}").format(str(e)))

    if not groups:
        return {
            "status": "success",
            "synced_records": 0,
            "message": _("No groups found in GPS Gate")
        }

    synced = 0
    errors = []

    # First pass: Create/update all groups without parent relationships
    for group in groups:
        try:
            group_id = group.get("id")
            if not group_id:
                continue

            # Check existing record
            doc_name = frappe.db.get_value(
                "GPS Gate Group",
                {"group_id": group_id},
                "name"
            )

            if doc_name:
                doc = frappe.get_doc("GPS Gate Group", doc_name)
            else:
                doc = frappe.new_doc("GPS Gate Group")
            
            doc._skip_gps_gate_sync = True

            # Update fields
            doc.group_id = group_id
            doc.group_name = group.get("name") or group.get("Name") or f"Group {group_id}"
            doc.description = group.get("description") or group.get("Description") or ""
            doc.parent_group_id = group.get("parentId") or group.get("ParentId")
            
            # Sync metadata
            doc.is_created_on_gps_gate = 1
            doc.last_synced_on = now()
            doc.sync_status = "Success"
            doc.sync_error = ""
            doc.raw_response = frappe.as_json(group)

            doc.save(ignore_permissions=True)
            synced += 1

        except Exception as e:
            error_msg = f"Error syncing group {group.get('name', group.get('id'))}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(
                title="GPS Gate Group Sync Error",
                message=frappe.get_traceback()
            )

    # Second pass: Update parent group links
    for group in groups:
        try:
            group_id = group.get("id")
            parent_id = group.get("parentId") or group.get("ParentId")
            
            if not parent_id:
                continue
            
            doc_name = frappe.db.get_value(
                "GPS Gate Group",
                {"group_id": group_id},
                "name"
            )
            
            parent_name = frappe.db.get_value(
                "GPS Gate Group",
                {"group_id": parent_id},
                "name"
            )
            
            if doc_name and parent_name:
                frappe.db.set_value("GPS Gate Group", doc_name, "parent_group", parent_name)
                
        except Exception:
            pass  # Ignore parent linking errors

    frappe.db.commit()

    result = {
        "status": "success" if not errors else "partial",
        "synced_records": synced,
        "total_groups": len(groups)
    }

    if errors:
        result["errors"] = errors
        result["error_count"] = len(errors)

    return result


@frappe.whitelist(allow_guest=False)
def sync_group_with_members(docname):
    """
    Sync a single group and its members from GPS Gate.
    
    Args:
        docname: GPS Gate Group document name
        
    Returns:
        dict: Sync result
    """
    doc = frappe.get_doc("GPS Gate Group", docname)
    
    if not doc.group_id:
        return {"status": "error", "message": _("Group does not have a GPS Gate Group ID")}
    
    try:
        client = get_gps_gate_client()
        
        # Get group details
        group_data = client.get_group(doc.group_id)
        
        if group_data:
            doc.group_name = group_data.get("name") or doc.group_name
            doc.description = group_data.get("description") or doc.description
            doc.raw_response = frappe.as_json(group_data)
        
        # Get group members
        users = client.get_group_users(doc.group_id)
        
        # Clear existing members
        doc.set("group_members", [])
        
        # Add users from GPS Gate
        for user in (users or []):
            user_id = user.get("id")
            
            # Try to find linked GPS Gate User
            linked_user = None
            if user_id:
                linked_user = frappe.db.get_value(
                    "GPS Gate User",
                    {"user_id": user_id},
                    "name"
                )
            
            doc.append("group_members", {
                "gps_gate_user": linked_user,
                "user_id": user_id,
                "username": user.get("username"),
                "full_name": f"{user.get('name', '')} {user.get('surname', '')}".strip(),
                "added_on": now()
            })
        
        doc.last_synced_on = now()
        doc.sync_status = "Success"
        doc.sync_error = ""
        doc._skip_gps_gate_sync = True
        doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": _("Group synced with {0} members").format(len(users or []))
        }
        
    except GPSGateAPIError as e:
        frappe.throw(str(e.message))
    except Exception as e:
        frappe.log_error(
            title="GPS Gate Group Sync Error",
            message=frappe.get_traceback()
        )
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False)
def get_group_hierarchy():
    """
    Get all groups organized in a hierarchical structure.
    
    Returns:
        list: Hierarchical list of groups
    """
    groups = frappe.get_all(
        "GPS Gate Group",
        fields=["name", "group_id", "group_name", "parent_group", "description"],
        order_by="group_name"
    )
    
    # Build hierarchy
    group_map = {g["name"]: g for g in groups}
    
    for group in groups:
        group["children"] = []
    
    root_groups = []
    for group in groups:
        if group["parent_group"] and group["parent_group"] in group_map:
            group_map[group["parent_group"]]["children"].append(group)
        else:
            root_groups.append(group)
    
    return root_groups
