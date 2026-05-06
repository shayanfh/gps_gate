// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings['GPS Gate User'] = {
    onload: function (listview) {
        // Sync GPS Gate Users button
        listview.page.add_inner_button(__('Sync GPS Gate Users'), function () {
            frappe.confirm(
                __('This will fetch all users from GPS Gate and sync them to ERPNext. Continue?'),
                function () {
                    frappe.call({
                        method: 'gps_gate.apis.sync_user.sync_gps_gate_users',
                        freeze: true,
                        freeze_message: __('Syncing GPS Gate users...'),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                let msg = __('Synced {0} of {1} users from GPS Gate',
                                    [r.message.synced_records, r.message.total_users]);

                                if (r.message.error_count) {
                                    msg += '<br><br>' + __('Errors: {0}', [r.message.error_count]);
                                    frappe.msgprint({
                                        title: __('Sync Completed with Errors'),
                                        message: msg,
                                        indicator: 'orange'
                                    });
                                } else {
                                    frappe.msgprint({
                                        title: __('Sync Success'),
                                        message: msg,
                                        indicator: 'green'
                                    });
                                }
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        });

    },

    get_indicator: function (doc) {
        // Show sync status indicator in list view
        if (doc.sync_status === 'Success') {
            return [__('Synced'), 'green', 'sync_status,=,Success'];
        } else if (doc.sync_status === 'Failed') {
            return [__('Sync Failed'), 'red', 'sync_status,=,Failed'];
        } else if (!doc.user_id) {
            return [__('Not Synced'), 'orange', 'user_id,=,'];
        }
        return [__('Unknown'), 'grey', ''];
    },

    formatters: {
        sync_status: function (value) {
            if (value === 'Success') {
                return '<span class="indicator-pill green">' + __('Synced') + '</span>';
            } else if (value === 'Failed') {
                return '<span class="indicator-pill red">' + __('Failed') + '</span>';
            }
            return value || '';
        }
    }
};
