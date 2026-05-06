// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate User", {
    refresh(frm) {
        // Add GPS Gate action buttons
        if (!frm.is_new()) {
            frm.trigger("add_gps_gate_buttons");
        }
    },

    add_gps_gate_buttons(frm) {
        frm.remove_custom_button(__("Fetch from GPS Gate"), __("GPS Gate"));
        frm.add_custom_button(__("Fetch from GPS Gate"), function () {
            frm.trigger("fetch_from_gps_gate");
        }, __("GPS Gate"));
    },

    fetch_from_gps_gate(frm) {
        frappe.confirm(
            __("Are you sure you want to fetch the latest data from GPS Gate? This will overwrite local changes."),
            function () {
                frappe.call({
                    method: "gps_gate.gps_gate.doctype.gps_gate_user.gps_gate_user.fetch_user_from_gps_gate",
                    args: {
                        docname: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Fetching from GPS Gate..."),
                    callback: function (r) {
                        if (r.message) {
                            if (r.message.status === "success") {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: "green"
                                });
                            } else {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: "red"
                                });
                            }
                            frm.reload_doc();
                        }
                    },
                    error: function (r) {
                        frappe.show_alert({
                            message: __("Failed to fetch from GPS Gate. Check Error Log for details."),
                            indicator: "red"
                        });
                        frm.reload_doc();
                    }
                });
            }
        );
    },


    
});
