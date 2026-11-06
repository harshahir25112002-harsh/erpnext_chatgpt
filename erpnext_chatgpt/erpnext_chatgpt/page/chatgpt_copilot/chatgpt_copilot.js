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

  // Universal Link Interceptor for Frappe v15, v16, v17
  container.on("click", ".chatgpt-page-bubble a, .chatgpt-btn-open-doc", function (e) {
    if (e.ctrlKey || e.metaKey || e.which === 2) return;

    let rawHref = $(this).attr("href");
    if (!rawHref) return;

    const isInternal = rawHref.includes("/app") || 
                       rawHref.includes("/desk") || 
                       rawHref.startsWith("#") || 
                       rawHref.includes("itfarmer.in") ||
                       rawHref.includes(window.location.host);

    if (!isInternal && (rawHref.startsWith("http://") || rawHref.startsWith("https://"))) {
      $(this).attr("target", "_blank");
      return;
    }

    e.preventDefault();

    try {
      // 1. If it contains a hash (e.g. ...desk/chatgpt_copilot#/app/purchase-invoice/PINV-26-00016)
      // The real target route is ALWAYS after the '#'
      let routeString = rawHref;
      if (routeString.includes("#")) {
        routeString = routeString.split("#")[1];
      }

      // 2. If it's an absolute URL without hash
      if (routeString.startsWith("http://") || routeString.startsWith("https://")) {
        const u = new URL(routeString);
        routeString = u.pathname + u.search;
      }

      // 3. Extract query parameters
      let queryStr = "";
      if (routeString.includes("?")) {
        const qParts = routeString.split("?");
        routeString = qParts[0];
        queryStr = qParts[1];
      }

      // 4. Clean leading slashes and app/ or desk/ prefixes
      routeString = routeString.replace(/^\/+/, "");
      if (routeString.startsWith("app/")) {
        routeString = routeString.substring(4);
      } else if (routeString.startsWith("desk/")) {
        routeString = routeString.substring(5);
      }
      routeString = routeString.replace(/\/+$/, "");

      const routeParts = routeString.split("/").filter(Boolean).map(decodeURIComponent);

      // Parse filter options
      const routeOptions = {};
      if (queryStr) {
        const params = new URLSearchParams(queryStr);
        params.forEach(function (val, key) {
          routeOptions[key] = val;
        });
      }

      frappe.route_options = routeOptions;

      // Navigate smoothly within Desk
      if (routeParts.length > 0) {
        frappe.set_route(routeParts);
      } else {
        window.location.href = "/app/" + routeString + (queryStr ? "?" + queryStr : "");
      }
    } catch (err) {
      console.warn("Link navigation fallback:", err);
      window.location.href = rawHref;
    }
  });

  // Voice Input (Speech Recognition with Graceful Inline Permission Helper)
  function setupSpeechRecognition() {
    const SpeechAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechAPI) {
      container.find("#page-btn-mic").attr("title", __("Speech recognition not supported in this browser (Use Chrome/Edge).")).css("opacity", 0.4);
      return;
    }

    try {
      speechRecognizer = new SpeechAPI();
      speechRecognizer.continuous = false;
      speechRecognizer.interimResults = false;
      speechRecognizer.lang = navigator.language || 'en-IN';

      speechRecognizer.onstart = function () {
        isListening = true;
        container.find("#mic-permission-help").slideUp();
        container.find("#page-btn-mic").addClass("is-recording").attr("title", __("Listening... Speak now or click to stop"));
        frappe.show_alert({ message: __("🎙️ Microphone active... Speak your question now"), indicator: "blue" });
      };

      speechRecognizer.onresult = function (event) {
        if (event.results && event.results[0] && event.results[0][0]) {
          const transcript = event.results[0][0].transcript;
          const input = container.find("#page-input-field");
          const current = input.val();
          input.val(current ? current + " " + transcript : transcript).focus();
        }
      };

      speechRecognizer.onerror = function (event) {
        stopListening();
        if (event.error === "not-allowed" || event.error === "permission-denied") {
          showMicPermissionBanner();
        } else if (event.error === "audio-capture") {
          frappe.show_alert({ message: __("No microphone detected or microphone is in use by another app."), indicator: "orange" });
        } else if (event.error !== "no-speech") {
          frappe.show_alert({ message: __("Voice note: {0}", [event.error]), indicator: "orange" });
        }
      };

      speechRecognizer.onend = function () {
        stopListening();
      };
    } catch (err) {
      console.warn("Speech recognition setup error:", err);
    }
  }

  function showMicPermissionBanner() {
    let banner = container.find("#mic-permission-help");
    if (banner.length === 0) {
      banner = $(`
        <div id="mic-permission-help" class="chatgpt-mic-banner">
          <div class="banner-text">
            <strong>🔒 ${__('Microphone Access Needed')}:</strong> 
            ${__('Click the lock/settings icon next to the URL in your browser bar ➔ set Microphone to "Allow" ➔ click the 🎙️ mic button again.')}
          </div>
          <button class="banner-close-btn" title="${__('Dismiss')}">×</button>
        </div>
      `).insertBefore(container.find(".chatgpt-page-input-box"));
      banner.find(".banner-close-btn").on("click", function () {
        banner.slideUp();
      });
    }
    banner.slideDown();
  }

  function toggleListening() {
    if (!speechRecognizer) {
      setupSpeechRecognition();
    }
    if (!speechRecognizer) {
      frappe.show_alert({ message: __("Speech recognition is not supported in this browser. Please use Chrome or Edge."), indicator: "orange" });
      return;
    }

    if (isListening) {
      try {
        speechRecognizer.stop();
      } catch (e) {}
      stopListening();
    } else {
      try {
        speechRecognizer.start();
      } catch (err) {
        console.warn("Speech recognizer start error:", err);
      }
    }
  }

  function stopListening() {
    isListening = false;
    container.find("#page-btn-mic").removeClass("is-recording").attr("title", __("Voice Input"));
  }

  // Invoice File Upload with Interactive Confirmation Card (Table View & Real Data Auto-Creation)
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
        appendMessageUI("user", `📎 ${__('Uploaded Document')}: <b>${frappe.utils.escape_html(file_doc.file_name)}</b>`);
        
        frappe.call({
          method: "erpnext_chatgpt.api.extract_invoice_and_draft",
          args: { file_url: file_doc.file_url },
          freeze: true,
          freeze_message: __("Analyzing invoice line items..."),
          callback: function (r) {
            if (!r.message) {
              appendMessageUI("assistant", "⚠️ " + __('No response from document extractor.'));
              return;
            }

            if (r.message.status === "preview_ready") {
              const data = r.message.parsed_data;
              const items = data.items || [];
              const currency = data.currency || (frappe.defaults.get_global_default("currency") || "INR");

              const supBadge = data.supplier_exists 
                ? `<span class="chatgpt-status-badge badge-matched">✓ ${__('Existing Supplier')}</span>`
                : `<span class="chatgpt-status-badge badge-new">✨ ${__('Will Auto-Create Supplier')}</span>`;

              let itemsRows = items.map((it, idx) => {
                const qty = flt(it.qty, 1);
                const rate = flt(it.rate, 0);
                const lineTotal = flt(it.amount || (qty * rate));
                const itemBadge = it.item_exists
                  ? `<span class="chatgpt-status-badge badge-matched">✓ ${__('Existing Item')}</span>`
                  : `<span class="chatgpt-status-badge badge-new">✨ ${__('Will Auto-Create Item')}</span>`;

                return `
                  <tr>
                    <td style="text-align: center; color: var(--text-muted);">${idx + 1}</td>
                    <td>
                      <div style="font-weight: 500;">${frappe.utils.escape_html(it.item_code || it.item_name || 'Item')}</div>
                      <div style="margin-top: 2px;">${itemBadge}</div>
                    </td>
                    <td style="text-align: right; font-weight: 500;">${qty}</td>
                    <td style="text-align: right;">${rate ? format_currency(rate, currency) : '-'}</td>
                    <td style="text-align: right; font-weight: 600;">${format_currency(lineTotal, currency)}</td>
                  </tr>
                `;
              }).join('');

              const totalAmount = flt(data.total);

              const previewHtml = `
                <div class="chatgpt-invoice-preview-card">
                  <div class="chatgpt-invoice-header">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="font-size: 20px;">📄</span>
                      <div>
                        <h5 style="margin: 0; font-size: 14.5px; font-weight: 600;">${__('Invoice Verification & Preview')}</h5>
                        <div class="text-muted" style="font-size: 11.5px;">${frappe.utils.escape_html(file_doc.file_name)}</div>
                      </div>
                    </div>
                    <span class="chatgpt-status-badge badge-pending">⏳ ${__('Pending Confirmation')}</span>
                  </div>

                  <div class="chatgpt-invoice-meta-grid">
                    <div class="meta-item">
                      <span class="meta-label">${__('Supplier / Vendor')}</span>
                      <span class="meta-val">${frappe.utils.escape_html(data.supplier || 'Unknown Supplier')}</span>
                      <div>${supBadge}</div>
                    </div>
                    <div class="meta-item">
                      <span class="meta-label">${__('Bill / Invoice #')}</span>
                      <span class="meta-val">${frappe.utils.escape_html(data.bill_no || 'N/A')}</span>
                    </div>
                    <div class="meta-item">
                      <span class="meta-label">${__('Estimated Grand Total')}</span>
                      <span class="meta-val total-highlight">${totalAmount ? format_currency(totalAmount, currency) : 'Calculated on Submit'}</span>
                    </div>
                  </div>

                  <div class="chatgpt-invoice-table-box">
                    <table class="chatgpt-data-table">
                      <thead>
                        <tr>
                          <th style="width: 36px; text-align: center;">#</th>
                          <th>${__('Item Description')}</th>
                          <th style="width: 70px; text-align: right;">${__('Qty')}</th>
                          <th style="width: 105px; text-align: right;">${__('Rate')}</th>
                          <th style="width: 115px; text-align: right;">${__('Amount')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        ${itemsRows || `<tr><td colspan="5" class="text-center text-muted">${__('No line items found')}</td></tr>`}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td colspan="4" style="text-align: right; font-weight: 600;">${__('Total Amount')}:</td>
                          <td style="text-align: right; font-weight: 700; color: #10a37f;">${format_currency(totalAmount, currency)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  <div class="chatgpt-invoice-footer">
                    <button class="chatgpt-btn-confirm-draft" data-json="${frappe.utils.escape_html(JSON.stringify(data))}">
                      ✓ ${__('Confirm & Create Draft Purchase Invoice')}
                    </button>
                    <div class="chatgpt-invoice-notice">
                      💡 ${__('ERPNext will auto-create missing Supplier & Items with real extracted data — zero hardcoded fallbacks.')}
                    </div>
                  </div>
                </div>
              `;
              appendMessageUI("assistant", previewHtml);

              // Wire confirmation action
              container.find(".chatgpt-btn-confirm-draft").last().on("click", function () {
                const btn = $(this);
                const card = btn.closest(".chatgpt-invoice-preview-card");
                btn.prop("disabled", true).html(`⏳ ${__('Creating Draft Invoice & Registering Data...')}`);
                
                const parsedPayload = JSON.parse(btn.attr("data-json"));

                frappe.call({
                  method: "erpnext_chatgpt.api.confirm_and_create_draft_invoice",
                  args: { parsed_data: parsedPayload },
                  callback: function (res) {
                    if (res.message && res.message.status === "draft_created") {
                      card.find(".chatgpt-status-badge.badge-pending")
                        .removeClass("badge-pending")
                        .addClass("badge-matched")
                        .html(`✓ ${__('Draft Created')}`);
                      
                      btn.parent().html(`
                        <div class="chatgpt-draft-success-box">
                          <div style="font-weight: 600; font-size: 13.5px; color: #10a37f; margin-bottom: 6px;">
                            ${res.message.message}
                          </div>
                          <div style="margin-top: 10px;">
                            <a href="${res.message.link}" class="chatgpt-btn-open-doc">
                              📄 ${__('Open Draft Purchase Invoice')} ${res.message.invoice_name} ➔
                            </a>
                          </div>
                        </div>
                      `);
                    } else {
                      btn.prop("disabled", false).html(`⚠️ ${__('Retry Draft Creation')}`);
                      frappe.msgprint(res.message ? res.message.error : __("Failed to create draft invoice."));
                    }
                  }
                });
              });

            } else if (r.message.status === "warning") {
              appendMessageUI("assistant", `
                ℹ️ <b>${__('Document Analyzed')}:</b> ${frappe.utils.escape_html(r.message.file_name)}<br><br>
                ${frappe.utils.escape_html(r.message.message)}<br><br>
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
