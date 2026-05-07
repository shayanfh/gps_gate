// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Type", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Generate Schedules"), function () {
                frappe.call({
                    method: "gps_gate.gps_gate.doctype.vehicle_type.vehicle_type.generate_schedules",
                    args: {
                        docname: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Generating schedules..."),
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __("Schedules Generated"),
                                message: r.message.message,
                                indicator: r.message.status === "success" ? "green" : "orange"
                            });
                        }
                    }
                });
            }, __("GPS Gate"));
        }
    }
});
