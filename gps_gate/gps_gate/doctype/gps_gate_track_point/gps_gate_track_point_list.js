// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["GPS Gate Track Point"] = {
    onload: function (listview) {
        listview.page.add_inner_button(__("Sync Tracks"), function () {
            let d = new frappe.ui.Dialog({
                title: __("Sync Track Points from GPS Gate"),
                fields: [
                    {
                        label: __("GPS Gate User"),
                        fieldname: "gps_gate_user",
                        fieldtype: "Link",
                        options: "GPS Gate User",
                        reqd: 1
                    },
                    {
                        label: __("Date"),
                        fieldname: "date",
                        fieldtype: "Date",
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    }
                ],
                primary_action_label: __("Sync"),
                primary_action: function (values) {
                    d.hide();
                    frappe.call({
                        method: "gps_gate.gps_gate.doctype.gps_gate_track_point.gps_gate_track_point.sync_tracks_for_date",
                        args: {
                            gps_gate_user: values.gps_gate_user,
                            date: values.date
                        },
                        freeze: true,
                        freeze_message: __("Syncing track points from GPS Gate..."),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                let indicator = r.message.status === "success" ? "green" : "orange";
                                frappe.msgprint({
                                    title: __("Sync Complete"),
                                    message: r.message.message,
                                    indicator: indicator
                                });
                                listview.refresh();
                            }
                        }
                    });
                }
            });
            d.show();
        });
    },

    get_indicator: function (doc) {
        if (doc.is_valid) {
            return [__("Valid"), "green", "is_valid,=,1"];
        }
        return [__("Invalid"), "orange", "is_valid,=,0"];
    },

    formatters: {
        is_valid: function (value) {
            if (value) {
                return '<span class="indicator-pill green">' + __("Valid") + "</span>";
            }
            return '<span class="indicator-pill orange">' + __("Invalid") + "</span>";
        },
        speed: function (value) {
            return value ? (value + " km/h") : "0 km/h";
        }
    }
};
