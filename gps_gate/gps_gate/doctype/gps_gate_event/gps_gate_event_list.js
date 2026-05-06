// Copyright (c) 2026, Naqeeb Khan and contributors
// For license information, please see license.txt
frappe.listview_settings['GPS Gate Event'] = {
    onload: function (listview) {
        // Sync Events from GPS Gate button
        listview.page.add_inner_button(__('Sync Events'), function () {
            // Show dialog to select date and optional filters
            let d = new frappe.ui.Dialog({
                title: __('Sync Events from GPS Gate'),
                fields: [
                    {
                        label: __('From Date'),
                        fieldname: 'from_date',
                        fieldtype: 'Date',
                        default: frappe.datetime.get_today(),
                        reqd: 1,
                        description: __('Select the date to fetch events for (format: YYYY-MM-DD)')
                    },
                    {
                        label: __('To Date'),
                        fieldname: 'to_date',
                        fieldtype: 'Date',
                        default: frappe.datetime.get_today(),
                        reqd: 1,
                        description: __('Select the date to fetch events for (format: YYYY-MM-DD)')
                    },
                    // {
                    //     fieldtype: 'Column Break'
                    // },
                    // {
                    //     label: __('Event Rule'),
                    //     fieldname: 'event_rule',
                    //     fieldtype: 'Link',
                    //     options: 'GPS Gate Event Rule',
                    //     description: __('Optional: Filter by specific event rule')
                    // },
                    // {
                    //     label: __('GPS Gate User'),
                    //     fieldname: 'gps_gate_user',
                    //     fieldtype: 'Link',
                    //     options: 'GPS Gate User',
                    //     description: __('Optional: Filter by specific user')
                    // }
                ],
                primary_action_label: __('Sync Events'),
                primary_action: function (values) {
                    d.hide();

                    frappe.call({
                        method: 'gps_gate.apis.sync_events.sync_gps_gate_events',
                        args: {
                            from_date: values.from_date,
                            to_date: values.to_date,
                            event_rule: values.event_rule,
                            gps_gate_user: values.gps_gate_user
                        },
                        freeze: true,
                        freeze_message: __('Syncing events from GPS Gate...'),
                        callback: function (r) {
                            if (!r.exc && r.message) {
                                let msg = __('Synced events from GPS Gate for date {1} to {2}', [r.message.synced_records, values.from_date, values.to_date]);
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
            });

            d.show();
        });

        // Acknowledge Selected button
        listview.page.add_inner_button(__('Acknowledge Selected'), function () {
            let selected = listview.get_checked_items();
            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one event to acknowledge.'));
                return;
            }

            frappe.confirm(
                __('Acknowledge {0} selected events?', [selected.length]),
                function () {
                    frappe.call({
                        method: 'gps_gate.apis.sync_events.acknowledge_events',
                        args: {
                            event_names: selected.map(e => e.name)
                        },
                        freeze: true,
                        freeze_message: __('Acknowledging events...'),
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.show_alert({
                                    message: __('Events acknowledged'),
                                    indicator: 'green'
                                });
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        }, __('Actions'));
    },

    get_indicator: function (doc) {
        if (doc.severity === 'Critical') {
            return [__('Critical'), 'red', 'severity,=,Critical'];
        } else if (doc.severity === 'Warning') {
            return [__('Warning'), 'orange', 'severity,=,Warning'];
        } else if (doc.acknowledged) {
            return [__('Acknowledged'), 'green', 'acknowledged,=,1'];
        } else {
            return [__('New'), 'blue', 'acknowledged,=,0'];
        }
    },

    formatters: {
        acknowledged: function (value) {
            if (value) {
                return '<span class="indicator-pill green">' + __('Yes') + '</span>';
            }
            return '<span class="indicator-pill orange">' + __('No') + '</span>';
        },
        severity: function (value) {
            let color = 'blue';
            if (value === 'Warning') color = 'orange';
            if (value === 'Critical') color = 'red';
            return '<span class="indicator-pill ' + color + '">' + (value || 'Info') + '</span>';
        }
    }
};
