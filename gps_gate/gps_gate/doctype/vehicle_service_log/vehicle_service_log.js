// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Service Log", {
    refresh(frm) {
        // Show summary headline
        if (frm.doc.vehicle && frm.doc.service_type && frm.doc.service_date) {
            frm.set_intro(
                __("{0} — {1} on {2}", [
                    frm.doc.vehicle,
                    frm.doc.service_type,
                    frappe.datetime.str_to_user(frm.doc.service_date)
                ]),
                "blue"
            );
        }

        // Show View Schedule button if submitted and schedule_reference exists
        if (frm.doc.docstatus === 1 && frm.doc.schedule_reference) {
            frm.add_custom_button(__("View Schedule"), function () {
                frappe.set_route("Form", "Vehicle Service Schedule", frm.doc.schedule_reference);
            });
        }
    }
});
