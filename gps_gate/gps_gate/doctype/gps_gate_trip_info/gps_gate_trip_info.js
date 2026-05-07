// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Trip Info", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.trigger("add_gps_gate_buttons");
        }

        if (frm.doc.start_latitude && frm.doc.start_longitude) {
            frm.add_custom_button(__("View Start on Map"), function () {
                window.open(
                    `https://www.google.com/maps?q=${frm.doc.start_latitude},${frm.doc.start_longitude}`,
                    "_blank"
                );
            });
        }

        if (frm.doc.end_latitude && frm.doc.end_longitude) {
            frm.add_custom_button(__("View End on Map"), function () {
                window.open(
                    `https://www.google.com/maps?q=${frm.doc.end_latitude},${frm.doc.end_longitude}`,
                    "_blank"
                );
            });
        }

        frm.trigger("show_trip_summary");
    },

    add_gps_gate_buttons(frm) {
        frm.remove_custom_button(__("Sync Trips for Date"), __("GPS Gate"));
        frm.add_custom_button(__("Sync Trips for Date"), function () {
            frm.trigger("sync_trips_for_date");
        }, __("GPS Gate"));
    },

    sync_trips_for_date(frm) {
        let default_date = frm.doc.start_time
            ? frm.doc.start_time.split(" ")[0]
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
                    method: "gps_gate.gps_gate.doctype.gps_gate_trip_info.gps_gate_trip_info.sync_trips_for_date",
                    args: {
                        gps_gate_user: frm.doc.gps_gate_user,
                        date: values.date
                    },
                    freeze: true,
                    freeze_message: __("Syncing trips from GPS Gate..."),
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
            __("Sync Trips"),
            __("Sync")
        );
    },

    show_trip_summary(frm) {
        if (frm.is_new()) return;

        let parts = [];

        if (frm.doc.distance) {
            let km = (frm.doc.distance / 1000).toFixed(2);
            parts.push(__("{0} km", [km]));
        }
        if (frm.doc.duration) {
            let mins = Math.floor(frm.doc.duration / 60);
            parts.push(__("{0} min", [mins]));
        }
        if (frm.doc.is_idle) {
            parts.push(__("Idle"));
        }

        if (parts.length) {
            frm.dashboard.set_headline(parts.join("  |  "), frm.doc.is_idle ? "orange" : "blue");
        }
    }
});
