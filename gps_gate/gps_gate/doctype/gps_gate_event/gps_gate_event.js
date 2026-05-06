// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Event", {
    refresh(frm) {
        // Add Acknowledge button
        if (!frm.is_new() && !frm.doc.acknowledged) {
            frm.add_custom_button(__("Acknowledge"), function () {
                frm.set_value("acknowledged", 1);
                frm.save();
            }).addClass("btn-primary");
        }

        // Add View on Map button if coordinates exist
        if (frm.doc.latitude && frm.doc.longitude) {
            frm.add_custom_button(__("View on Map"), function () {
                window.open(
                    `https://www.google.com/maps?q=${frm.doc.latitude},${frm.doc.longitude}`,
                    "_blank"
                );
            });
        }

        // Show event severity indicator
        frm.trigger("show_severity_indicator");
    },

    show_severity_indicator(frm) {
        if (frm.is_new()) return;

        let color = "blue";
        if (frm.doc.severity === "Warning") {
            color = "orange";
        } else if (frm.doc.severity === "Critical") {
            color = "red";
        }

        let headline = frm.doc.event_rule_name || "Event";
        if (frm.doc.event_time) {
            headline += " - " + frappe.datetime.str_to_user(frm.doc.event_time);
        }

        frm.dashboard.set_headline(headline, color);

        if (!frm.doc.acknowledged) {
            frm.set_intro(__("This event has not been acknowledged yet."), "orange");
        }
    }
});
