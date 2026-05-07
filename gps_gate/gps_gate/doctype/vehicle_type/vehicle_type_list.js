// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["Vehicle Type"] = {
    get_indicator: function (doc) {
        if (doc.is_active) {
            return [__("Active"), "green", "is_active,=,1"];
        }
        return [__("Inactive"), "red", "is_active,=,0"];
    },

    formatters: {
        is_active: function (value) {
            if (value) {
                return '<span class="indicator-pill green">' + __("Active") + "</span>";
            }
            return '<span class="indicator-pill red">' + __("Inactive") + "</span>";
        }
    }
};
