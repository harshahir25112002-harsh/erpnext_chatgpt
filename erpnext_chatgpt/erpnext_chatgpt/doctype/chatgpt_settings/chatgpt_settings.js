// Copyright (c) 2026, Antigravity AI and contributors
// For license information, please see license.txt

frappe.ui.form.on('ChatGPT Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Test API Connection'), function() {
            frm.call({
                method: 'erpnext_chatgpt.api.test_connection',
                freeze: true,
                freeze_message: __('Testing connection to OpenAI...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint({
                            title: __('Connection Successful'),
                            indicator: 'green',
                            message: __('ChatGPT API connected successfully! Sample reply: <br><blockquote>' + r.message.sample + '</blockquote>')
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Connection Failed'),
                            indicator: 'red',
                            message: r.message ? r.message.error : __('Unknown error connecting to API.')
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

