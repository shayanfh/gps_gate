// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Event Rule", {
    refresh(frm) {
        // Add View Events button
        if (!frm.is_new() && frm.doc.event_rule_id) {
            frm.add_custom_button(__("View Events"), function () {
                frappe.set_route("List", "GPS Gate Event", {
                    "event_rule": frm.doc.name
                });
            });
        }

        // Show sync status
        frm.trigger("show_sync_status");
    },

    show_sync_status(frm) {
        if (frm.is_new()) return;

        if (frm.doc.last_synced_on) {
            frm.dashboard.set_headline(
                __("Last synced: {0}", [frappe.datetime.prettyDate(frm.doc.last_synced_on)]),
                "green"
            );
        }
    }
});
