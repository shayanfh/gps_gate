// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Group", {
    refresh(frm) {
        frm.trigger("show_sync_status");

        if (!frm.is_new()) {
            frm.trigger("add_sync_button");
        }
    },

    add_sync_button(frm) {
        // Remove any existing GPS Gate buttons
        frm.remove_custom_button(__("Sync Members"), __("GPS Gate"));

        // Only show Sync button if group exists on GPS Gate
        if (frm.doc.group_id) {
            frm.add_custom_button(__("Sync Members"), function () {
                frm.trigger("sync_members");
            }, __("GPS Gate"));
        }
    },

    sync_members(frm) {
        frappe.confirm(
            __("Sync members from GPS Gate? This will overwrite the current member list."),
            function () {
                frappe.call({
                    method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.sync_group_members",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Syncing members from GPS Gate..."),
                    callback: function (r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: r.message.message || __("Members synced"),
                                indicator: r.message.status === "success" ? "green" : "red"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }
        );
    },

    show_sync_status(frm) {
        frm.dashboard.clear_headline();

        if (frm.is_new()) return;

        if (frm.doc.group_id && frm.doc.is_created_on_gps_gate) {
            let headline = __("Synced with GPS Gate (Group ID: {0})", [frm.doc.group_id]);

            if (frm.doc.last_synced_on) {
                headline += " - " + __("Last synced: {0}", [frappe.datetime.prettyDate(frm.doc.last_synced_on)]);
            }

            frm.dashboard.set_headline(headline, "green");

            if (frm.doc.sync_status === "Failed") {
                frm.set_intro(
                    __("Last sync failed: {0}", [frm.doc.sync_error || "Unknown error"]),
                    "red"
                );
            }
        } else {
            frm.dashboard.set_headline(
                __("Not synced to GPS Gate"),
                "orange"
            );
        }
    }
});



// // Copyright (c) 2026, Naqeeb Khan and contributors
// // For license information, please see license.txt

// frappe.ui.form.on("GPS Gate Group", {
//     refresh(frm) {
//         // Show sync status
//         frm.trigger("show_sync_status");

//         // Add GPS Gate action buttons
//         if (!frm.is_new()) {
//             frm.trigger("add_gps_gate_buttons");
//         }
//     },

//     add_gps_gate_buttons(frm) {
//         // Clear existing GPS Gate buttons
//         frm.remove_custom_button(__("Create on GPS Gate"), __("GPS Gate"));
//         frm.remove_custom_button(__("Update on GPS Gate"), __("GPS Gate"));
//         frm.remove_custom_button(__("Sync Members"), __("GPS Gate"));
//         frm.remove_custom_button(__("Add User"), __("GPS Gate"));
//         frm.remove_custom_button(__("Delete from GPS Gate"), __("GPS Gate"));

//         if (!frm.doc.group_id) {
//             // Group doesn't exist on GPS Gate - show Create button
//             frm.add_custom_button(__("Create on GPS Gate"), function () {
//                 frm.trigger("create_on_gps_gate");
//             }, __("GPS Gate"));
//         } else {
//             // Group exists on GPS Gate
//             frm.add_custom_button(__("Update on GPS Gate"), function () {
//                 frm.trigger("update_on_gps_gate");
//             }, __("GPS Gate"));

//             frm.add_custom_button(__("Sync Members"), function () {
//                 frm.trigger("sync_members");
//             }, __("GPS Gate"));

//             frm.add_custom_button(__("Add User"), function () {
//                 frm.trigger("add_user_dialog");
//             }, __("GPS Gate"));

//             // Delete from GPS Gate button (appears in red)
//             frm.add_custom_button(__("Delete from GPS Gate"), function () {
//                 frm.trigger("delete_from_gps_gate");
//             }, __("GPS Gate"));
//         }
//     },

//     create_on_gps_gate(frm) {
//         if (frm.is_dirty()) {
//             frappe.msgprint(__("Please save the document first."));
//             return;
//         }

//         if (!frm.doc.group_name) {
//             frappe.msgprint(__("Group Name is required."));
//             return;
//         }

//         frappe.confirm(
//             __("Create this group on GPS Gate?"),
//             function () {
//                 frappe.call({
//                     method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.create_group_on_gps_gate",
//                     args: { docname: frm.doc.name },
//                     freeze: true,
//                     freeze_message: __("Creating group on GPS Gate..."),
//                     callback: function (r) {
//                         if (r.message) {
//                             frappe.show_alert({
//                                 message: r.message.message,
//                                 indicator: r.message.status === "success" ? "green" : "red"
//                             });
//                             frm.reload_doc();
//                         }
//                     }
//                 });
//             }
//         );
//     },

//     update_on_gps_gate(frm) {
//         if (frm.is_dirty()) {
//             frappe.msgprint(__("Please save the document first."));
//             return;
//         }

