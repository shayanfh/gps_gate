// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Track Point", {
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
    },

    add_gps_gate_buttons(frm) {
        frm.remove_custom_button(__("Sync Tracks for Date"), __("GPS Gate"));
        frm.add_custom_button(__("Sync Tracks for Date"), function () {
            frm.trigger("sync_tracks_for_date");
        }, __("GPS Gate"));
    },

    sync_tracks_for_date(frm) {
        let default_date = frm.doc.track_time
            ? frm.doc.track_time.split(" ")[0]
            : frappe.datetime.nowdate();

        frappe.prompt(
            {
                label: __("Date"),
                fieldname: "date",
                fieldtype: "Date",
                default: default_date,
                reqd: 1
            },
            function (values) {
                frappe.call({
                    method: "gps_gate.gps_gate.doctype.gps_gate_track_point.gps_gate_track_point.sync_tracks_for_date",
                    args: {
                        gps_gate_user: frm.doc.gps_gate_user,
                        date: values.date
                    },
                    freeze: true,
                    freeze_message: __("Syncing track points from GPS Gate..."),
                    callback(r) {
                        if (r.message) {
                            let indicator = r.message.status === "success" ? "green" : "orange";
                            frappe.show_alert({ message: r.message.message, indicator });
                        }
                        frm.reload_doc();
                    },
                    error() {
                        frappe.show_alert({ message: __("Sync failed. Check Error Log."), indicator: "red" });
                    }
                });
            },
            __("Sync Track Points"),
            __("Sync")
        );
    }
});
