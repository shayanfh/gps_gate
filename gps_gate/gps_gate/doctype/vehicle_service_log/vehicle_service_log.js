// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Service Log", {
    setup(frm) {
        frm._from_schedule_button = false;
        frm._pending_prefill = null;
    },

    onload(frm) {
        // Detect if opened from "Create Service Log" button on a Schedule form
        if (frm.is_new() && frappe.route_options) {
            const init_st = frappe.route_options._init_service_type;
            const init_sched = frappe.route_options._init_schedule;
            if (init_st || init_sched) {
                frm._from_schedule_button = true;
                frm._pending_prefill = {
                    service_type: init_st,
                    schedule: init_sched
                };
                // Remove custom keys so Frappe doesn't try to set them as fields
                delete frappe.route_options._init_service_type;
                delete frappe.route_options._init_schedule;
            }
        }
    },

    vehicle(frm) {
        // Auto-populate service types and schedules for manual creation only
        // Skip if this form was opened from a Schedule's "Create Service Log" button
        if (!frm.is_new() || !frm.doc.vehicle || frm._from_schedule_button) return;

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Vehicle Service Schedule",
                filters: {
                    vehicle: frm.doc.vehicle,
                    status: ["in", ["Due Soon", "Overdue"]]
                },
                fields: ["name", "service_type"],
                order_by: "status asc, due_date asc"
            },
            callback(r) {
                frm.clear_table("service_type");
                frm.clear_table("schedule_reference");
                if (r.message && r.message.length) {
                    r.message.forEach(s => {
                        frm.add_child("service_type", { service_type: s.service_type });
                        frm.add_child("schedule_reference", { schedule_reference: s.name });
                    });
                }
                frm.refresh_field("service_type");
                frm.refresh_field("schedule_reference");
            }
        });
    },

    refresh(frm) {
        // Apply pre-fill from Schedule button (only on first refresh after onload)
        if (frm.is_new() && frm._pending_prefill) {
            const { service_type, schedule } = frm._pending_prefill;
            frm._pending_prefill = null;
            if (service_type) {
                frm.add_child("service_type", { service_type });
                frm.refresh_field("service_type");
            }
            if (schedule) {
                frm.add_child("schedule_reference", { schedule_reference: schedule });
                frm.refresh_field("schedule_reference");
            }
        }

        // Show summary headline
        const service_types = (frm.doc.service_type || [])
            .map(r => r.service_type)
            .filter(Boolean)
            .join(", ");
        if (frm.doc.vehicle && service_types && frm.doc.service_date) {
            frm.set_intro(
                __("{0} — {1} on {2}", [
                    frm.doc.vehicle,
                    service_types,
                    frappe.datetime.str_to_user(frm.doc.service_date)
                ]),
                "blue"
            );
        }

        // Show "View Schedule" button for each referenced schedule (submitted docs only)
        if (frm.doc.docstatus === 1 && frm.doc.schedule_reference && frm.doc.schedule_reference.length) {
            frm.doc.schedule_reference.forEach(row => {
                frm.add_custom_button(__("View Schedule: {0}", [row.schedule_reference]), () => {
                    frappe.set_route("Form", "Vehicle Service Schedule", row.schedule_reference);
                });
            });
        }
    }
});
