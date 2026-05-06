// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings['GPS Gate Event Rule'] = {
    onload: function (listview) {
        // Sync Event Rules from GPS Gate button
        listview.page.add_inner_button(__('Sync Event Rules'), function () {
            frappe.confirm(
                __('This will fetch all event rules from GPS Gate and sync them to ERPNext. Continue?'),
                function () {
                    frappe.call({
                        method: 'gps_gate.apis.sync_events.sync_gps_gate_event_rules',
                        freeze: true,
                        freeze_message: __('Syncing event rules from GPS Gate...'),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                frappe.msgprint({
                                    title: __('Sync Complete'),
                                    message: __('Synced {0} event rules from GPS Gate', [r.message.synced_records]),
                                    indicator: 'green'
                                });
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        });
    },

    get_indicator: function (doc) {
        if (doc.is_enabled) {
            return [__('Enabled'), 'green', 'is_enabled,=,1'];
        } else {
            return [__('Disabled'), 'grey', 'is_enabled,=,0'];
        }
    }
};
