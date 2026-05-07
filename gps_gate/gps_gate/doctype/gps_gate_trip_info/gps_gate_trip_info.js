// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Trip Info", {
    refresh(frm) {
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

    show_trip_summary(frm) {
        if (frm.is_new()) return;

        let parts = [];
        if (frm.doc.distance) {
            parts.push(__("Distance: {0} m", [frm.doc.distance]));
        }
        if (frm.doc.duration) {
            let mins = Math.floor(frm.doc.duration / 60);
            parts.push(__("Duration: {0} min", [mins]));
        }
        if (frm.doc.max_speed) {
            parts.push(__("Max Speed: {0}", [frm.doc.max_speed]));
        }

        if (parts.length) {
            frm.dashboard.set_headline(parts.join("  |  "), "blue");
        }
    }
});
