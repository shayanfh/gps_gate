// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings["Vehicle Service Type"] = {
    get_indicator: function (doc) {
        const color_map = {
            "Mechanical": "blue",
            "Legal": "orange",
            "Safety": "red",
            "Tire": "grey",
            "Oil": "green",
            "Other": "grey"
        };
        const color = color_map[doc.category] || "grey";
        return [__(doc.category || "Uncategorised"), color, "category,=," + doc.category];
    },

    formatters: {
        category: function (value) {
            if (!value) return "";
            const color_map = {
                "Mechanical": "blue",
                "Legal": "orange",
                "Safety": "red",
                "Tire": "grey",
                "Oil": "green",
                "Other": "grey"
            };
            const color = color_map[value] || "grey";
            return '<span class="indicator-pill ' + color + '">' + __(value) + "</span>";
        }
    }
};
