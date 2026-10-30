// Automatic AI Action Buttons on ERPNext DocType Forms
(function () {
  let templateCache = {};

  $(document).on("form-refresh", function (event, frm) {
    if (!frm || !frm.doc || frm.is_new()) return;

    const doctype = frm.doctype;

    // Check if templates already cached
    if (templateCache[doctype] !== undefined) {
      renderAiButtons(frm, templateCache[doctype]);
      return;
    }

    frappe.call({
      method: "erpnext_chatgpt.api.get_templates_for_doctype",
      args: { doctype: doctype },
      callback: function (r) {
        templateCache[doctype] = r.message || [];
        renderAiButtons(frm, templateCache[doctype]);
      }
    });
  });

  function renderAiButtons(frm, templates) {
    // 1. Add Default "✨ Ask AI about this document"
    frm.add_custom_button(__("Ask AI about this Doc"), function () {
      openFreeformDocPrompt(frm);
    }, __("✨ AI Actions"));

    // 2. Add any configured Prompt Templates
    if (templates && templates.length > 0) {
      templates.forEach(function (tpl) {
        frm.add_custom_button(__(tpl.btn_label || tpl.template_name), function () {
          executeTemplate(frm, tpl);
        }, __("✨ AI Actions"));
      });
    }
  }

  function executeTemplate(frm, tpl) {
    frappe.show_alert({
      message: __("Asking ChatGPT ({0})...", [tpl.template_name]),
      indicator: "blue"
    });

    frappe.call({
      method: "erpnext_chatgpt.api.run_prompt_template",
      args: {
        template_name: tpl.template_name,
        doc: JSON.stringify(frm.doc)
      },
      freeze: true,
      freeze_message: __("ChatGPT is processing {0}...", [tpl.template_name]),
      callback: function (r) {
        if (!r.message) return;
        const res = r.message;

        if (res.action_type === "Fill Field" && res.target_field) {
          frm.set_value(res.target_field, res.reply);
          frappe.show_alert({
            message: __("Field '{0}' updated by AI!", [res.target_field]),
            indicator: "green"
          });
        } else if (res.action_type === "Add Timeline Comment") {
          frm.timeline && frm.timeline.refresh();
          frappe.show_alert({
            message: __("AI response added to timeline."),
            indicator: "green"
          });
        } else {
          // Popup Dialog
          showAiResultDialog(tpl.template_name, res.reply);
        }
      }
    });
  }

  function openFreeformDocPrompt(frm) {
    const d = new frappe.ui.Dialog({
      title: __("✨ Ask AI about {0} #{1}", [frm.doctype, frm.doc.name]),
      fields: [
        {
          label: __("Your Question or Instruction"),
          fieldname: "prompt",
          fieldtype: "Small Text",
          reqd: 1,
          description: __("Example: 'Summarize key points', 'Draft an email response to this customer', or 'Check if fields look consistent'.")
        }
      ],
      primary_action_label: __("Ask ChatGPT"),
      primary_action: function (values) {
        d.hide();
        frappe.call({
          method: "erpnext_chatgpt.api.chat",
          args: {
            message: values.prompt,
            reference_doctype: frm.doctype,
            reference_name: frm.doc.name
          },
          freeze: true,
          freeze_message: __("Consulting ChatGPT..."),
          callback: function (r) {
            if (r.message && r.message.reply) {
              showAiResultDialog(__("AI Answer for {0}", [frm.doc.name]), r.message.reply);
            }
          }
        });
      }
    });
    d.show();
  }

  function showAiResultDialog(title, content) {
    const rendered = typeof frappe.markdown === "function" ? frappe.markdown(content) : content;
    const d = new frappe.ui.Dialog({
      title: title,
      fields: [
        {
          fieldtype: "HTML",
          fieldname: "response_html",
          options: `<div style="max-height: 400px; overflow-y: auto; padding: 12px; background: var(--chatgpt-card-bg, #f8f9fa); border-radius: 8px; line-height: 1.6;">${rendered}</div>`
        }
      ],
      primary_action_label: __("Copy to Clipboard"),
      primary_action: function () {
        frappe.utils.copy_to_clipboard(content);
        frappe.show_alert({ message: __("Copied to clipboard!"), indicator: "green" });
      }
    });
    d.show();
  }
})();

