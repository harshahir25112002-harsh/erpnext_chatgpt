// Copyright (c) 2026, Antigravity AI and contributors
// For license information, please see license.txt

frappe.ui.form.on('AI Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Test Provider Connection'), function() {
            frm.call({
                method: 'erpnext_chatgpt.api.test_connection',
                freeze: true,
                freeze_message: __('Testing connection to AI provider...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint({
                            title: __('Connection Verified'),
                            indicator: 'green',
                            message: __('Successfully connected to {0} ({1})! Sample reply:<br><blockquote>{2}</blockquote>Latency: {3}s', [
                                frm.doc.provider,
                                frm.doc.model,
                                r.message.sample,
                                r.message.latency || 0.5
                            ])
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Connection Failed'),
                            indicator: 'red',
                            message: r.message ? r.message.error : __('Failed to connect.')
                        });
                    }
                }
            });
        }).addClass('btn-primary');
    },

    test_connection_btn: function(frm) {
        frm.trigger('refresh');
    }
});

