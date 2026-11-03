// Dedicated Full-Page AI Copilot (Enhanced UI & UX)
frappe.pages['chatgpt_copilot'].on_page_load = function (wrapper) {
  var page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __('AI Copilot'),
    single_column: true
  });

  let currentConvId = null;
  let conversations = [];

  const starterCardsHtml = `
    <div class="text-center" style="margin-top: 25px; margin-bottom: 20px;">
      <h3 style="font-weight: 600; margin-bottom: 6px;">${__('Welcome to ERPNext AI Copilot')}</h3>
      <p class="text-muted" style="font-size: 13.5px;">${__('Ask questions, query live ERP stock & balances, or draft business communications.')}</p>
    </div>
    <div class="chatgpt-starter-grid">
      <div class="chatgpt-prompt-card" data-prompt="What is the current stock balance and available quantity for item ITEM-001?">
        <strong>📦 ${__('Check Item Stock')}</strong>
        <span>${__('Query warehouse quantities and projected balance for any item code.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="What is the total outstanding balance and overdue amount for customer?">
        <strong>💳 ${__('Customer Outstanding')}</strong>
        <span>${__('Review unpaid sales invoices and overdue amounts for a client.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="Summarize total sales orders and revenue over the last 3 months.">
        <strong>📊 ${__('3-Month Sales Summary')}</strong>
        <span>${__('Aggregate sales order counts and revenue trends.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="Draft a polite but firm payment reminder email for an overdue invoice.">
        <strong>✉️ ${__('Draft Payment Reminder')}</strong>
        <span>${__('Compose a professional collection notice for outstanding dues.')}</span>
      </div>
    </div>
  `;

  const container = $(`
    <div class="chatgpt-page-layout">
      <div class="chatgpt-page-sidebar">
        <div class="chatgpt-sidebar-header">
          <button class="chatgpt-new-chat-btn" id="page-new-chat-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
            <span>${__('New Chat')}</span>
          </button>
        </div>
        <div class="chatgpt-conversations-list" id="page-conv-list"></div>
      </div>
      <div class="chatgpt-page-main">
        <div class="chatgpt-main-header">
          <div class="chatgpt-main-title" id="page-main-title">${__('New Conversation')}</div>
          <div class="text-muted small" id="page-token-counter"></div>
        </div>
        <div class="chatgpt-main-messages" id="page-messages-area">
          ${starterCardsHtml}
        </div>
        <div class="chatgpt-page-input-wrapper">
          <div class="chatgpt-page-input-box">
            <textarea id="page-input-field" placeholder="${__('Type your question or request... (Press Enter to send, Shift+Enter for new line)')}"></textarea>
            <button class="chatgpt-page-send-btn" id="page-send-btn" title="${__('Send')}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            </button>
          </div>
          <div style="font-size: 11px; color: var(--text-muted, #888); text-align: center; margin-top: 6px;">
            🛡️ ${__('PII Masked')} • ${__('Read-Only Tools')} • ${__('Enterprise Budget Protected')}
          </div>
        </div>
      </div>
    </div>
  `).appendTo(page.main);

  function loadConversations() {
    frappe.call({
      method: "erpnext_chatgpt.api.get_user_conversations",
      callback: function (r) {
        conversations = r.message || [];
        renderConversationList();
      }
    });
  }

  function renderConversationList() {
    const list = container.find("#page-conv-list");
    list.empty();
    if (conversations.length === 0) {
      list.append(`<div class="text-muted small text-center p-3">${__('No conversations yet')}</div>`);
      return;
    }

    conversations.forEach(function (c) {
      const activeClass = c.name === currentConvId ? "active" : "";
      const item = $(`
        <div class="chatgpt-conv-item ${activeClass}" data-id="${c.name}">
          <span class="chatgpt-conv-title">${frappe.utils.escape_html(c.title || c.name)}</span>
          <button class="chatgpt-conv-delete" title="${__('Delete Chat')}">×</button>
        </div>
      `);

      item.on("click", function (e) {
        if ($(e.target).hasClass("chatgpt-conv-delete")) {
          e.stopPropagation();
          deleteConv(c.name);
          return;
        }
        selectConversation(c.name);
      });

      list.append(item);
    });
  }

  function selectConversation(convId) {
    currentConvId = convId;
    renderConversationList();

    frappe.call({
      method: "erpnext_chatgpt.api.get_conversation_details",
      args: { conversation_id: convId },
      callback: function (r) {
        if (!r.message) return;
        const data = r.message;
        container.find("#page-main-title").text(data.title || data.name);
        container.find("#page-token-counter").text(data.total_tokens ? `${data.total_tokens} ${__('tokens used')}` : "");
        
        const area = container.find("#page-messages-area");
        area.empty();

        (data.messages || []).forEach(function (m) {
          appendMessageUI(m.role, m.content);
        });
      }
    });
  }

  function deleteConv(convId) {
    frappe.confirm(__('Are you sure you want to delete this chat session?'), function () {
      frappe.call({
        method: "erpnext_chatgpt.api.delete_conversation",
        args: { conversation_id: convId },
        callback: function () {
          if (currentConvId === convId) {
            startNewSession();
          }
          loadConversations();
        }
      });
    });
  }

  function startNewSession() {
    currentConvId = null;
    renderConversationList();
    container.find("#page-main-title").text(__('New Conversation'));
    container.find("#page-token-counter").text("");
    container.find("#page-messages-area").html(starterCardsHtml);
    bindStarterCards();
  }

  function appendMessageUI(role, text, meta) {
    const area = container.find("#page-messages-area");
    const isUser = role === "user";
    const userInitial = (frappe.session.user_fullname || frappe.session.user || "U").charAt(0).toUpperCase();
    const avatar = isUser ? `<div class="chatgpt-avatar user-avatar">${userInitial}</div>` : `<div class="chatgpt-avatar ai-avatar">AI</div>`;
    const formatted = !isUser && typeof frappe.markdown === "function" ? frappe.markdown(text) : frappe.utils.escape_html(text);

    let actionsHtml = "";
    if (!isUser) {
      actionsHtml = `
        <div class="chatgpt-msg-meta">
          <button class="chatgpt-action-pill copy-btn">📋 ${__('Copy')}</button>
          ${meta && meta.log_id ? `
            <button class="chatgpt-action-pill fb-up-btn" data-log="${meta.log_id}">👍</button>
            <button class="chatgpt-action-pill fb-down-btn" data-log="${meta.log_id}">👎</button>
          ` : ""}
          ${meta && meta.tokens ? `<span>⚡ ${meta.tokens} tokens</span>` : ""}
        </div>
      `;
    }

    const msg = $(`
      <div class="chatgpt-page-msg ${isUser ? 'user' : 'assistant'}">
        ${avatar}
        <div class="chatgpt-msg-content-wrapper">
          <div class="chatgpt-page-bubble">${formatted}</div>
          ${actionsHtml}
        </div>
      </div>
    `);

    // Copy Action
    msg.find(".copy-btn").on("click", function () {
      frappe.utils.copy_to_clipboard(text);
      $(this).text("✓ " + __('Copied!'));
      const btn = $(this);
      setTimeout(() => btn.html("📋 " + __('Copy')), 2000);
    });

    // Feedback Actions
    msg.find(".fb-up-btn").on("click", function () {
      submitFeedback(meta.log_id, "Thumbs Up", $(this));
    });
    msg.find(".fb-down-btn").on("click", function () {
      submitFeedback(meta.log_id, "Thumbs Down", $(this));
    });

    area.append(msg);
    area.scrollTop(area[0].scrollHeight);
  }

  function submitFeedback(logId, rating, btn) {
    frappe.call({
      method: "erpnext_chatgpt.api.submit_feedback",
      args: { log_id: logId, feedback: rating },
      callback: function () {
        btn.parent().find(".fb-up-btn, .fb-down-btn").prop("disabled", true).css("opacity", 0.5);
        frappe.show_alert({ message: __("Feedback saved: {0}", [rating]), indicator: "green" });
      }
    });
  }

  function sendPageMessage(customText) {
    const input = container.find("#page-input-field");
    const text = (customText || input.val() || "").trim();
    if (!text) return;

    // Remove starter cards if present
    if (container.find(".chatgpt-starter-grid").length > 0) {
      container.find("#page-messages-area").empty();
    }

    appendMessageUI("user", text);
    if (!customText) {
      input.val("").css("height", "auto");
    }

    // Add loading indicator
    const loading = $(`
      <div class="chatgpt-page-msg assistant" id="page-msg-loading">
        <div class="chatgpt-avatar ai-avatar">AI</div>
        <div class="chatgpt-msg-content-wrapper">
          <div class="chatgpt-page-bubble text-muted"><em>${__('AI is processing...')}</em></div>
        </div>
      </div>
    `).appendTo(container.find("#page-messages-area"));
    container.find("#page-messages-area").scrollTop(container.find("#page-messages-area")[0].scrollHeight);

    frappe.call({
      method: "erpnext_chatgpt.api.chat",
      args: {
        message: text,
        conversation_id: currentConvId
      },
      callback: function (r) {
        loading.remove();
        if (r.message && r.message.reply) {
          if (!currentConvId) {
            currentConvId = r.message.conversation_id;
            loadConversations();
          }
          container.find("#page-main-title").text(r.message.title);
          appendMessageUI("assistant", r.message.reply, {
            log_id: r.message.log_id,
            tokens: r.message.tokens
          });
        }
      },
      error: function () {
        loading.remove();
        appendMessageUI("assistant", __("⚠️ An error occurred while communicating with the AI service."));
      }
    });
  }

  function bindStarterCards() {
    container.find(".chatgpt-prompt-card").on("click", function () {
      const prompt = $(this).attr("data-prompt");
      container.find("#page-input-field").val(prompt).focus();
    });
  }

  // Bindings
  container.find("#page-new-chat-btn").on("click", startNewSession);
  container.find("#page-send-btn").on("click", () => sendPageMessage());
  container.find("#page-input-field").on("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPageMessage();
    }
  });

  bindStarterCards();
  loadConversations();

  // If opened with route parameter
  const route = frappe.get_route();
  if (frappe.route_options && frappe.route_options.conversation) {
    selectConversation(frappe.route_options.conversation);
  }
};
