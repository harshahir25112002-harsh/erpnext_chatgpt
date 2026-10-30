// Copyright (c) 2026, Antigravity AI and contributors
// For license information, please see license.txt

frappe.ui.form.on('ChatGPT Conversation', {
    refresh: function(frm) {
        frm.add_custom_button(__('Open in Copilot Page'), function() {
            frappe.set_route('chatgpt_copilot', { conversation: frm.doc.name });
        });
    }
});

