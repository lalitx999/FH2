// แผนที่ Leaflet ใช้ไฟล์ในโปรเจกต์ ส่วนภาพแผนที่โหลดจาก OpenStreetMap
(function () {
  "use strict";

  const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

  function createMap(element, options) {
    const map = L.map(element, Object.assign({ scrollWheelZoom: false }, options));
    // OpenStreetMap ปฏิเสธคำขอจากเบราว์เซอร์ที่ไม่ส่ง Referer
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION, referrerPolicy: "strict-origin-when-cross-origin" }).addTo(map);
    return map;
  }

  function priceLabel(price) {
    if (price >= 1000000) return "฿" + (price / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
    if (price >= 1000) return "฿" + Math.round(price / 1000) + "K";
    return "฿" + price;
  }

  function pinIcon(point, selected) {
    const tone = selected ? "selected" : point.type === "RENT" ? "rent" : "sale";
    const span = document.createElement("span");
    span.className = "fh-pin " + tone;
    span.textContent = priceLabel(point.price);
    return L.divIcon({ className: "fh-pin-wrap", html: span, iconSize: [0, 0] });
  }

  function initHomeMap() {
    const element = document.getElementById("home-map");
    const data = document.getElementById("map-data");
    if (!element || !data) return;
    const points = JSON.parse(data.textContent);
    const map = createMap(element, { center: [13.7563, 100.5018], zoom: 11 });
    const preview = document.getElementById("map-preview");
    const template = document.getElementById("map-card");
    const markers = new Map();
    let selected = null;

    function refreshPins() {
      markers.forEach((marker, point) => marker.setIcon(pinIcon(point, point === selected)));
    }

    function close() {
      selected = null;
      preview.classList.add("d-none");
      preview.replaceChildren();
      refreshPins();
    }

    function open(point) {
      selected = point;
      const card = template.content.cloneNode(true);
      card.querySelector("[data-price]").textContent = "฿" + point.price_text;
      card.querySelector("[data-title]").textContent = point.title;
      card.querySelector("[data-location]").textContent = point.location;
      card.querySelector("[data-specs]").textContent = point.specs;
      card.querySelector("[data-icon]").classList.add(point.icon);
      card.querySelector("a").href = point.url;
      card.querySelector("[data-close]").addEventListener("click", close);
      preview.replaceChildren(card);
      preview.classList.remove("d-none");
      refreshPins();
      map.panTo([point.lat, point.lng]);
    }

    points.forEach((point) => {
      const marker = L.marker([point.lat, point.lng], {
        icon: pinIcon(point, false),
        title: point.title,
        alt: point.title,
      }).addTo(map);
      marker.on("click", () => open(point));
      markers.set(point, marker);
    });

    if (points.length) {
      map.fitBounds(points.map((p) => [p.lat, p.lng]), { padding: [40, 40], maxZoom: 13 });
    }
  }

  function initDetailMap() {
    const element = document.getElementById("detail-map");
    if (!element) return;
    const position = [Number(element.dataset.lat), Number(element.dataset.lng)];
    const map = createMap(element, { center: position, zoom: 15 });
    const span = document.createElement("span");
    span.className = "fh-pin selected";
    span.textContent = element.dataset.label;
    L.marker(position, {
      icon: L.divIcon({ className: "fh-pin-wrap", html: span, iconSize: [0, 0] }),
      alt: element.dataset.label,
    }).addTo(map);
  }

  // แผนที่อยู่ท้ายหน้า โหลด Leaflet และภาพแผนที่เมื่อใกล้เลื่อนถึงเท่านั้น
  let leafletReady;

  function loadLeaflet(element) {
    if (leafletReady) return leafletReady;
    leafletReady = new Promise((resolve, reject) => {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = element.dataset.leafletCss;
      document.head.append(css);
      const script = document.createElement("script");
      script.src = element.dataset.leafletJs;
      script.onload = resolve;
      script.onerror = reject;
      document.head.append(script);
    });
    return leafletReady;
  }

  function whenNear(id, init) {
    const element = document.getElementById(id);
    if (!element) return;
    const start = () => loadLeaflet(element).then(init);
    if (!("IntersectionObserver" in window)) {
      start();
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      start();
    }, { rootMargin: "400px 0px" });
    observer.observe(element);
  }

  whenNear("home-map", initHomeMap);
  whenNear("detail-map", initDetailMap);
})();
