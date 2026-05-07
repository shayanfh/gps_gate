// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["Vehicle Service Log"] = {
    get_indicator: function (doc) {
        if (doc.docstatus === 1) {
            return [__("Submitted"), "green", "docstatus,=,1"];
        } else if (doc.docstatus === 2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }
        return [__("Draft"), "grey", "docstatus,=,0"];
    },

    formatters: {
        cost: function (value) {
            if (value == null || value === "") return "";
            return frappe.format(value, { fieldtype: "Currency" });
        },

        service_odometer: function (value) {
            if (value == null || value === "") return "";
            return frappe.format(value, { fieldtype: "Float" }) + " km";
        }
    }
};
