// ERPNext ChatGPT Copilot Widget (Bulletproof & Isolated)
(function () {
  let activeConversationId = null;
  let isSending = false;

  function safeInit() {
    try {
      initChatGPTWidget();
    } catch (err) {
      console.warn("[AI Copilot] Safe initialization caught error (Desk unaffected):", err);
    }
  }

  function initChatGPTWidget() {
    if (document.getElementById("chatgpt-launcher-btn")) return;

    // 1. Create Floating Button
    const launcher = document.createElement("button");
    launcher.id = "chatgpt-launcher-btn";
    launcher.title = "Ask AI Copilot (Ctrl+Shift+K)";
    launcher.innerHTML = `
      <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor">
        <path d="M12 2C6.477 2 2 6.477 2 12c0 1.821.487 3.53 1.338 5L2 22l5.223-1.282A9.957 9.957 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2zm0 18a7.95 7.95 0 01-4.223-1.205l-.303-.18-3.11.764.786-3.023-.197-.314A7.957 7.957 0 014 12c0-4.411 3.589-8 8-8s8 3.589 8 8-3.589 8-8 8zm-1-12h2v4h-2zm0 6h2v2h-2z"/>
      </svg>
    `;

    // 2. Determine User Display Name Safely
    let userName = "";
    try {
      userName = (frappe.session && (frappe.session.user_fullname || frappe.session.user)) || "";
    } catch (e) {
      userName = "";
    }

    // 3. Create Drawer
    const drawer = document.createElement("div");
    drawer.id = "chatgpt-drawer";
    drawer.innerHTML = `
      <div class="chatgpt-header">
        <div class="chatgpt-header-title">
          <span>AI Copilot</span>
          <span class="chatgpt-badge">v16 • Protected</span>
        </div>
        <div class="chatgpt-header-actions">
          <button class="chatgpt-icon-btn" id="chatgpt-btn-new" title="New Chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
          </button>
          <button class="chatgpt-icon-btn" id="chatgpt-btn-fullscreen" title="Open Fullpage Copilot">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
          </button>
          <button class="chatgpt-icon-btn" id="chatgpt-btn-close" title="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
      </div>
      <div class="chatgpt-context-bar" id="chatgpt-context-bar" style="display: none;">
        <span id="chatgpt-context-text">Context: None</span>
        <button class="chatgpt-icon-btn" id="chatgpt-context-clear" title="Ignore Context">×</button>
      </div>
      <div class="chatgpt-messages-container" id="chatgpt-messages">
        <div class="chatgpt-msg assistant">
          <div class="chatgpt-bubble">
            Hello ${userName ? userName + " " : ""}👋<br>
            I am your ERPNext AI Copilot. Sensitive financial data (PAN, GSTIN, accounts) is automatically masked, and tool queries respect your permissions.
          </div>
        </div>
      </div>
      <div class="chatgpt-input-area">
        <textarea class="chatgpt-input" id="chatgpt-input" rows="1" placeholder="Type a message or tool request (e.g. stock, outstanding)..."></textarea>
        <button class="chatgpt-send-btn" id="chatgpt-send-btn" title="Send message">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </button>
      </div>
      <div style="font-size: 10px; color: var(--chatgpt-subtext, #888); text-align: center; padding: 4px; background: var(--chatgpt-card-bg, #f4f4f4);">
        🛡️ PII Masked • Read-Only ORM Tools • Drafts Only
      </div>
    `;

    document.body.appendChild(launcher);
    document.body.appendChild(drawer);

    // Event Bindings
    launcher.addEventListener("click", toggleDrawer);
    document.getElementById("chatgpt-btn-close").addEventListener("click", closeDrawer);
    document.getElementById("chatgpt-btn-new").addEventListener("click", startNewChat);
    document.getElementById("chatgpt-btn-fullscreen").addEventListener("click", function () {
      closeDrawer();
      if (frappe.set_route) {
        frappe.set_route("chatgpt_copilot", activeConversationId ? { conversation: activeConversationId } : {});
      }
    });

    const sendBtn = document.getElementById("chatgpt-send-btn");
    const inputArea = document.getElementById("chatgpt-input");

    sendBtn.addEventListener("click", sendMessage);
    inputArea.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    inputArea.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    // Keyboard shortcut Ctrl+Shift+K or Cmd+Shift+K
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === "K" || e.key === "k")) {
        e.preventDefault();
        toggleDrawer();
      }
    });

    // Universal Link Interceptor for Drawer
    document.getElementById("chatgpt-messages").addEventListener("click", function (e) {
      const anchor = e.target.closest("a");
      if (!anchor) return;
      if (e.ctrlKey || e.metaKey || e.which === 2) return;

      let rawHref = anchor.getAttribute("href");
      if (!rawHref) return;

      const isInternal = rawHref.includes("/app") || 
                         rawHref.includes("/desk") || 
                         rawHref.startsWith("#") || 
                         rawHref.includes(window.location.host);

      if (!isInternal && (rawHref.startsWith("http://") || rawHref.startsWith("https://"))) {
        anchor.setAttribute("target", "_blank");
        return;
      }

      e.preventDefault();

      try {
        let routeString = rawHref;
        if (routeString.includes("#")) {
          routeString = routeString.split("#")[1];
        }
        if (routeString.startsWith("http://") || routeString.startsWith("https://")) {
          const u = new URL(routeString);
          routeString = u.pathname + u.search;
        }

        let queryStr = "";
        if (routeString.includes("?")) {
          const qParts = routeString.split("?");
          routeString = qParts[0];
          queryStr = qParts[1];
        }

        routeString = routeString.replace(/^\/+/, "");
        if (routeString.startsWith("app/")) {
          routeString = routeString.substring(4);
        } else if (routeString.startsWith("desk/")) {
          routeString = routeString.substring(5);
        }
        routeString = routeString.replace(/\/+$/, "");

        const routeParts = routeString.split("/").filter(Boolean).map(decodeURIComponent);
        const routeOptions = {};
        if (queryStr) {
          const params = new URLSearchParams(queryStr);
          params.forEach(function (val, key) {
            if (val.startsWith("<=")) {
              routeOptions[key] = ["<=", val.substring(2)];
            } else if (val.startsWith(">=")) {
              routeOptions[key] = [">=", val.substring(2)];
            } else if (val.startsWith("<")) {
              routeOptions[key] = ["<", val.substring(1)];
            } else if (val.startsWith(">")) {
              routeOptions[key] = [">", val.substring(1)];
            } else {
              routeOptions[key] = val;
            }
          });
        }

        frappe.route_options = routeOptions;
        if (routeParts.length > 0) {
          frappe.set_route(routeParts);
        } else {
          window.location.href = "/app/" + routeString + (queryStr ? "?" + queryStr : "");
        }
      } catch (err) {
        window.location.href = rawHref;
      }
    });

    // Realtime WebSocket Listener for background async completions
    if (window.frappe && frappe.realtime) {
      frappe.realtime.on("ai_chat_response", function (data) {
        removeTypingIndicator();
        isSending = false;
        if (data.status === "error") {
          appendMessage("assistant", "⚠️ " + (data.error || "Background task error"));
        } else if (data.reply) {
          activeConversationId = data.conversation_id;
          appendMessage("assistant", data.reply, data.log_id);
        }
      });
    }
  }

  function toggleDrawer() {
    const drawer = document.getElementById("chatgpt-drawer");
    if (!drawer) return;
    if (drawer.classList.contains("is-open")) {
      closeDrawer();
    } else {
      openDrawer();
    }
  }

  function openDrawer() {
    const drawer = document.getElementById("chatgpt-drawer");
    if (!drawer) return;
    drawer.classList.add("is-open");
    updateCurrentContext();
    const input = document.getElementById("chatgpt-input");
    if (input) input.focus();
  }

  function closeDrawer() {
    const drawer = document.getElementById("chatgpt-drawer");
    if (drawer) drawer.classList.remove("is-open");
  }

  function getCurrentDocContext() {
    try {
      const route = frappe.get_route ? frappe.get_route() : null;
      if (route && route[0] === "Form" && route[1] && route[2]) {
        return {
          doctype: route[1],
          docname: route[2]
        };
      }
    } catch (e) {}
    return null;
  }

  function updateCurrentContext() {
    const ctx = getCurrentDocContext();
    const bar = document.getElementById("chatgpt-context-bar");
    const txt = document.getElementById("chatgpt-context-text");
    if (!bar || !txt) return;
    if (ctx) {
      txt.innerText = `📄 Context: ${ctx.doctype} #${ctx.docname}`;
      bar.style.display = "flex";
    } else {
      bar.style.display = "none";
    }
  }

  function startNewChat() {
    activeConversationId = null;
    const container = document.getElementById("chatgpt-messages");
    if (!container) return;
    container.innerHTML = `
      <div class="chatgpt-msg assistant">
        <div class="chatgpt-bubble">
          Started a new clean session. Ask questions or query stock/balances!
        </div>
      </div>
    `;
    updateCurrentContext();
  }

  function appendMessage(role, text, logId) {
    const container = document.getElementById("chatgpt-messages");
    if (!container) return;
    const msgDiv = document.createElement("div");
    msgDiv.className = `chatgpt-msg ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "chatgpt-bubble";
    
    if (role === "assistant" && typeof frappe.markdown === "function") {
      bubble.innerHTML = frappe.markdown(text);
    } else {
      bubble.innerText = text;
    }

    msgDiv.appendChild(bubble);

    // Add Thumbs Up / Down feedback for assistant responses
    if (role === "assistant" && logId) {
      const fbDiv = document.createElement("div");
      fbDiv.style.cssText = "display: flex; gap: 8px; margin-top: 4px; font-size: 11px; color: var(--chatgpt-subtext, #888);";
      fbDiv.innerHTML = `
        <span style="cursor: pointer;" title="Helpful" class="chatgpt-fb-up">👍 Helpful</span>
        <span style="cursor: pointer;" title="Not helpful" class="chatgpt-fb-down">👎 Not Helpful</span>
      `;
      fbDiv.querySelector(".chatgpt-fb-up").addEventListener("click", function() {
        submitFeedback(logId, "Thumbs Up", this);
      });
      fbDiv.querySelector(".chatgpt-fb-down").addEventListener("click", function() {
        submitFeedback(logId, "Thumbs Down", this);
      });
      msgDiv.appendChild(fbDiv);
    }

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
  }

  function submitFeedback(logId, rating, el) {
    frappe.call({
      method: "erpnext_chatgpt.api.submit_feedback",
      args: { log_id: logId, feedback: rating },
      callback: function() {
        el.parentElement.innerHTML = `<span style="color: #10a37f;">✓ Feedback recorded (${rating})</span>`;
      }
    });
  }

  function showTypingIndicator() {
    const container = document.getElementById("chatgpt-messages");
    if (!container) return;
    const typing = document.createElement("div");
    typing.id = "chatgpt-typing-indicator";
    typing.className = "chatgpt-msg assistant";
    typing.innerHTML = `
      <div class="chatgpt-typing">
        <div class="chatgpt-dot"></div>
        <div class="chatgpt-dot"></div>
        <div class="chatgpt-dot"></div>
      </div>
    `;
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
  }

  function removeTypingIndicator() {
    const typing = document.getElementById("chatgpt-typing-indicator");
    if (typing) typing.remove();
  }

  function sendMessage() {
    if (isSending) return;
    const input = document.getElementById("chatgpt-input");
    if (!input) return;
    const text = (input.value || "").trim();
    if (!text) return;

    appendMessage("user", text);
    input.value = "";
    input.style.height = "auto";
    isSending = true;
    showTypingIndicator();

    const ctx = getCurrentDocContext();
    const args = {
      message: text,
      conversation_id: activeConversationId
    };

    if (ctx) {
      args.reference_doctype = ctx.doctype;
      args.reference_name = ctx.docname;
    }

    frappe.call({
      method: "erpnext_chatgpt.api.chat",
      args: args,
      callback: function (r) {
        removeTypingIndicator();
        isSending = false;
        if (r.message && r.message.reply) {
          activeConversationId = r.message.conversation_id;
          appendMessage("assistant", r.message.reply, r.message.log_id);
        } else if (r.message && r.message.status === "enqueued") {
          // Waiting on WebSocket
        } else {
          appendMessage("assistant", "⚠️ An error occurred while generating reply.");
        }
      },
      error: function (err) {
        removeTypingIndicator();
        isSending = false;
        appendMessage("assistant", "⚠️ Connection error or policy limit exceeded.");
      }
    });
  }

  // Safe Lazy Launch: wait until Desk has fully booted up so we NEVER interfere with Frappe startup
  function initWhenReady() {
    setTimeout(safeInit, 600);
  }

  if (document.readyState === "complete") {
    initWhenReady();
  } else {
    window.addEventListener("load", initWhenReady);
  }
})();
