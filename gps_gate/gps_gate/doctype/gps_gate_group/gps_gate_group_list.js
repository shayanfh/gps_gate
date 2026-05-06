// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings['GPS Gate Group'] = {
    onload: function (listview) {
        // Sync Groups from GPS Gate button
        listview.page.add_inner_button(__('Sync Groups'), function () {
            frappe.confirm(
                __('This will fetch all groups from GPS Gate and sync them to ERPNext. Continue?'),
                function () {
                    frappe.call({
                        method: 'gps_gate.apis.sync_groups.sync_gps_gate_groups',
                        freeze: true,
                        freeze_message: __('Syncing groups from GPS Gate...'),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                let msg = __('Synced {0} groups from GPS Gate', [r.message.synced_records]);
                                if (r.message.error_count) {
                                    msg += '<br>' + __('Errors: {0}', [r.message.error_count]);
                                }
                                frappe.msgprint({
                                    title: __('Sync Complete'),
                                    message: msg,
                                    indicator: r.message.error_count ? 'orange' : 'green'
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
        if (doc.group_id && doc.is_created_on_gps_gate) {
            if (doc.sync_status === 'Failed') {
                return [__('Sync Failed'), 'red', 'sync_status,=,Failed'];
            }
            return [__('Synced'), 'green', 'is_created_on_gps_gate,=,1'];
        } else {
            return [__('Not Synced'), 'orange', 'is_created_on_gps_gate,=,0'];
        }
    }
};
