# Copyright (c) 2026, Naqeeb Khan
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

from gps_gate.gps_gate_api import GPSGateAPIError, get_gps_gate_client


class GPSGateGroup(Document):
    """GPS Gate Group Document Controller (Sync Only Version)"""

    # ================= SYNC MEMBERS =================

    def sync_members_from_gps_gate(self):
        """
        Sync group members from GPS Gate.
        Only fetches users and updates local child table.
        """
        if not self.group_id:
            frappe.throw(_("Cannot sync members: No GPS Gate Group ID found"))

        try:
            client = get_gps_gate_client()
            users = client.get_group_users(self.group_id)

            # Clear existing members
            self.set("group_members", [])

            # Add users from GPS Gate
            for user in (users or []):
                user_id = user.get("id")

                linked_user = None
                if user_id:
                    linked_user = frappe.db.get_value(
                        "GPS Gate User",
                        {"user_id": user_id},
                        "name"
                    )

                self.append("group_members", {
                    "gps_gate_user": linked_user,
                    "user_id": user_id,
                    "username": user.get("username"),
                    "full_name": f"{user.get('name', '')} {user.get('surname', '')}".strip(),
                    "added_on": now()
                })

            self.last_synced_on = now()
            self.save(ignore_permissions=True)

            return {
                "status": "success",
                "message": _("Synced {0} members from GPS Gate").format(len(users or []))
            }

        except GPSGateAPIError as e:
            return {"status": "error", "message": str(e.message)}

        except Exception as e:
            frappe.log_error(
                title="GPS Gate Group Members Sync Error",
                message=frappe.get_traceback()
            )
            return {
                "status": "error",
                "message": _("Failed to sync members from GPS Gate: {0}").format(str(e))
            }


# ================= WHITELISTED METHOD =================

@frappe.whitelist()
def sync_group_members(docname):
    """Sync group members from GPS Gate."""
    doc = frappe.get_doc("GPS Gate Group", docname)

    try:
        result = doc.sync_members_from_gps_gate()
        frappe.db.commit()
        return result
    except Exception as e:
        frappe.db.rollback()
        return {"status": "error", "message": str(e)}



# # Copyright (c) 2026, Naqeeb Khan
# # For license information, please see license.txt

# """
# GPS Gate Group DocType Controller

# This module handles the integration of GPS Gate Group records with the GPS Gate REST API.
# ERPNext acts as the single source of truth:
# - Creating a group in ERPNext creates it in GPS Gate
# - Updating a group in ERPNext updates it in GPS Gate
# - Deleting a group from ERPNext deletes it from GPS Gate

# All errors are properly handled, logged, and visible to the user.
# """

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from frappe.utils import now

# from gps_gate.gps_gate_api import GPSGateClient, GPSGateAPIError, get_gps_gate_client


# class GPSGateGroup(Document):
#     """GPS Gate Group Document Controller"""
    
#     # ========== VALIDATION ==========
    
#     def validate(self):
#         """Validate the document before saving."""
#         self.validate_required_fields()
    
#     def validate_required_fields(self):
#         """Validate that all required fields are present."""
#         if not self.group_name:
#             frappe.throw(_("Group Name is required"), title=_("Missing Required Field"))
    
#     # ========== DOCUMENT HOOKS ==========
    
#     def after_insert(self):
#         """
#         Called after the document is inserted.
#         Creates the group on GPS Gate if it's a new local group.
#         """
#         if getattr(self, '_skip_gps_gate_sync', False):
#             return
        
#         # Only create on GPS Gate if this is a new local group
#         if not self.group_id and not self.is_created_on_gps_gate:
#             self.create_on_gps_gate()
    
#     def on_trash(self):
#         """
#         Called before the document is deleted.
#         NOTE: Does NOT auto-delete from GPS Gate to prevent accidental data loss.
#         Use the 'Delete from GPS Gate' button to explicitly remove from GPS Gate.
#         """
#         # Do NOT auto-delete from GPS Gate
#         # User must explicitly use the 'Delete from GPS Gate' button
#         pass
    
#     # ========== GPS GATE API OPERATIONS ==========
    
#     def create_on_gps_gate(self):
#         """
#         Create this group on GPS Gate.
#         Updates the document with the returned GPS Gate Group ID.
#         """
#         try:
#             client = get_gps_gate_client()
#             payload = self._build_api_payload()
            
#             frappe.log_error(
#                 title="GPS Gate Create Group - Payload",
#                 message=f"Creating group with payload:\n{frappe.as_json(payload)}"
#             )
            
#             response = client.create_group(payload)
            
