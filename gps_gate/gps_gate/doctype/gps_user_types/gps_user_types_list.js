// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt

frappe.listview_settings['GPS User Types'] = {
    onload: function (listview) {
        // Sync User Types from GPS Gate button
        listview.page.add_inner_button(__('Sync User Types'), function () {
            frappe.confirm(
                __('This will fetch all user types from GPS Gate and sync them to ERPNext. Continue?'),
                function () {
                    frappe.call({
                        method: 'gps_gate.apis.sync_user.get_gps_gate_user_types1',
                        freeze: true,
                        freeze_message: __('Syncing user types from GPS Gate...'),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                let msg = `
                                    <b>Created:</b> ${r.message.created || 0}<br>
                                    <b>Updated:</b> ${r.message.updated || 0}<br>
                                    <b>Total:</b> ${r.message.total || 0}
                                `;

                                if (r.message.error_count) {
                                    msg += `<br><b>Errors:</b> ${r.message.error_count}`;
                                }

                                frappe.msgprint({
                                    title: __('GPS Gate User Types Sync Complete'),
                                    message: msg,
                                    indicator: r.message.status === 'success' ? 'green' : 'orange'
                                });

                                listview.refresh();
                            }
                        },
                        error: function (r) {
                            frappe.msgprint({
                                title: __('Sync Failed'),
                                message: __('Unable to sync user types from GPS Gate. Check Error Log for details.'),
                                indicator: 'red'
                            });
                        }
                    });
                }
            );
        });
    },

    get_indicator: function (doc) {
        // Show sync status indicator in list view
        if (doc.is_synced && doc.sync_status === 'Success') {
            return [__('Synced'), 'green', 'sync_status,=,Success'];
        } else if (doc.sync_status === 'Failed') {
            return [__('Sync Failed'), 'red', 'sync_status,=,Failed'];
        } else if (!doc.is_synced) {
            return [__('Not Synced'), 'orange', 'is_synced,=,0'];
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
        },
        is_synced: function (value) {
            if (value) {
                return '<span class="indicator-pill green">' + __('Yes') + '</span>';
            }
            return '<span class="indicator-pill orange">' + __('No') + '</span>';
        }
    }
};
