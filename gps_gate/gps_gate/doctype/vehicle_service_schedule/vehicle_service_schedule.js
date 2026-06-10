// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Service Schedule", {
    refresh(frm) {
        frm.trigger("show_status_indicator");

        if (!frm.is_new()) {
            // Mark Cancelled button — only if not already Completed or Cancelled
            frm.add_custom_button(__("Run Maintenance Job"), function () {
                frappe.call({
                    method: "gps_gate.apis.maintenance_jobs.hourly_vehicle_maintenance_job",
                    freeze: true,
                    freeze_message: __("Running maintenance job..."),
                    callback: function () {
                        frappe.show_alert({
                            message: __("Maintenance job completed"),
                            indicator: "green"
                        });
                        frm.reload_doc();
                    }
                });
            }, __("Actions"));

            if (!["Completed", "Cancelled"].includes(frm.doc.status)) {
                frm.add_custom_button(__("Mark Cancelled"), function () {
                    frappe.confirm(
                        __("Are you sure you want to cancel this schedule?"),
                        function () {
                            frappe.call({
                                method: "gps_gate.gps_gate.doctype.vehicle_service_schedule.vehicle_service_schedule.mark_cancelled",
                                args: { docname: frm.doc.name },
                                freeze: true,
                                freeze_message: __("Cancelling..."),
                                callback: function (r) {
                                    if (r.message && r.message.status === "success") {
                                        frappe.show_alert({
                                            message: __("Schedule marked as Cancelled"),
                                            indicator: "grey"
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }
                    );
                });
            }

            // Create Service Log button — available for all statuses except Cancelled
           if (frm.doc.status !== "Cancelled") {
                frm.add_custom_button(__("Create Service Log"), function () {
                    const payload = {
                        vehicle: frm.doc.vehicle,
                        service_type: frm.doc.service_type,
                        schedule: frm.doc.name
                    };


                    sessionStorage.setItem(
                        "vehicle_service_log_prefill",
                        JSON.stringify(payload)
                    );

                    frappe.new_doc("Vehicle Service Log", {
                        vehicle: frm.doc.vehicle
                    });
                });
            }
                    }
                },

    show_status_indicator(frm) {
        const status_color = {
            "Overdue": "red",
            "Due Soon": "orange",
            "OK": "green",
            "Completed": "blue",
            "Cancelled": "grey"
        };
        const color = status_color[frm.doc.status] || "grey";
        frm.page.set_indicator(__(frm.doc.status || "Unknown"), color);
    }
});