#             if not response or not response.get("id"):
#                 raise GPSGateAPIError(_("GPS Gate did not return a Group ID"))
            
#             # Update local record with GPS Gate ID
#             frappe.db.set_value("GPS Gate Group", self.name, {
#                 "group_id": response.get("id"),
#                 "is_created_on_gps_gate": 1,
#                 "sync_status": "Success",
#                 "sync_error": "",
#                 "last_synced_on": now()
#             }, update_modified=False)
            
#             self.group_id = response.get("id")
#             self.is_created_on_gps_gate = 1
#             self.sync_status = "Success"
#             self.sync_error = ""
#             self.last_synced_on = now()
            
#             frappe.msgprint(
#                 _("Group successfully created on GPS Gate with ID: {0}").format(response.get("id")),
#                 indicator="green",
#                 alert=True
#             )
            
#             return response
            
#         except GPSGateAPIError as e:
#             self._handle_sync_error(str(e.message), operation="create")
#             frappe.throw(str(e.message))
#         except Exception as e:
#             error_msg = str(e)
#             self._handle_sync_error(error_msg, operation="create")
#             frappe.log_error(title="GPS Gate Group Create Error", message=frappe.get_traceback())
#             frappe.throw(_("Failed to create group on GPS Gate: {0}").format(error_msg))
    
#     def update_on_gps_gate(self):
#         """
#         Update this group on GPS Gate.
#         """
#         if not self.group_id:
#             frappe.throw(_("Cannot update group on GPS Gate: No GPS Gate Group ID found"))
        
#         try:
#             client = get_gps_gate_client()
#             payload = self._build_api_payload(include_id=True)
            
#             frappe.log_error(
#                 title="GPS Gate Update Group - Payload",
#                 message=f"Updating group {self.group_id} with payload:\n{frappe.as_json(payload)}"
#             )
            
#             response = client.update_group(self.group_id, payload)
            
#             # Update sync status
#             frappe.db.set_value("GPS Gate Group", self.name, {
#                 "sync_status": "Success",
#                 "sync_error": "",
#                 "last_synced_on": now()
#             }, update_modified=False)
            
#             self.sync_status = "Success"
#             self.sync_error = ""
#             self.last_synced_on = now()
            
#             frappe.msgprint(
#                 _("Group successfully updated on GPS Gate"),
#                 indicator="green",
#                 alert=True
#             )
            
#             return response
            
#         except GPSGateAPIError as e:
#             self._handle_sync_error(str(e.message), operation="update")
#             frappe.throw(str(e.message))
#         except Exception as e:
#             error_msg = str(e)
#             self._handle_sync_error(error_msg, operation="update")
#             frappe.log_error(title="GPS Gate Group Update Error", message=frappe.get_traceback())
#             frappe.throw(_("Failed to update group on GPS Gate: {0}").format(error_msg))
    
#     def delete_on_gps_gate(self):
#         """
#         Delete this group from GPS Gate.
#         """
#         if not self.group_id:
#             return
        
#         try:
#             client = get_gps_gate_client()
            
#             frappe.log_error(
#                 title="GPS Gate Delete Group",
#                 message=f"Deleting group {self.group_id} from GPS Gate"
#             )
            
#             client.delete_group(self.group_id)
            
#             frappe.msgprint(
#                 _("Group successfully deleted from GPS Gate"),
#                 indicator="green",
#                 alert=True
#             )
            
#         except GPSGateAPIError as e:
#             frappe.log_error(
#                 title="GPS Gate Group Delete Error",
#                 message=f"""Failed to delete group from GPS Gate
                
# Group ID: {self.group_id}
# Document: {self.name}
# Error: {e.message}
# Status Code: {e.status_code}
# Response: {e.response_text}
# """
#             )
#             frappe.msgprint(
#                 _("Warning: Failed to delete group from GPS Gate. Error: {0}. The error has been logged.").format(e.message),
#                 indicator="orange",
#                 alert=True
#             )
#         except Exception as e:
#             frappe.log_error(
#                 title="GPS Gate Group Delete Error",
#                 message=frappe.get_traceback()
#             )
#             frappe.msgprint(
#                 _("Warning: Failed to delete group from GPS Gate. Error: {0}. The error has been logged.").format(str(e)),
#                 indicator="orange",
#                 alert=True
#             )
    
#     def sync_members_from_gps_gate(self):
#         """
#         Sync group members from GPS Gate.
#         """
#         if not self.group_id:
#             frappe.throw(_("Cannot sync members: No GPS Gate Group ID found"))
        
#         try:
#             client = get_gps_gate_client()
#             users = client.get_group_users(self.group_id)
            
