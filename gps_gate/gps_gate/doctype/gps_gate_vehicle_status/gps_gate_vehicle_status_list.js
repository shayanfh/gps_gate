// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["GPS Gate Vehicle Status"] = {
    onload: function (listview) {
        listview.page.add_inner_button(__("Sync All Vehicle Status"), function () {
            frappe.confirm(
                __("Fetch the latest status for all vehicles from GPS Gate? This will overwrite existing records."),
                function () {
                    frappe.call({
                        method: "gps_gate.gps_gate.doctype.gps_gate_vehicle_status.gps_gate_vehicle_status.sync_all_vehicle_status",
                        freeze: true,
                        freeze_message: __("Fetching vehicle statuses from GPS Gate..."),
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
            );
        });
    },

    get_indicator: function (doc) {
        if (doc.online_status === "Online") {
            return [__("Online"), "green", "online_status,=,Online"];
        } else if (doc.online_status === "Offline") {
            return [__("Offline"), "red", "online_status,=,Offline"];
        }
        return [__("Unknown"), "grey", ""];
    },

    formatters: {
        online_status: function (value) {
            if (value === "Online") {
                return '<span class="indicator-pill green">' + __("Online") + "</span>";
            } else if (value === "Offline") {
                return '<span class="indicator-pill red">' + __("Offline") + "</span>";
            }
            return value || "";
        },
        speed: function (value) {
            return value ? (value + " km/h") : "—";
        }
    }
};
