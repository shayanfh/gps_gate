// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("GPS Gate Track Point", {
    refresh(frm) {
        if (frm.doc.latitude && frm.doc.longitude) {
            frm.add_custom_button(__("View on Map"), function () {
                window.open(
                    `https://www.google.com/maps?q=${frm.doc.latitude},${frm.doc.longitude}`,
                    "_blank"
                );
            });
        }
    }
});