#             # Clear existing members
#             self.set("group_members", [])
            
#             # Add users from GPS Gate
#             for user in (users or []):
#                 user_id = user.get("id")
                
#                 # Try to find linked GPS Gate User
#                 linked_user = None
#                 if user_id:
#                     linked_user = frappe.db.get_value(
#                         "GPS Gate User",
#                         {"user_id": user_id},
#                         "name"
#                     )
                
#                 self.append("group_members", {
#                     "gps_gate_user": linked_user,
#                     "user_id": user_id,
#                     "username": user.get("username"),
#                     "full_name": f"{user.get('name', '')} {user.get('surname', '')}".strip(),
#                     "added_on": now()
#                 })
            
#             self.last_synced_on = now()
#             self._skip_gps_gate_sync = True
#             self.save(ignore_permissions=True)
            
#             frappe.msgprint(
#                 _("Synced {0} members from GPS Gate").format(len(users or [])),
#                 indicator="green",
#                 alert=True
#             )
            
#             return {"status": "success", "member_count": len(users or [])}
            
#         except GPSGateAPIError as e:
#             frappe.throw(str(e.message))
#         except Exception as e:
#             frappe.log_error(title="GPS Gate Group Members Sync Error", message=frappe.get_traceback())
#             frappe.throw(_("Failed to sync members from GPS Gate: {0}").format(str(e)))
    
#     def add_member_to_gps_gate(self, user_id):
#         """
#         Add a user to this group on GPS Gate.
        
#         Args:
#             user_id: GPS Gate user ID to add
#         """
#         if not self.group_id:
#             frappe.throw(_("Cannot add member: No GPS Gate Group ID found"))
        
#         try:
#             client = get_gps_gate_client()
#             client.add_user_to_group(self.group_id, user_id)
            
#             frappe.msgprint(
#                 _("User added to group on GPS Gate"),
#                 indicator="green",
#                 alert=True
#             )
            
#         except GPSGateAPIError as e:
#             frappe.throw(str(e.message))
#         except Exception as e:
#             frappe.log_error(title="GPS Gate Add Member Error", message=frappe.get_traceback())
#             frappe.throw(_("Failed to add member to group: {0}").format(str(e)))
    
#     def remove_member_from_gps_gate(self, user_id):
#         """
#         Remove a user from this group on GPS Gate.
        
#         Args:
#             user_id: GPS Gate user ID to remove
#         """
#         if not self.group_id:
#             frappe.throw(_("Cannot remove member: No GPS Gate Group ID found"))
        
#         try:
#             client = get_gps_gate_client()
#             client.remove_user_from_group(self.group_id, user_id)
            
#             frappe.msgprint(
#                 _("User removed from group on GPS Gate"),
#                 indicator="green",
#                 alert=True
#             )
            
#         except GPSGateAPIError as e:
#             frappe.throw(str(e.message))
#         except Exception as e:
#             frappe.log_error(title="GPS Gate Remove Member Error", message=frappe.get_traceback())
#             frappe.throw(_("Failed to remove member from group: {0}").format(str(e)))
    
#     def _build_api_payload(self, include_id=False):
#         """
#         Build the API payload for create/update operations.
        
#         Args:
#             include_id: Whether to include the group ID in the payload
            
#         Returns:
#             dict: API payload
#         """
#         payload = {
#             "name": self.group_name
#         }
        
#         if include_id and self.group_id:
#             payload["id"] = int(self.group_id)
        
#         if self.description:
#             payload["description"] = self.description
        
#         # Handle parent group
#         if self.parent_group:
#             parent_id = frappe.db.get_value("GPS Gate Group", self.parent_group, "group_id")
#             if parent_id:
#                 payload["parentId"] = int(parent_id)
#         elif self.parent_group_id:
#             payload["parentId"] = int(self.parent_group_id)
        
#         return payload
    
#     def _handle_sync_error(self, error_message, operation="sync"):
#         """
#         Handle and record sync errors.
#         """
#         try:
#             frappe.db.set_value("GPS Gate Group", self.name, {
#                 "sync_status": "Failed",
#                 "sync_error": f"{operation.upper()} Error: {error_message}"
#             }, update_modified=False)
            
#             self.sync_status = "Failed"
#             self.sync_error = f"{operation.upper()} Error: {error_message}"
#         except Exception:
#             pass


# # ========== WHITELISTED METHODS ==========

# @frappe.whitelist()
# def create_group_on_gps_gate(docname):
#     """Manually create a group on GPS Gate."""
#     doc = frappe.get_doc("GPS Gate Group", docname)
    
