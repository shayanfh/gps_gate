// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Vehicle Status", {
    refresh(frm) {
        if (frm.doc.latitude && frm.doc.longitude) {
            frm.add_custom_button(__("View on Map"), function () {
                window.open(
                    `https://www.google.com/maps?q=${frm.doc.latitude},${frm.doc.longitude}`,
                    "_blank"
                );
            });
        }

        frm.trigger("show_status_indicator");
    },

    show_status_indicator(frm) {
        if (frm.is_new()) return;

        let color = frm.doc.online_status === "Online" ? "green" : "red";
        let headline = frm.doc.user_name || frm.doc.gps_gate_user;

        if (frm.doc.device_time) {
            headline += " — " + frappe.datetime.str_to_user(frm.doc.device_time);
        }

        frm.dashboard.set_headline(headline, color);
    }
});
