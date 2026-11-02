(() => {
  const root = document.querySelector("[data-chat]");
  if (!root) return;

  const POLL_INTERVAL_MS = 1200;
  const POLL_LIMIT_MS = 60000;
  const panel = root.querySelector(".fh-chat-panel");
  const opener = root.querySelector("[data-chat-open]");
  const body = root.querySelector("[data-chat-body]");
  const log = root.querySelector("[data-chat-log]");
  const form = root.querySelector("[data-chat-form]");
  const input = form.elements.message;
  const headers = { "X-Requested-With": "XMLHttpRequest" };
  let historyLoaded = false;
  let sending = false;

  const scrollToEnd = () => { body.scrollTop = body.scrollHeight; };

  const appendHtml = (html) => {
    log.insertAdjacentHTML("beforeend", html);
    log.querySelectorAll("[data-poll-url]:not([data-polling])").forEach(poll);
    scrollToEnd();
  };

  const showNote = (text) => {
    const note = document.createElement("div");
    note.className = "fh-chat-msg bot";
    note.textContent = text;
    log.append(note);
    scrollToEnd();
  };

  function poll(bubble) {
    bubble.dataset.polling = "1";
    const startedAt = Date.now();
    const tick = async () => {
      try {
        const response = await fetch(bubble.dataset.pollUrl, { headers });
        if (response.status === 200) {
          bubble.insertAdjacentHTML("afterend", await response.text());
          bubble.remove();
          scrollToEnd();
          return;
        }
        if (response.status !== 204) throw new Error(String(response.status));
      } catch (_) {
        // เครือข่ายสะดุดชั่วคราว ลองรอบถัดไปจนกว่าจะหมดเวลา
      }
      if (Date.now() - startedAt > POLL_LIMIT_MS) {
        bubble.classList.remove("pending");
        bubble.removeAttribute("data-poll-url");
        bubble.textContent = "ระบบตอบช้ากว่าปกติ กรุณาลองใหม่อีกครั้งครับ";
        return;
      }
      setTimeout(tick, POLL_INTERVAL_MS);
    };
    setTimeout(tick, POLL_INTERVAL_MS);
  }

  const loadHistory = async () => {
    if (historyLoaded) return;
    historyLoaded = true;
    try {
      const response = await fetch(root.dataset.historyUrl, { headers });
      if (response.ok) appendHtml(await response.text());
    } catch (_) {
      historyLoaded = false;
    }
  };

  const setOpen = (open) => {
    panel.hidden = !open;
    opener.hidden = open;
    opener.setAttribute("aria-expanded", String(open));
    if (open) {
      loadHistory();
      scrollToEnd();
      input.focus();
    } else {
      opener.focus();
    }
  };

  const send = async () => {
    const text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    const data = new FormData(form);
    input.value = "";
    try {
      const response = await fetch(form.action, { method: "POST", body: data, headers });
      if (response.ok) {
        appendHtml(await response.text());
      } else {
        showNote(response.status === 403 ? "กรุณารีเฟรชหน้าแล้วลองใหม่ครับ" : await response.text());
      }
    } catch (_) {
      showNote("เชื่อมต่อไม่ได้ กรุณาลองใหม่อีกครั้งครับ");
    } finally {
      sending = false;
    }
  };

  opener.addEventListener("click", () => setOpen(true));
  root.querySelector("[data-chat-close]").addEventListener("click", () => setOpen(false));
  panel.addEventListener("keydown", (event) => { if (event.key === "Escape") setOpen(false); });
  form.addEventListener("submit", (event) => { event.preventDefault(); send(); });
  root.querySelectorAll("[data-chat-chip]").forEach((chip) => {
    chip.addEventListener("click", () => { input.value = chip.dataset.chatChip; send(); });
  });
})();