#     if doc.group_id:
#         return {"status": "error", "message": _("Group already exists on GPS Gate with ID: {0}").format(doc.group_id)}
    
#     try:
#         doc.create_on_gps_gate()
#         frappe.db.commit()
#         return {"status": "success", "message": _("Group created on GPS Gate with ID: {0}").format(doc.group_id)}
#     except Exception as e:
#         frappe.db.rollback()
#         return {"status": "error", "message": str(e)}


# @frappe.whitelist()
# def update_group_on_gps_gate(docname):
#     """Manually update a group on GPS Gate."""
#     doc = frappe.get_doc("GPS Gate Group", docname)
    
#     if not doc.group_id:
#         return {"status": "error", "message": _("Group does not have a GPS Gate Group ID. Please create the group first.")}
    
#     try:
#         doc.update_on_gps_gate()
#         frappe.db.commit()
#         return {"status": "success", "message": _("Group updated on GPS Gate")}
#     except Exception as e:
#         frappe.db.rollback()
#         return {"status": "error", "message": str(e)}


# @frappe.whitelist()
# def sync_group_members(docname):
#     """Sync group members from GPS Gate."""
#     doc = frappe.get_doc("GPS Gate Group", docname)
    
#     try:
#         result = doc.sync_members_from_gps_gate()
#         frappe.db.commit()
#         return result
#     except Exception as e:
#         frappe.db.rollback()
#         return {"status": "error", "message": str(e)}


# @frappe.whitelist()
# def add_user_to_group(docname, user_docname):
#     """Add a GPS Gate User to a group."""
#     doc = frappe.get_doc("GPS Gate Group", docname)
#     user_doc = frappe.get_doc("GPS Gate User", user_docname)
    
#     if not user_doc.user_id:
#         return {"status": "error", "message": _("User does not have a GPS Gate User ID")}
    
#     try:
#         doc.add_member_to_gps_gate(user_doc.user_id)
        
#         # Add to local child table if not already present
#         existing = [m.user_id for m in doc.group_members]
#         if user_doc.user_id not in existing:
#             doc.append("group_members", {
#                 "gps_gate_user": user_docname,
#                 "user_id": user_doc.user_id,
#                 "username": user_doc.username,
#                 "full_name": user_doc.full_name,
#                 "added_on": now()
#             })
#             doc._skip_gps_gate_sync = True
#             doc.save(ignore_permissions=True)
        
#         frappe.db.commit()
#         return {"status": "success", "message": _("User added to group")}
#     except Exception as e:
#         frappe.db.rollback()
#         return {"status": "error", "message": str(e)}


# @frappe.whitelist()
# def remove_user_from_group(docname, user_docname):
#     """Remove a GPS Gate User from a group."""
#     doc = frappe.get_doc("GPS Gate Group", docname)
#     user_doc = frappe.get_doc("GPS Gate User", user_docname)
    
#     if not user_doc.user_id:
#         return {"status": "error", "message": _("User does not have a GPS Gate User ID")}
    
#     try:
#         doc.remove_member_from_gps_gate(user_doc.user_id)
        
#         # Remove from local child table
#         doc.group_members = [m for m in doc.group_members if m.user_id != user_doc.user_id]
#         doc._skip_gps_gate_sync = True
#         doc.save(ignore_permissions=True)
        
#         frappe.db.commit()
#         return {"status": "success", "message": _("User removed from group")}
#     except Exception as e:
#         frappe.db.rollback()
#         return {"status": "error", "message": str(e)}


# @frappe.whitelist()
# def delete_group_from_gps_gate(docname):
#     """
#     Manually delete a group from GPS Gate (without deleting from ERPNext).
#     This clears the GPS Gate sync status but keeps the local record.
    
#     Args:
#         docname: Name of the GPS Gate Group document
        
#     Returns:
#         dict: Result of the delete operation
#     """
#     doc = frappe.get_doc("GPS Gate Group", docname)
    
#     if not doc.group_id:
#         return {"status": "error", "message": _("Group does not have a GPS Gate Group ID.")}
    
#     try:
#         # Delete from GPS Gate
#         doc.delete_on_gps_gate()
        
#         # Clear GPS Gate sync fields but keep the local record
#         frappe.db.set_value("GPS Gate Group", docname, {
#             "group_id": None,
#             "is_created_on_gps_gate": 0,
#             "sync_status": "",
#             "sync_error": "",
#             "last_synced_on": None
#         }, update_modified=False)
        
#         frappe.db.commit()
#         return {"status": "success", "message": _("Group deleted from GPS Gate. Local record preserved.")}
#     except Exception as e:
#         frappe.db.rollback()
#         return {"status": "error", "message": str(e)}
