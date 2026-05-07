// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["GPS Gate Trip Info"] = {
    onload: function (listview) {
        listview.page.add_inner_button(__("Sync Trips"), function () {
            let d = new frappe.ui.Dialog({
                title: __("Sync Trips from GPS Gate"),
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
                        method: "gps_gate.gps_gate.doctype.gps_gate_trip_info.gps_gate_trip_info.sync_trips_for_date",
                        args: {
                            gps_gate_user: values.gps_gate_user,
                            date: values.date
                        },
                        freeze: true,
                        freeze_message: __("Syncing trips from GPS Gate..."),
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
        if (doc.is_idle) {
            return [__("Idle"), "orange", "is_idle,=,1"];
        }
        return [__("Moving"), "blue", "is_idle,=,0"];
    },

    formatters: {
        is_idle: function (value) {
            if (value) {
                return '<span class="indicator-pill orange">' + __("Idle") + "</span>";
            }
            return '<span class="indicator-pill blue">' + __("Moving") + "</span>";
        },
        distance: function (value) {
            if (!value) return "—";
            return (value / 1000).toFixed(2) + " km";
        },
        duration: function (value) {
            if (!value) return "—";
            let mins = Math.floor(value / 60);
            return mins + " min";
        }
    }
};
