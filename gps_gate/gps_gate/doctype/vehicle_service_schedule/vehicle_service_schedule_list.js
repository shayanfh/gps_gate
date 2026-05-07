// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["Vehicle Service Schedule"] = {
    onload: function (listview) {
        listview.page.add_inner_button(__("Refresh All Status"), function () {
            frappe.confirm(
                __("Re-evaluate status for all open Vehicle Service Schedules?"),
                function () {
                    frappe.call({
                        method: "gps_gate.gps_gate.doctype.vehicle_service_schedule.vehicle_service_schedule.refresh_all_schedules",
                        freeze: true,
                        freeze_message: __("Refreshing schedules..."),
                        callback: function (r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __("Refresh Complete"),
                                    message: r.message.message,
                                    indicator: r.message.status === "success" ? "green" : "orange"
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
        const map = {
            "Overdue": ["Overdue", "red", "status,=,Overdue"],
            "Due Soon": ["Due Soon", "orange", "status,=,Due Soon"],
            "OK": ["OK", "green", "status,=,OK"],
            "Completed": ["Completed", "blue", "status,=,Completed"],
            "Cancelled": ["Cancelled", "grey", "status,=,Cancelled"]
        };
        return map[doc.status] || [__(doc.status || "Unknown"), "grey", "status,=," + doc.status];
    },

    formatters: {
        status: function (value) {
            const color_map = {
                "Overdue": "red",
                "Due Soon": "orange",
                "OK": "green",
                "Completed": "blue",
                "Cancelled": "grey"
            };
            const color = color_map[value] || "grey";
            return '<span class="indicator-pill ' + color + '">' + __(value || "") + "</span>";
        },

        due_odometer: function (value) {
            if (value == null || value === "") return "";
            return frappe.format(value, { fieldtype: "Float" }) + " km";
        },

        due_date: function (value) {
            if (!value) return "";
            return frappe.datetime.str_to_user(value);
        }
    }
};
