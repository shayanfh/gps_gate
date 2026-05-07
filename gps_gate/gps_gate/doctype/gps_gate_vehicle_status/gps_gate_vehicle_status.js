// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Vehicle Status", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.trigger("add_gps_gate_buttons");
        }

        if (frm.doc.latitude && frm.doc.longitude) {
            frm.add_custom_button(__("View on Map"), function () {
                window.open(
                    `https://www.google.com/maps?q=${frm.doc.latitude},${frm.doc.longitude}`,
                    "_blank"
                );
            });
        }

        frm.trigger("show_status_indicator");
    },

    add_gps_gate_buttons(frm) {
        frm.remove_custom_button(__("Sync from GPS Gate"), __("GPS Gate"));
        frm.add_custom_button(__("Sync from GPS Gate"), function () {
            frm.trigger("sync_from_gps_gate");
        }, __("GPS Gate"));
    },

    sync_from_gps_gate(frm) {
        frappe.confirm(
            __("Fetch the latest status from GPS Gate? This will overwrite current values."),
            function () {
                frappe.call({
                    method: "gps_gate.gps_gate.doctype.gps_gate_vehicle_status.gps_gate_vehicle_status.sync_vehicle_status",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Fetching from GPS Gate..."),
                    callback(r) {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({ message: r.message.message, indicator: "green" });
                        } else {
                            frappe.show_alert({ message: __("Sync failed. Check Error Log."), indicator: "red" });
                        }
                        frm.reload_doc();
                    },
                    error() {
                        frappe.show_alert({ message: __("Sync failed. Check Error Log."), indicator: "red" });
                        frm.reload_doc();
                    }
                });
            }
        );
    },

    show_status_indicator(frm) {
        if (frm.is_new()) return;

        let color = frm.doc.online_status === "Online" ? "green" : "red";
        let headline = frm.doc.user_name || frm.doc.gps_gate_user;

        if (frm.doc.device_time) {
            headline += " — " + frappe.datetime.str_to_user(frm.doc.device_time);
        }

        frm.dashboard.set_headline(headline, color);
    }
});
