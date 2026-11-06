// Dedicated Full-Page AI Copilot (Version-Agnostic v15/v16/v17, Filtered Routing & Invoice Confirmation)
frappe.pages['chatgpt_copilot'].on_page_load = function (wrapper) {
  var page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __('AI Copilot'),
    single_column: true
  });

  let currentConvId = null;
  let conversations = [];
  let speechRecognizer = null;
  let isListening = false;

  const starterCardsHtml = `
    <div class="text-center" style="margin-top: 15px; margin-bottom: 20px;">
      <h3 style="font-weight: 600; margin-bottom: 6px;">${__('Welcome to ERPNext AI Copilot')}</h3>
      <p class="text-muted" style="font-size: 13.5px;">${__('Ask questions, check live stock & balances, diagnose errors, or speak with voice.')}</p>
    </div>
    <div class="chatgpt-starter-grid">
      <div class="chatgpt-prompt-card" data-prompt="Show me my current stock balance across warehouses.">
        <strong>📦 ${__('Check Stock Balance')}</strong>
        <span>${__('Query warehouse quantities & projected stock.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="Show all unpaid sales invoices and total overdue customer balance.">
        <strong>💳 ${__('Customer Outstanding')}</strong>
        <span>${__('Review unpaid invoices & overdue amounts.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="Which supplier gives the lowest price based on past purchase orders?">
        <strong>🏭 ${__('Supplier Price Comparison')}</strong>
        <span>${__('Find the cheapest vendor from purchase history.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="Show all delayed Purchase Orders that have passed their expected delivery date.">
        <strong>⏳ ${__('Delayed Purchase Orders')}</strong>
        <span>${__('Track overdue deliveries from suppliers.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="What are our total vendor payables and current liquid bank balances?">
        <strong>💰 ${__('Vendor Payables & Cash Flow')}</strong>
        <span>${__('Summarize unpaid bills & bank liquidity.')}</span>
      </div>
      <div class="chatgpt-prompt-card" data-prompt="Diagnose validation errors on my recent documents.">
        <strong>🛠️ ${__('Error Diagnoser')}</strong>
        <span>${__('Inspect document validation & get step-by-step fix.')}</span>
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
          <div style="display: flex; align-items: center; gap: 10px;">
            <button class="chatgpt-action-pill" id="page-btn-briefing" title="${__('Run Morning Executive Briefing')}">
              🌅 ${__("Morning Briefing")}
            </button>
            <div class="text-muted small" id="page-token-counter"></div>
          </div>
        </div>
        <div class="chatgpt-main-messages" id="page-messages-area">
          ${starterCardsHtml}
        </div>
        <div class="chatgpt-page-input-wrapper">
          <div class="chatgpt-page-input-box">
            <button class="chatgpt-icon-input-btn" id="page-btn-attach" title="${__('Attach Invoice PDF/Image')}">📎</button>
            <button class="chatgpt-icon-input-btn" id="page-btn-mic" title="${__('Voice Input (Speak in English, Hindi, etc.)')}">🎙️</button>
            <textarea id="page-input-field" placeholder="${__('Ask a question or speak... (Enter to send, Shift+Enter for new line)')}"></textarea>
            <button class="chatgpt-page-send-btn" id="page-send-btn" title="${__('Send')}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            </button>
          </div>
          <div style="font-size: 11px; color: var(--text-muted, #888); text-align: center; margin-top: 6px;">
            🛡️ ${__('PII Masked')} • 🎙️ ${__('Voice Enabled')} • 📎 ${__('Invoice OCR')} • ⚡ ${__('Live ORM Tools')}
          </div>
        </div>
      </div>
    </div>
  `).appendTo(page.main);

  // Global Filtered Link Interceptor for Frappe v15, v16, v17
  container.on("click", ".chatgpt-page-bubble a", function (e) {
    const rawHref = $(this).attr("href");
    if (!rawHref) return;

    if (rawHref.includes("/app/") || rawHref.startsWith("app/")) {
      e.preventDefault();
      try {
        const urlObj = new URL(rawHref, window.location.origin);
        const pathParts = urlObj.pathname.replace(/^\/?app\/?/, "").split("/").filter(Boolean);
        
        // Pass query parameters to Frappe's route options so filters apply!
        const routeOptions = {};
        urlObj.searchParams.forEach(function (val, key) {
          routeOptions[key] = val;
        });

        frappe.route_options = routeOptions;
        frappe.set_route(pathParts);
      } catch (err) {
        window.location.href = rawHref;
      }
    }
  });

  // Voice Input (Speech Recognition with Permission Handling)
  function setupSpeechRecognition() {
    const SpeechAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechAPI) {
      container.find("#page-btn-mic").attr("title", __("Speech recognition not supported in this browser.")).css("opacity", 0.4);
      return;
    }

    speechRecognizer = new SpeechAPI();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = false;
    speechRecognizer.lang = 'en-IN';

    speechRecognizer.onstart = function () {
      isListening = true;
      container.find("#page-btn-mic").addClass("is-recording").attr("title", __("Listening... Speak now"));
      frappe.show_alert({ message: __("🎙️ Microphone active... Speak your question now"), indicator: "blue" });
    };

    speechRecognizer.onresult = function (event) {
      const transcript = event.results[0][0].transcript;
      const input = container.find("#page-input-field");
      const current = input.val();
      input.val(current ? current + " " + transcript : transcript).focus();
    };

    speechRecognizer.onerror = function (event) {
      stopListening();
      if (event.error === "not-allowed" || event.error === "permission-denied") {
        frappe.msgprint({
          title: __("Microphone Permission Required"),
          indicator: "orange",
          message: __("Please allow microphone access in your browser address bar to use voice input.")
        });
      } else if (event.error !== "no-speech") {
        frappe.show_alert({ message: __("Voice error: {0}", [event.error]), indicator: "orange" });
      }
    };

    speechRecognizer.onend = function () {
      stopListening();
    };
  }

  function toggleListening() {
    if (!speechRecognizer) {
      setupSpeechRecognition();
    }
    if (!speechRecognizer) return;

    if (isListening) {
      speechRecognizer.stop();
      stopListening();
    } else {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true }).then(function () {
          speechRecognizer.start();
        }).catch(function () {
          frappe.msgprint({
            title: __("Microphone Blocked"),
            indicator: "red",
            message: __("Please click the lock/settings icon in your browser address bar and allow Microphone access.")
          });
        });
      } else {
        speechRecognizer.start();
      }
    }
  }

  function stopListening() {
    isListening = false;
    container.find("#page-btn-mic").removeClass("is-recording").attr("title", __("Voice Input"));
  }

  // Invoice File Upload with Interactive Confirmation Card
  function openInvoiceUploader() {
    new frappe.ui.FileUploader({
      allow_multiple: false,
      restrictions: {
        allowed_file_types: [".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"]
      },
      on_success: function (file_doc) {
        frappe.show_alert({ message: __("Analyzing invoice with AI..."), indicator: "blue" });
        if (container.find(".chatgpt-starter-grid").length > 0) {
          container.find("#page-messages-area").empty();
        }
        appendMessageUI("user", `📎 ${__('Uploaded File')}: <b>${file_doc.file_name}</b>`);
        
        frappe.call({
          method: "erpnext_chatgpt.api.extract_invoice_and_draft",
          args: { file_url: file_doc.file_url },
          freeze: true,
          freeze_message: __("Analyzing file..."),
          callback: function (r) {
            if (!r.message) {
              appendMessageUI("assistant", "⚠️ " + __('No response from document extractor.'));
              return;
            }

            if (r.message.status === "preview_ready") {
              const data = r.message.parsed_data;
              const items = data.items || [];
              let itemsRows = items.map(it => `
                <tr>
                  <td>${frappe.utils.escape_html(it.item_code || 'Item')}</td>
                  <td style="text-align: right;">${it.qty || 1}</td>
                  <td style="text-align: right;">${it.rate || 0}</td>
                </tr>
              `).join('');

              const previewHtml = `
                <div style="background: var(--card-bg, #fff); border: 1px solid var(--border-color, #cbd5e1); border-radius: 8px; padding: 14px; margin-top: 6px;">
                  <h5 style="margin-top: 0; margin-bottom: 8px; font-weight: 600;">📄 ${__('Invoice Preview')} (${file_doc.file_name})</h5>
                  <div style="display: flex; gap: 20px; font-size: 13px; margin-bottom: 10px;">
                    <div><b>${__('Supplier')}:</b> ${frappe.utils.escape_html(data.supplier || 'Unknown')}</div>
                    <div><b>${__('Bill No')}:</b> ${frappe.utils.escape_html(data.bill_no || 'N/A')}</div>
                    <div><b>${__('Estimated Total')}:</b> ${data.total || 'Calculated on submit'}</div>
                  </div>
                  <table class="table table-bordered table-sm" style="font-size: 12px; margin-bottom: 12px;">
                    <thead><tr><th>Item</th><th style="text-align: right;">Qty</th><th style="text-align: right;">Rate</th></tr></thead>
                    <tbody>${itemsRows}</tbody>
                  </table>
                  <button class="btn btn-primary btn-sm confirm-draft-btn" data-json="${frappe.utils.escape_html(JSON.stringify(data))}">
                    ✓ ${__('Confirm & Create Draft Purchase Invoice')}
                  </button>
                </div>
              `;
              appendMessageUI("assistant", previewHtml);

              // Wire confirmation action
              container.find(".confirm-draft-btn").last().on("click", function () {
                const btn = $(this);
                btn.prop("disabled", true).text(__("Creating Draft..."));
                const parsedPayload = JSON.parse(btn.attr("data-json"));

                frappe.call({
                  method: "erpnext_chatgpt.api.confirm_and_create_draft_invoice",
                  args: { parsed_data: parsedPayload },
                  callback: function (res) {
                    if (res.message && res.message.status === "draft_created") {
                      btn.replaceWith(`
                        <div style="color: #10a37f; font-weight: 600; margin-top: 8px;">
                          ✓ ${res.message.message} <br>
                          <a href="${res.message.link}" style="color: #0284c7; text-decoration: underline;">${__('Open Draft')} ${res.message.invoice_name}</a>
                        </div>
                      `);
                    } else {
                      btn.prop("disabled", false).text(__("Retry"));
                      frappe.msgprint(res.message ? res.message.error : __("Failed to create draft invoice."));
                    }
                  }
                });
              });

            } else if (r.message.status === "warning") {
              appendMessageUI("assistant", `
                ℹ️ <b>${__('Document Analyzed')}:</b> ${r.message.file_name}<br><br>
                ${r.message.message}<br>
                <i>Tip: Please upload a commercial invoice or bill with line items.</i>
              `);
            }
          }
        });
      }
    });
  }

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

        setTimeout(function () {
          area.scrollTop(area[0].scrollHeight);
        }, 80);
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
    
    let formatted = "";
    if (isUser) {
      formatted = (text.startsWith("📎") || text.includes("<b>")) ? text : frappe.utils.escape_html(text);
    } else {
      formatted = typeof frappe.markdown === "function" ? frappe.markdown(text) : text;
    }

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

    if (container.find(".chatgpt-starter-grid").length > 0) {
      container.find("#page-messages-area").empty();
    }

    appendMessageUI("user", text);
    if (!customText) {
      input.val("").css("height", "auto");
    }

    const loading = $(`
      <div class="chatgpt-page-msg assistant" id="page-msg-loading">
        <div class="chatgpt-avatar ai-avatar">AI</div>
        <div class="chatgpt-msg-content-wrapper">
          <div class="chatgpt-page-bubble text-muted"><em>${__('AI is consulting live ERP database...')}</em></div>
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
  container.find("#page-btn-mic").on("click", toggleListening);
  container.find("#page-btn-attach").on("click", openInvoiceUploader);
  
  // Morning Briefing: Streams directly into chat!
  container.find("#page-btn-briefing").on("click", function () {
    frappe.show_alert({ message: __("Generating Executive Morning Briefing..."), indicator: "blue" });
    if (container.find(".chatgpt-starter-grid").length > 0) {
      container.find("#page-messages-area").empty();
    }
    appendMessageUI("user", "🌅 " + __("Generate today's executive morning briefing."));

    const loading = $(`
      <div class="chatgpt-page-msg assistant" id="page-msg-loading">
        <div class="chatgpt-avatar ai-avatar">AI</div>
        <div class="chatgpt-msg-content-wrapper">
          <div class="chatgpt-page-bubble text-muted"><em>${__('Analyzing financial positions & delayed orders...')}</em></div>
        </div>
      </div>
    `).appendTo(container.find("#page-messages-area"));
    container.find("#page-messages-area").scrollTop(container.find("#page-messages-area")[0].scrollHeight);

    frappe.call({
      method: "erpnext_chatgpt.api.trigger_manual_briefing",
      callback: function (r) {
        loading.remove();
        if (r.message && r.message.briefing_content) {
          appendMessageUI("assistant", r.message.briefing_content);
        } else {
          appendMessageUI("assistant", "⚠️ " + __('Could not synthesize morning briefing.'));
        }
      },
      error: function () {
        loading.remove();
        appendMessageUI("assistant", "⚠️ " + __('Error communicating with AI service.'));
      }
    });
  });

  container.find("#page-input-field").on("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPageMessage();
    }
  });

  setupSpeechRecognition();
  bindStarterCards();
  loadConversations();

  if (frappe.route_options && frappe.route_options.conversation) {
    selectConversation(frappe.route_options.conversation);
  }
};
