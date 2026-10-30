// Dedicated Full-Page ChatGPT Copilot
frappe.pages['chatgpt_copilot'].on_page_load = function (wrapper) {
  var page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __('ChatGPT Copilot'),
    single_column: true
  });

  let currentConvId = null;
  let conversations = [];

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
          <div class="text-center text-muted" style="margin-top: 100px;">
            <h4>${__('Welcome to ERPNext ChatGPT Copilot')}</h4>
            <p>${__('Ask any question about your ERP, workflows, financial summaries, or custom reports.')}</p>
          </div>
        </div>
        <div class="chatgpt-page-input-wrapper">
          <div class="chatgpt-page-input-box">
            <textarea id="page-input-field" placeholder="${__('Type your question or instruction... (Enter to send)')}"></textarea>
            <button class="chatgpt-page-send-btn" id="page-send-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            </button>
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
    container.find("#page-messages-area").html(`
      <div class="text-center text-muted" style="margin-top: 100px;">
        <h4>${__('New Chat Session')}</h4>
        <p>${__('Type below to begin chatting with ChatGPT.')}</p>
      </div>
    `);
  }

  function appendMessageUI(role, text) {
    const area = container.find("#page-messages-area");
    const isUser = role === "user";
    const avatar = isUser ? `<div class="chatgpt-avatar user-avatar">${frappe.user.first_name().charAt(0)}</div>` : `<div class="chatgpt-avatar ai-avatar">AI</div>`;
    const formatted = !isUser && typeof frappe.markdown === "function" ? frappe.markdown(text) : frappe.utils.escape_html(text);

    const msg = $(`
      <div class="chatgpt-page-msg ${isUser ? 'user' : 'assistant'}">
        ${avatar}
        <div class="chatgpt-page-bubble">${formatted}</div>
      </div>
    `);

    area.append(msg);
    area.scrollTop(area[0].scrollHeight);
  }

  function sendPageMessage() {
    const input = container.find("#page-input-field");
    const text = (input.val() || "").trim();
    if (!text) return;

    if (container.find("#page-messages-area h4").length > 0) {
      container.find("#page-messages-area").empty();
    }

    appendMessageUI("user", text);
    input.val("").css("height", "auto");

    // Add loading indicator
    const loading = $(`
      <div class="chatgpt-page-msg assistant" id="page-msg-loading">
        <div class="chatgpt-avatar ai-avatar">AI</div>
        <div class="chatgpt-page-bubble text-muted"><em>${__('ChatGPT is thinking...')}</em></div>
      </div>
    `).appendTo(container.find("#page-messages-area"));

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
          appendMessageUI("assistant", r.message.reply);
        }
      },
      error: function () {
        loading.remove();
        appendMessageUI("assistant", __("⚠️ An error occurred while communicating with OpenAI."));
      }
    });
  }

  // Bindings
  container.find("#page-new-chat-btn").on("click", startNewSession);
  container.find("#page-send-btn").on("click", sendPageMessage);
  container.find("#page-input-field").on("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPageMessage();
    }
  });

  loadConversations();

  // If opened with route parameter
  const route = frappe.get_route();
  if (frappe.route_options && frappe.route_options.conversation) {
    selectConversation(frappe.route_options.conversation);
  }
};

