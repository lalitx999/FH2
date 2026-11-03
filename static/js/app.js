// Ajax และการโต้ตอบทั้งเว็บอยู่ไฟล์นี้ไฟล์เดียว ข้อตกลงกับ server ดูที่ config/ajax.py
(function () {
  "use strict";

  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const COMPARE_KEY = "fh_compare_ids";
  const maxCompare = Number(document.body.dataset.maxCompare || 4);

  function toast(message, ok) {
    const box = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = "fh-toast" + (ok ? " ok" : "");
    el.setAttribute("role", "status");
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }

  // คืน {ok, status, text} ส่วน error ทั่วไปและการไม่ login จัดการที่นี่จุดเดียว
  async function ajax(url, options) {
    const opts = options || {};
    let response;
    try {
      response = await fetch(url, {
        method: opts.method || "GET",
        body: opts.body,
        headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken },
      });
    } catch (err) {
      toast("เชื่อมต่อไม่สำเร็จ กรุณาลองใหม่");
      return { ok: false, status: 0, text: "" };
    }
    const text = await response.text();
    if (response.status === 401) {
      const login = response.headers.get("X-Login-URL");
      window.location.href = login + "?next=" + encodeURIComponent(location.pathname + location.search);
    } else if (!response.ok && response.status !== 422) {
      const plain = (response.headers.get("Content-Type") || "").startsWith("text/plain");
      toast(plain ? text : "เกิดข้อผิดพลาด กรุณาลองใหม่");
    }
    return { ok: response.ok, status: response.status, text: text };
  }

  function swap(el, html) {
    const holder = document.createElement("template");
    holder.innerHTML = html.trim();
    el.replaceWith(holder.content);
  }

  function resolveTarget(el) {
    const selector = el.dataset.target;
    if (!selector) return el;
    if (selector.startsWith("closest:")) return el.closest(selector.slice(8));
    return document.querySelector(selector);
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (form.id === "search-form") {
      event.preventDefault();
      runSearch(form);
    } else if (form.matches("[data-ajax-form]")) {
      event.preventDefault();
      const button = form.querySelector('[type="submit"]');
      if (button) button.disabled = true;
      const result = await ajax(form.action, { method: "POST", body: new FormData(form) });
      if (result.ok || result.status === 422) swap(form, result.text);
      else if (button) button.disabled = false;
    }
  });

  document.addEventListener("click", async (event) => {
    const post = event.target.closest("[data-ajax-post]");
    if (post) {
      event.preventDefault();
      if (post.dataset.confirm && !window.confirm(post.dataset.confirm)) return;
      post.disabled = true;
      const target = resolveTarget(post);
      const result = await ajax(post.dataset.ajaxPost, { method: "POST" });
      if (result.ok) {
        swap(target, result.text);
        updateCounts();
      } else {
        post.disabled = false;
      }
      return;
    }
    const confirmButton = event.target.closest("[data-confirm]");
    if (confirmButton && !window.confirm(confirmButton.dataset.confirm)) {
      event.preventDefault();
      return;
    }
    const pageLink = event.target.closest("#results .page-link");
    if (pageLink && pageLink.href) {
      event.preventDefault();
      loadResults(pageLink.href, true);
      document.getElementById("results").scrollIntoView({ behavior: "smooth" });
      return;
    }
    const compareButton = event.target.closest("[data-compare-id]");
    if (compareButton) {
      toggleCompare(Number(compareButton.dataset.compareId));
      return;
    }
    if (event.target.closest("[data-compare-clear]")) {
      writeCompare([]);
      renderCompare();
      return;
    }
    const copyButton = event.target.closest("[data-copy-link]");
    if (copyButton) {
      copyLink();
      return;
    }
    const step = event.target.closest("[data-step-go]");
    if (step) goToStep(step);
  });

  // ค้นหา: หน้าเต็มและ Ajax ใช้ view เดียวกัน URL เปลี่ยนตาม จึงแชร์ลิงก์ได้
  let latestSearch = 0;

  async function loadResults(url, push) {
    const results = document.getElementById("results");
    if (!results) return;
    const searchId = ++latestSearch;
    results.classList.add("is-loading");
    const result = await ajax(url);
    if (searchId !== latestSearch) return;  // มีการค้นหาใหม่กว่าแล้ว คำตอบนี้ทิ้งได้
    results.classList.remove("is-loading");
    if (!result.ok) return;
    results.innerHTML = result.text;
    if (push) history.pushState(null, "", url);
    renderCompare();
  }

  function runSearch(form) {
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      if (value) params.append(key, value);
    });
    const query = params.toString();
    loadResults(form.action + (query ? "?" + query : ""), true);
  }

  document.addEventListener("change", (event) => {
    const form = event.target.closest("#search-form");
    if (form && document.getElementById("results")) runSearch(form);
    if (event.target.matches("input[data-upload-url]")) uploadFiles(event.target);
  });

  // ปุ่มย้อนกลับเปลี่ยนแค่ URL จึงต้องตั้งค่าในฟอร์มให้ตรงกับผลการค้นหาด้วย
  function syncSearchForm() {
    const form = document.getElementById("search-form");
    if (!form) return;
    const params = new URLSearchParams(location.search);
    Array.from(form.elements).forEach((field) => {
      if (!field.name) return;
      const value = params.get(field.name) || "";
      if (field.type === "radio" || field.type === "checkbox") field.checked = field.value === value;
      else if (field.tagName === "SELECT") field.value = value || field.options[0].value;
      else field.value = value;
    });
  }

  window.addEventListener("popstate", () => {
    if (!document.getElementById("results")) return;
    syncSearchForm();
    loadResults(location.href, false);
  });

  // อัปโหลดทีละไฟล์ กัน request ใหญ่เกินเพดานของ proxy และแสดงความคืบหน้าได้จริง
  async function uploadFiles(input) {
    const files = Array.from(input.files);
    if (!files.length) return;
    const grid = document.querySelector(input.dataset.target);
    const bar = document.querySelector(input.dataset.progress);
    const fill = bar.querySelector(".progress-bar");
    bar.classList.remove("d-none");
    input.disabled = true;
    let done = 0;
    for (const file of files) {
      const body = new FormData();
      body.append("file", file);
      const result = await ajax(input.dataset.uploadUrl, { method: "POST", body: body });
      if (result.ok) {
        grid.insertAdjacentHTML("beforeend", result.text);
        updateCounts();
      }
      done += 1;
      const percent = Math.round((done / files.length) * 100);
      fill.style.width = percent + "%";
      fill.textContent = done + " / " + files.length;
    }
    input.disabled = false;
    input.value = "";
    setTimeout(() => bar.classList.add("d-none"), 800);
  }

  // นับจำนวนรูปในกล่องอัปโหลด แล้วเปิดปุ่มส่งเมื่อครบขั้นต่ำ
  function updateCounts() {
    document.querySelectorAll("[data-count-of]").forEach((label) => {
      const grid = document.querySelector(label.dataset.countOf);
      const count = grid ? grid.children.length : 0;
      label.textContent = count;
      const submit = label.dataset.enables && document.querySelector(label.dataset.enables);
      if (submit) submit.disabled = count < Number(label.dataset.min || 0);
    });
  }

  // เปรียบเทียบ: เก็บ id ไว้ในเบราว์เซอร์ หน้าตารางดึงข้อมูลจริงจาก server
  function readCompare() {
    try {
      return JSON.parse(localStorage.getItem(COMPARE_KEY) || "[]");
    } catch (err) {
      return [];
    }
  }

  function writeCompare(ids) {
    try {
      localStorage.setItem(COMPARE_KEY, JSON.stringify(ids));
    } catch (err) {
      toast("เบราว์เซอร์นี้บันทึกรายการเปรียบเทียบไม่ได้");
    }
  }

  function toggleCompare(id) {
    let ids = readCompare();
    if (ids.includes(id)) {
      ids = ids.filter((item) => item !== id);
    } else if (ids.length >= maxCompare) {
      toast("เปรียบเทียบได้สูงสุด " + maxCompare + " รายการ");
      return;
    } else {
      ids.push(id);
    }
    writeCompare(ids);
    renderCompare();
  }

  function renderCompare() {
    const ids = readCompare();
    document.querySelectorAll("[data-compare-id]").forEach((button) => {
      button.classList.toggle("is-on", ids.includes(Number(button.dataset.compareId)));
    });
    const bar = document.getElementById("compare-bar");
    if (!bar) return;
    bar.classList.toggle("d-none", ids.length === 0);
    bar.querySelector("[data-compare-count]").textContent = ids.length;
    bar.querySelector("a").href = bar.dataset.url + "?ids=" + ids.join(",");
  }

  // ฟอร์มหลายขั้น: ตรวจช่องในขั้นปัจจุบันก่อนไปขั้นถัดไป server ตรวจซ้ำตอนส่งจริง
  function goToStep(button) {
    const steps = Array.from(document.querySelectorAll(".wizard-step"));
    const current = button.closest(".wizard-step");
    const nextIndex = steps.indexOf(current) + Number(button.dataset.stepGo);
    if (Number(button.dataset.stepGo) > 0) {
      for (const field of current.querySelectorAll("input, select, textarea")) {
        if (!field.reportValidity()) return;
      }
    }
    showStep(steps, nextIndex);
  }

  function showStep(steps, index) {
    steps.forEach((step, i) => step.classList.toggle("d-none", i !== index));
    document.querySelectorAll(".fh-step").forEach((pill, i) => pill.classList.toggle("active", i === index));
    window.scrollTo({ top: 0 });
  }

  function openStepWithError() {
    const steps = Array.from(document.querySelectorAll(".wizard-step"));
    if (!steps.length) return;
    const index = steps.findIndex((step) => step.querySelector(".is-invalid"));
    showStep(steps, Math.max(index, 0));
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(location.href);
      toast("คัดลอกลิงก์แล้ว", true);
    } catch (err) {
      toast("คัดลอกไม่สำเร็จ กรุณาคัดลอกจากแถบที่อยู่");
    }
  }

  // แกลเลอรี: อัปเดตเลขรูปและรูปย่อตามสไลด์ที่แสดง
  function initGallery() {
    const gallery = document.getElementById("gallery");
    if (!gallery) return;
    gallery.addEventListener("slid.bs.carousel", (event) => {
      const current = document.querySelector("[data-gallery-current]");
      if (current) current.textContent = event.to + 1;
      document.querySelectorAll(".fh-thumbs button").forEach((thumb, index) => {
        thumb.classList.toggle("active", index === event.to);
      });
    });
  }

  // แสดงเฉพาะช่องที่เกี่ยวข้อง ฟอร์มฝากขายเลือกตามประเภททรัพย์ ฟอร์มลงประกาศและตัวกรองเลือกตามหมวด
  function initTypeFields() {
    const typeSelect = document.getElementById("id_property_type");
    const switcher = document.querySelector("[data-field-switch]") || typeSelect;
    const fields = document.querySelectorAll("[data-show-for], [data-show-type]");
    if (!switcher || !fields.length) return;
    const showWhenEmpty = switcher.hasAttribute("data-show-empty");
    const apply = () => {
      const value = switcher.selectedOptions[0]?.dataset.slug || switcher.value;
      fields.forEach((field) => {
        const { showFor, showType } = field.dataset;
        const matchesSwitch = showFor === undefined || (showWhenEmpty && !value) || showFor.split(",").includes(value);
        const matchesType = !showType || showType === typeSelect?.value;
        field.classList.toggle("d-none", !(matchesSwitch && matchesType));
        // ตัวกรองที่ซ่อนไปแล้วต้องไม่ค้างเงื่อนไข ไม่อย่างนั้นผลค้นหาจะว่างโดยไม่รู้สาเหตุ
        if (showWhenEmpty && !matchesSwitch) field.querySelectorAll("input, select").forEach((input) => { input.value = ""; });
      });
    };
    switcher.addEventListener("change", apply);
    if (typeSelect && typeSelect !== switcher) typeSelect.addEventListener("change", apply);
    apply();
  }

  // รวมเนื้อที่ให้เห็นระหว่างกรอก จะได้จับเลขไร่-งานที่พิมพ์ผิดได้ทันที
  function initLandTotal() {
    const output = document.querySelector("[data-land-total]");
    if (!output) return;
    const inputs = [["id_land_rai", 400], ["id_land_ngan", 100], ["id_land_sqw", 1]]
      .map(([id, sqw]) => [document.getElementById(id), sqw]);
    const apply = () => {
      const total = inputs.reduce((sum, [input, sqw]) => sum + (Number(input.value) || 0) * sqw, 0);
      output.textContent = `รวม ${total ? total.toLocaleString("th-TH") : "-"} ตร.ว.`;
    };
    inputs.forEach(([input]) => input.addEventListener("input", apply));
    apply();
  }

  // เลื่อนถึงแล้วค่อยแสดง ถ้าเบราว์เซอร์ไม่รองรับก็แสดงตามปกติ
  function initReveal() {
    const items = document.querySelectorAll("[data-reveal]");
    if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    items.forEach((item) => {
      item.classList.add("fh-reveal");
      observer.observe(item);
    });
  }

  updateCounts();
  renderCompare();
  openStepWithError();
  initTypeFields();
  initLandTotal();
  initGallery();
  initReveal();
})();