//         frappe.confirm(
//             __("Update this group on GPS Gate?"),
//             function () {
//                 frappe.call({
//                     method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.update_group_on_gps_gate",
//                     args: { docname: frm.doc.name },
//                     freeze: true,
//                     freeze_message: __("Updating group on GPS Gate..."),
//                     callback: function (r) {
//                         if (r.message) {
//                             frappe.show_alert({
//                                 message: r.message.message,
//                                 indicator: r.message.status === "success" ? "green" : "red"
//                             });
//                             frm.reload_doc();
//                         }
//                     }
//                 });
//             }
//         );
//     },

//     delete_from_gps_gate(frm) {
//         frappe.confirm(
//             __("Are you sure you want to delete this group from GPS Gate?<br><br><b>This will:</b><ul><li>Remove the group from GPS Gate</li><li>Keep the local record in ERPNext</li><li>Clear the sync status</li></ul>"),
//             function () {
//                 frappe.call({
//                     method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.delete_group_from_gps_gate",
//                     args: { docname: frm.doc.name },
//                     freeze: true,
//                     freeze_message: __("Deleting group from GPS Gate..."),
//                     callback: function (r) {
//                         if (r.message) {
//                             frappe.show_alert({
//                                 message: r.message.message,
//                                 indicator: r.message.status === "success" ? "green" : "red"
//                             });
//                             frm.reload_doc();
//                         }
//                     }
//                 });
//             }
//         );
//     },

//     sync_members(frm) {
//         frappe.confirm(
//             __("Sync members from GPS Gate? This will overwrite the current member list."),
//             function () {
//                 frappe.call({
//                     method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.sync_group_members",
//                     args: { docname: frm.doc.name },
//                     freeze: true,
//                     freeze_message: __("Syncing members from GPS Gate..."),
//                     callback: function (r) {
//                         if (r.message) {
//                             frappe.show_alert({
//                                 message: r.message.message || __("Members synced"),
//                                 indicator: r.message.status === "success" ? "green" : "red"
//                             });
//                             frm.reload_doc();
//                         }
//                     }
//                 });
//             }
//         );
//     },

//     add_user_dialog(frm) {
//         let d = new frappe.ui.Dialog({
//             title: __("Add User to Group"),
//             fields: [
//                 {
//                     label: __("GPS Gate User"),
//                     fieldname: "gps_gate_user",
//                     fieldtype: "Link",
//                     options: "GPS Gate User",
//                     reqd: 1,
//                     get_query: function () {
//                         // Exclude users already in the group
//                         let existing_users = (frm.doc.group_members || []).map(m => m.gps_gate_user);
//                         return {
//                             filters: {
//                                 "user_id": ["!=", ""],
//                                 "name": ["not in", existing_users]
//                             }
//                         };
//                     }
//                 }
//             ],
//             primary_action_label: __("Add"),
//             primary_action: function (values) {
//                 d.hide();

//                 frappe.call({
//                     method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.add_user_to_group",
//                     args: {
//                         docname: frm.doc.name,
//                         user_docname: values.gps_gate_user
//                     },
//                     freeze: true,
//                     freeze_message: __("Adding user to group..."),
//                     callback: function (r) {
//                         if (r.message) {
//                             frappe.show_alert({
//                                 message: r.message.message,
//                                 indicator: r.message.status === "success" ? "green" : "red"
//                             });
//                             frm.reload_doc();
//                         }
//                     }
//                 });
//             }
//         });

//         d.show();
//     },

//     show_sync_status(frm) {
//         frm.dashboard.clear_headline();

//         if (frm.is_new()) return;

//         if (frm.doc.group_id && frm.doc.is_created_on_gps_gate) {
//             let headline = __("Synced with GPS Gate (Group ID: {0})", [frm.doc.group_id]);
//             if (frm.doc.last_synced_on) {
//                 headline += " - " + __("Last synced: {0}", [frappe.datetime.prettyDate(frm.doc.last_synced_on)]);
//             }
//             frm.dashboard.set_headline(headline, "green");

//             if (frm.doc.sync_status === "Failed") {
//                 frm.set_intro(
//                     __("Last sync failed: {0}", [frm.doc.sync_error || "Unknown error"]),
//                     "red"
//                 );
//             }
//         } else {
//             frm.dashboard.set_headline(
//                 __("Not synced to GPS Gate - Click 'Create on GPS Gate' to sync"),
//                 "orange"
//             );
//         }
//     }
// });

// // Child table events
// frappe.ui.form.on("GPS Gate Group Member", {
//     before_group_members_remove: function (frm, cdt, cdn) {
//         let row = locals[cdt][cdn];

//         if (row.user_id && frm.doc.group_id) {
//             // Remove user from GPS Gate group as well
//             frappe.call({
//                 method: "gps_gate.gps_gate.doctype.gps_gate_group.gps_gate_group.remove_user_from_group",
//                 args: {
//                     docname: frm.doc.name,
//                     user_docname: row.gps_gate_user
//                 },
//                 async: false,
//                 callback: function (r) {
//                     if (r.message && r.message.status !== "success") {
//                         frappe.msgprint(r.message.message);
//                     }
//                 }
//             });
//         }
//     }
// });
