/*
 * Kostal Piko card for Home Assistant (part of the kostal integration).
 *
 *   type: custom:kostal-piko-card
 *   prefix: sensor.kostal_piko   # entity_id prefix of the integration
 *   main: ring                   # ring | bar | number
 *   color: amber                 # amber | teal | blue | purple | green | any CSS color
 *   show: [kpis, history, strings, phases]
 *   details: false               # voltage and current for strings and phases
 *   show_outage: true            # notice and chart band while the inverter does not answer
 *   history_hours: 24
 *   max_power: 10000             # fallback if no maximum output power is configured
 *   price: 0.30                  # optional, price per kWh: shows the savings of today
 *   co2_factor: 380              # g CO2 per kWh of grid power, for the avoided CO2
 *   name: Kostal Piko
 */
const COLORS = {
  amber: "#EF9F27",
  teal: "#1D9E75",
  blue: "#378ADD",
  purple: "#7F77DD",
  green: "#639922",
};
const BLOCKS = ["kpis", "history", "strings", "phases"];
const TEXT = {
  en: {
    today: "Today", efficiency: "Efficiency", average: "Avg 15 min", utilization: "Utilization",
    yield: "Specific yield", strings: "Strings", phases: "Phases", total: "Total energy",
    history: "Power history", of: "of", string: "String", noData: "No data",
    standby: "Standby", peak: "Peak today", lastActive: "Last active", now: "Now",
    co2: "CO₂ avoided", saved: "Saved today",
    offline: "Offline", noConnection: "No connection since",
    recovery: "The values return as soon as the inverter answers again.", noDataSince: "no data since",
  },
  de: {
    today: "Heute", efficiency: "Wirkungsgrad", average: "Ø 15 min", utilization: "Auslastung",
    yield: "Spez. Ertrag", strings: "Strings", phases: "Phasen", total: "Gesamtertrag",
    history: "Leistungsverlauf", of: "von", string: "String", noData: "Keine Daten",
    standby: "Standby", peak: "Peak heute", lastActive: "Zuletzt aktiv", now: "Jetzt",
    co2: "CO₂ vermieden", saved: "Heute gespart",
    offline: "Offline", noConnection: "Keine Verbindung seit",
    recovery: "Die Werte kommen zurück, sobald der Wechselrichter wieder antwortet.", noDataSince: "keine Daten seit",
  },
};
// 24x24 line icons of the tiles and the outage notice
const ICONS = {
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chart: '<path d="M4 20h16M7 16v-4M12 16V7M17 16v-7"/>',
  leaf: '<path d="M5 19c0-8 6-14 15-14 0 9-6 14-14 14M5 19l7-7"/>',
  coin: '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.5a3 3 0 0 0-5 1.5c0 2.5 5 1.5 5 4a3 3 0 0 1-5 1.5M12 6.5v2M12 15.5v2"/>',
  offline: '<path d="M3 3l18 18M8.5 16.4a5 5 0 0 1 5.6-1M5 12.9a10 10 0 0 1 4.3-2.6M2 9.2a15 15 0 0 1 4-2.6M16.7 10.6A10 10 0 0 1 19 12.9M11.4 6A15 15 0 0 1 22 9.2"/><circle cx="12" cy="20" r="1" fill="currentColor" stroke="none"/>',
};
const HISTORY_REFRESH_MS = 5 * 60 * 1000;
const HISTORY_POINTS = 72;
// a pause in the history longer than this (and 3x the usual spacing) counts as a gap
const GAP_MIN_MS = 15 * 60 * 1000;

const esc = (value) =>
  String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class KostalPikoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._history = [];
    this._historyAt = 0;
    this._historyBusy = false;
  }

  setConfig(config) {
    if (config.main && !["ring", "bar", "number"].includes(config.main)) {
      throw new Error("main must be ring, bar or number");
    }
    const show = config.show === undefined ? BLOCKS : config.show;
    if (!Array.isArray(show) || show.some((block) => !BLOCKS.includes(block))) {
      throw new Error(`show must be a list of: ${BLOCKS.join(", ")}`);
    }
    const defaults = {
      prefix: "sensor.kostal_piko",
      main: "ring",
      color: "amber",
      details: false,
      show_outage: true,
      history_hours: 24,
      max_power: 10000,
      co2_factor: 380,
      name: "Kostal Piko",
    };
    this._config = { ...config, show };
    for (const [key, value] of Object.entries(defaults)) {
      if (this._config[key] === undefined || this._config[key] === null) this._config[key] = value;
    }
    this._historyAt = 0;
    this._render();
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (!previous || !this._config || this._changedSince(previous)) this._render();
    if (this._config) this._loadHistory();
  }

  // only re-render when an entity of this card or the language changed
  _changedSince(previous) {
    if (previous.language !== this._hass.language) return true;
    const prefix = `${this._config.prefix}_`;
    const now = this._hass.states;
    const before = previous.states;
    if (now === before) return false;
    for (const id of Object.keys(now)) {
      if (id.startsWith(prefix) && now[id] !== before[id]) return true;
    }
    return Object.keys(before).some((id) => id.startsWith(prefix) && !(id in now));
  }

  getCardSize() {
    return 3 + (this._config?.show.includes("history") ? 1 : 0) + (this._config?.show.includes("strings") ? 2 : 0) + (this._config?.show.includes("phases") ? 1 : 0);
  }

  static getStubConfig() {
    return { type: "custom:kostal-piko-card" };
  }

  static getConfigElement() {
    return document.createElement("kostal-piko-card-editor");
  }

  _t(key) {
    const lang = (this._hass?.language || "en").startsWith("de") ? "de" : "en";
    return TEXT[lang][key];
  }

  _entity(key) {
    return this._hass?.states[`${this._config.prefix}_${key}`];
  }

  _num(key) {
    const state = this._entity(key);
    if (!state) return null;
    const value = parseFloat(state.state);
    return Number.isFinite(value) ? value : null;
  }

  _fmt(value, digits = 0) {
    if (value === null || value === undefined) return "–";
    return value.toLocaleString(this._hass?.language, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  _power(value) {
    if (value === null) return "–";
    return Math.abs(value) >= 1000 ? `${this._fmt(value / 1000, 1)} kW` : `${this._fmt(value)} W`;
  }

  _color() {
    return esc(COLORS[this._config.color] || this._config.color);
  }

  _maxPower() {
    const attrs = this._entity("current_power")?.attributes || {};
    return attrs.max_output_power || this._config.max_power;
  }

  async _loadHistory() {
    const now = Date.now();
    if (this._historyBusy || now - this._historyAt < HISTORY_REFRESH_MS) return;
    this._historyBusy = true;
    this._historyAt = now;
    try {
      const entityId = `${this._config.prefix}_current_power`;
      const start = new Date(now - this._config.history_hours * 3600 * 1000);
      const result = await this._hass.callApi(
        "GET",
        `history/period/${start.toISOString()}?filter_entity_id=${entityId}&minimal_response&no_attributes`
      );
      const points = (result[0] || [])
        .map((item) => ({ t: new Date(item.last_changed || item.last_updated).getTime(), v: parseFloat(item.state) }))
        .filter((point) => Number.isFinite(point.v));
      const step = Math.max(1, Math.ceil(points.length / HISTORY_POINTS));
      this._historyStart = start.getTime();
      this._history = this._fillGaps(
        points.filter((_, index) => index % step === 0),
        this._historyStart,
        now
      );
    } catch (err) {
      this._history = [];
    } finally {
      this._historyBusy = false;
      this._render();
    }
  }

  // The history has no values while the inverter is unreachable (unavailable
  // states are dropped). Without help the chart would connect the last value
  // before the gap diagonally with the first one after it. Instead the line
  // stays at 0 through the gap and steps up where data resumes.
  _fillGaps(points, start, end) {
    if (points.length < 2) return points;
    const spacing = points.slice(1).map((p, i) => p.t - points[i].t).sort((a, b) => a - b);
    const limit = Math.max(GAP_MIN_MS, 3 * spacing[Math.floor(spacing.length / 2)]);
    const out = [];
    const gap = (from, to, fromValue) => {
      if (fromValue > 0) out.push({ t: from, v: 0 });
      out.push({ t: to, v: 0 });
    };
    if (points[0].t - start > limit) out.push({ t: start, v: 0 }, { t: points[0].t, v: 0 });
    points.forEach((point, index) => {
      const prev = points[index - 1];
      if (prev && point.t - prev.t > limit) gap(prev.t, point.t, prev.v);
      out.push(point);
    });
    const last = points[points.length - 1];
    if (end - last.t > limit) gap(last.t, end, last.v);
    return out;
  }

  // The inverter does not answer: its entities are unavailable. Only with the
  // option show_outage (default on).
  _offline() {
    return Boolean(this._config.show_outage && this._entity("current_power")?.state === "unavailable");
  }

  // time since the inverter does not answer (with the weekday if it was not today)
  _since() {
    const stamp = this._entity("current_power")?.last_changed;
    const date = stamp ? new Date(stamp) : null;
    if (!date || Number.isNaN(date.getTime())) return null;
    const sameDay = date.toDateString() === new Date().toDateString();
    const format = sameDay ? { hour: "2-digit", minute: "2-digit" } : { weekday: "short", hour: "2-digit", minute: "2-digit" };
    return { ms: date.getTime(), text: date.toLocaleString(this._hass?.language, format) };
  }

  // "4,2 kWh" becomes the number plus a smaller, grey unit
  _withUnit(text) {
    const index = text.indexOf(" ");
    if (index < 0) return esc(text);
    return `${esc(text.slice(0, index))}<span class="u">${esc(text.slice(index + 1))}</span>`;
  }

  _tile(icon, label, value) {
    return `<div class="tile"><span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[icon]}</svg></span>
      <div><div class="detail">${esc(label)}</div><div class="value">${this._withUnit(value)}</div></div></div>`;
  }

  _ring(power, max, color) {
    const offline = this._offline();
    const circumference = 2 * Math.PI * 50;
    const fraction = power === null || !max ? 0 : Math.min(Math.max(power / max, 0), 1);
    const value = power === null ? "–" : Math.abs(power) >= 1000 ? this._fmt(power / 1000, 1) : this._fmt(power);
    const unit = power !== null && Math.abs(power) >= 1000 ? "kW" : "W";
    const producing = fraction > 0;
    // sun while producing, crescent moon in standby, nothing during an outage
    const rays = [0, 45, 90, 135, 180, 225, 270, 315]
      .map((a) => `<line x1="60" y1="21" x2="60" y2="24" transform="rotate(${a} 60 30)"/>`)
      .join("");
    let icon = `<path d="M64 24a7 7 0 1 0 0 12a5.5 5.5 0 0 1 0-12z" fill="var(--secondary-text-color)" opacity="0.8"/>`;
    if (producing) {
      icon = `<g stroke="${color}" stroke-width="1.5" stroke-linecap="round" fill="none"><circle cx="60" cy="30" r="4" fill="${color}" stroke="none"/>${rays}</g>`;
    } else if (offline) {
      icon = "";
    }
    // dashed track in standby (grey) and during an outage (warning color)
    const track = producing
      ? `<circle cx="60" cy="60" r="50" fill="none" stroke="color-mix(in srgb, ${color} 16%, transparent)" stroke-width="8"/>`
      : `<circle cx="60" cy="60" r="50" fill="none" stroke="${offline ? "var(--warning-color, #ffa600)" : "var(--secondary-text-color)"}"
        stroke-opacity="${offline ? 0.45 : 0.35}" stroke-width="8" stroke-dasharray="2 6"/>`;
    // a zero-length round-capped arc would still draw a dot, so the arc is skipped at 0 W
    const arc = producing
      ? `<circle class="arc" cx="60" cy="60" r="50" fill="none" stroke="url(#arc)" stroke-width="8" stroke-linecap="round"
        stroke-dasharray="${(fraction * circumference).toFixed(1)} ${circumference.toFixed(1)}" transform="rotate(-90 60 60)" style="filter:drop-shadow(0 0 4px color-mix(in srgb, ${color} 60%, transparent))"/>`
      : "";
    return `<svg class="ring" viewBox="0 0 120 120" role="img" aria-label="${esc(value)} ${unit}">
      <defs><linearGradient id="arc" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" style="stop-color:color-mix(in srgb, ${color} 55%, white)"/><stop offset="1" stop-color="${color}"/>
      </linearGradient></defs>
      ${track}${arc}${icon}
      <text x="60" y="68" text-anchor="middle" class="ring-value${offline ? " muted" : ""}">${esc(value)}</text>
      <text x="60" y="84" text-anchor="middle" class="ring-unit">${unit}</text>
    </svg>`;
  }

  _main(power, max, color) {
    const utilization = this._num("utilization");
    const caption =
      utilization !== null
        ? `${this._fmt(utilization, 0)} % ${this._t("of")} ${this._power(max)}`
        : `${this._t("of")} ${this._power(max)}`;
    if (this._config.main === "bar") {
      const fraction = power === null || !max ? 0 : Math.min(Math.max(power / max, 0), 1);
      return `<div class="main-box"><div class="big">${this._withUnit(this._power(power))}</div>
        <div class="bar thick"><i style="width:${(fraction * 100).toFixed(1)}%;background:${color}"></i></div>
        <div class="small">${esc(caption)}</div></div>`;
    }
    if (this._config.main === "number") {
      return `<div class="main-box"><div class="big" style="color:${color}">${this._withUnit(this._power(power))}</div>
        <div class="small">${esc(caption)}</div></div>`;
    }
    return `<div class="main-box">${this._ring(power, max, color)}</div>`;
  }

  _kpis() {
    const offline = this._offline();
    const items = [
      [this._t("today"), `${this._fmt(this._num("daily_energy"), 1)} kWh`, this._entity("daily_energy")],
      [this._t("efficiency"), `${this._fmt(this._num("efficiency"), 1)} %`, this._entity("efficiency")],
      [this._t("average"), this._power(this._num("average_power_15_min")), this._entity("average_power_15_min")],
      [this._t("yield"), `${this._fmt(this._num("specific_yield"), 2)} kWh/kWp`, this._entity("specific_yield")],
    ].filter((item) => item[2]);
    if (this._config.main === "ring" && this._entity("utilization") && !offline) {
      items.push([this._t("utilization"), `${this._fmt(this._num("utilization"), 0)} %`, true]);
    }
    // during an outage only figures that still have a value are shown
    const shown = offline ? items.filter((item) => item[2] === true || item[2].state !== "unavailable") : items;
    if (!shown.length) return "";
    // the first figure is the hero, the rest fills two columns (an odd last one spans both)
    return `<div class="kpis">${shown
      .map((item, index) => {
        const cls = index === 0 ? "hero" : index === shown.length - 1 && index % 2 === 1 ? "wide" : "";
        return `<div class="${cls}"><div class="label">${esc(item[0])}</div><div class="value">${this._withUnit(item[1])}</div></div>`;
      })
      .join("")}</div>`;
  }

  _historyBlock(color) {
    if (this._history.length < 2) {
      this._chart = null;
      return "";
    }
    const end = Date.now();
    const start = this._historyStart || end - this._config.history_hours * 3600 * 1000;
    const max = Math.max(...this._history.map((p) => p.v), 1);
    // plot area: y 8 (maximum) to 88 (0 W) of a 300 x 96 viewBox
    const x = (t) => ((t - start) / (end - start)) * 100;
    const yUnits = (v) => 8 + (1 - Math.max(v, 0) / max) * 80;
    const y = (v) => (yUnits(v) / 96) * 100;
    this._chart = { points: this._history, start, end, x, y };
    const coords = this._history.map((p) => `${(x(p.t) * 3).toFixed(1)},${yUnits(p.v).toFixed(1)}`);
    const line = coords.join(" ");
    const first = coords[0].split(",")[0];
    const last = coords[coords.length - 1].split(",")[0];
    const area = `${first},88 ${line} ${last},88`;
    const peak = this._history.reduce((best, p) => (p.v > best.v ? p : best));
    const peakLeft = x(peak.t);
    const peakMarker = peak.v > 0
      ? `<div class="peak ${peakLeft > 80 ? "flip" : ""}" style="left:${peakLeft.toFixed(1)}%;top:${y(peak.v).toFixed(1)}%"><i></i><span>${esc(this._power(peak.v))}</span></div>`
      : "";
    const time = (t) => new Date(t).toLocaleTimeString(this._hass?.language, { hour: "2-digit", minute: "2-digit" });
    // a 24 h window starts at the same clock time as it ends: add the weekday to the start label
    const startLabel = new Date(start).toLocaleString(this._hass?.language, { weekday: "short", hour: "2-digit", minute: "2-digit" });
    // outage: shade the time without data and say since when
    const since = this._offline() ? this._since() : null;
    const band = since && since.ms < end
      ? `<rect class="gap-band" x="${(Math.max(x(since.ms), 0) * 3).toFixed(1)}" y="0" width="${((100 - Math.max(x(since.ms), 0)) * 3).toFixed(1)}" height="88"/>`
      : "";
    const endLabel = since
      ? `<span class="gap">${esc(this._t("noDataSince"))} ${esc(since.text)}</span>`
      : `<span>${esc(this._t("now"))} · ${esc(time(end))}</span>`;
    return `<div class="section"><div class="label">${esc(this._t("history"))}</div>
      <div class="chart">
        <svg viewBox="0 0 300 96" preserveAspectRatio="none" class="spark" role="img" aria-label="${esc(this._t("history"))}">
          <defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${color}" stop-opacity="0.35"/><stop offset="0.6" stop-color="${color}" stop-opacity="0.08"/><stop offset="1" stop-color="${color}" stop-opacity="0"/>
          </linearGradient></defs>
          ${band}
          <line class="grid-line" x1="0" x2="300" y1="28" y2="28" vector-effect="non-scaling-stroke"/>
          <line class="grid-line" x1="0" x2="300" y1="48" y2="48" vector-effect="non-scaling-stroke"/>
          <line class="grid-line" x1="0" x2="300" y1="68" y2="68" vector-effect="non-scaling-stroke"/>
          <line class="base-line" x1="0" x2="300" y1="88" y2="88" vector-effect="non-scaling-stroke"/>
          <polygon fill="url(#fill)" points="${area}"/>
          <polyline fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke" points="${line}"/>
        </svg>
        ${peakMarker}
        <div class="cursor" hidden></div>
        <div class="dot" hidden style="background:${color}"></div>
        <div class="tip" hidden></div>
      </div>
      <div class="axis"><span>${esc(startLabel)}</span>${endLabel}</div></div>`;
  }

  _bindChart() {
    const chart = this.shadowRoot.querySelector(".chart");
    if (!chart || !this._chart) return;
    const move = (event) => {
      const rect = chart.getBoundingClientRect();
      if (!rect.width) return;
      const { points, start, end } = this._chart;
      const t = start + Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1) * (end - start);
      this._hover = points.reduce((best, p) => (Math.abs(p.t - t) < Math.abs(best.t - t) ? p : best));
      this._applyHover();
    };
    const leave = () => {
      this._hover = null;
      this._applyHover();
    };
    chart.addEventListener("pointermove", move);
    chart.addEventListener("pointerdown", move);
    chart.addEventListener("pointerleave", leave);
    chart.addEventListener("pointercancel", leave);
  }

  _applyHover() {
    const root = this.shadowRoot;
    const cursor = root.querySelector(".cursor");
    const dot = root.querySelector(".dot");
    const tip = root.querySelector(".tip");
    if (!cursor || !dot || !tip) return;
    const point = this._hover;
    const chart = this._chart;
    root.querySelector(".chart")?.classList.toggle("hover", Boolean(point));
    if (!point || !chart || point.t < chart.start) {
      cursor.hidden = dot.hidden = tip.hidden = true;
      return;
    }
    const left = chart.x(point.t);
    const when = new Date(point.t).toLocaleString(this._hass?.language, {
      weekday: "short", hour: "2-digit", minute: "2-digit",
    });
    cursor.style.left = dot.style.left = `${left}%`;
    dot.style.top = `${chart.y(point.v)}%`;
    tip.innerHTML = `<b>${esc(this._power(point.v))}</b><span>${esc(when)}</span>`;
    // keep the tooltip inside the card: flip it on the right half
    tip.style.left = `${left}%`;
    tip.style.transform = left > 55 ? "translateX(calc(-100% - 8px))" : "translateX(8px)";
    cursor.hidden = dot.hidden = tip.hidden = false;
  }

  // night view: replaces strings and phases (all zeros) with a short summary of today
  _standbyTiles() {
    const midnight = new Date();
    midnight.setHours(0, 0, 0, 0);
    const today = this._history.filter((p) => p.t >= midnight.getTime() && p.v > 0);
    if (!today.length) return [];
    const peak = today.reduce((best, p) => (p.v > best.v ? p : best));
    const last = today[today.length - 1];
    const time = (t) => new Date(t).toLocaleTimeString(this._hass?.language, { hour: "2-digit", minute: "2-digit" });
    return [
      this._tile("bolt", this._t("peak"), `${this._power(peak.v)} · ${time(peak.t)}`),
      this._tile("clock", this._t("lastActive"), time(last.t)),
    ];
  }

  // lifetime yield, avoided CO2 and (with a price) today's savings
  _statsTiles() {
    const total = this._num("total_energy");
    if (total === null || !this._entity("total_energy")) return [];
    const tiles = [this._tile("chart", this._t("total"), `${this._fmt(total)} kWh`)];
    const factor = Number(this._config.co2_factor);
    if (Number.isFinite(factor) && factor > 0) {
      const kg = (total * factor) / 1000;
      tiles.push(this._tile("leaf", this._t("co2"), kg >= 1000 ? `${this._fmt(kg / 1000, 1)} t` : `${this._fmt(kg)} kg`));
    }
    const price = Number(this._config.price);
    const today = this._num("daily_energy");
    if (this._config.price !== undefined && Number.isFinite(price) && price > 0 && today !== null) {
      let money = this._fmt(today * price, 2);
      try {
        money = (today * price).toLocaleString(this._hass?.language, {
          style: "currency", currency: this._hass?.config?.currency || "EUR",
        });
      } catch (err) {
        // unknown currency code: keep the plain number
      }
      tiles.push(this._tile("coin", this._t("saved"), money));
    }
    return tiles;
  }

  _stringsBlock(color) {
    const strings = [1, 2, 3]
      .map((n) => {
        const state = this._entity(`string_${n}_power`);
        if (!state || state.state === "unavailable") return null;
        const wp = state.attributes?.installed_power || 0;
        return {
          n,
          wp,
          power: this._num(`string_${n}_power`),
          voltage: this._num(`string_${n}_voltage`),
          current: this._num(`string_${n}_current`),
        };
      })
      .filter(Boolean);
    // with plant data only the strings with installed power count, the rest is unused
    const configured = strings.some((s) => s.wp);
    const visible = configured ? strings.filter((s) => s.wp) : strings;
    if (!visible.length) return "";
    const reference = Math.max(...visible.map((s) => s.power || 0), 1);
    // each string gets its own shade of the card color
    const shade = (index) => `color-mix(in srgb, ${color} ${[100, 72, 48][index % 3]}%, ${index ? "white" : "transparent"})`;
    const rows = visible
      .map((s, index) => {
        const tint = shade(index);
        const fraction = Math.min(Math.max((s.power || 0) / (s.wp || reference), 0), 1);
        const percent = s.wp && s.power !== null ? ` · ${this._fmt((s.power / s.wp) * 100, 0)} %` : "";
        const extra = this._config.details
          ? `<div class="detail sub">${this._fmt(s.voltage)} V · ${this._fmt(s.current, 2)} A</div>`
          : "";
        return `<div><div class="row"><span class="name"><b style="background:${tint}"></b>${esc(this._t("string"))} ${s.n}</span>
          <div class="bar"><i style="width:${(fraction * 100).toFixed(1)}%;background:linear-gradient(90deg, color-mix(in srgb, ${tint} 60%, white), ${tint})"></i></div>
          <span class="amount">${esc(this._power(s.power))}${percent ? `<small>${esc(percent)}</small>` : ""}</span></div>${extra}</div>`;
      })
      .join("");
    return `<div class="section"><div class="label">${esc(this._t("strings"))}</div><div class="rows">${rows}</div></div>`;
  }

  _phasesBlock() {
    const phases = [1, 2, 3]
      .map((n) => ({ n, state: this._entity(`l${n}_power`), power: this._num(`l${n}_power`), voltage: this._num(`l${n}_voltage`) }))
      .filter((phase) => phase.state && phase.state.state !== "unavailable");
    if (!phases.length) return "";
    const tiles = phases
      .map(
        (phase) => `<div class="tile"><div><div class="detail">L${phase.n}${this._config.details ? ` · ${this._fmt(phase.voltage)} V` : ""}</div>
          <div class="value">${this._withUnit(this._power(phase.power))}</div></div></div>`
      )
      .join("");
    return `<div class="section"><div class="label">${esc(this._t("phases"))}</div><div class="tiles three">${tiles}</div></div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const color = this._color();
    const power = this._num("current_power");
    const max = this._maxPower();
    const status = this._entity("status");
    const offline = this._offline();
    const since = offline ? this._since() : null;
    const producing = power !== null && power > 0;
    const show = this._config.show;
    const empty = !this._entity("current_power");
    const standby = !producing;
    const summary = standby && (show.includes("strings") || show.includes("phases")) ? this._standbyTiles() : [];
    const tiles = [...summary, ...this._statsTiles()];
    const kpis = show.includes("kpis") ? this._kpis() : "";
    const chipText = offline ? this._t("offline") : status?.state;
    const chipClass = offline ? "warn" : producing ? "on" : "";
    const alert = offline
      ? `<div class="alert"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS.offline}</svg>
          <div><b>${esc(this._t("noConnection"))}${since ? ` ${esc(since.text)}` : ""}</b><span>${esc(this._t("recovery"))}</span></div></div>`
      : "";

    this.shadowRoot.innerHTML = `<style>
      :host { display: block; }
      ha-card { padding: 16px; --accent: ${color}; --warn: var(--warning-color, #ffa600); --ok: var(--success-color, #43a047); }
      .head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 14px; }
      .title { font-size: 16px; font-weight: 600; letter-spacing: -.01em; color: var(--primary-text-color); }
      .chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; padding: 3px 10px 3px 8px; border-radius: 999px; white-space: nowrap;
        background: color-mix(in srgb, var(--secondary-text-color) 12%, transparent); color: var(--secondary-text-color); }
      .chip i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
      .chip.on { background: color-mix(in srgb, var(--ok) 15%, transparent); color: var(--ok); }
      .chip.warn { background: color-mix(in srgb, var(--warn) 15%, transparent); color: var(--warn); }
      .alert { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 12px; margin-bottom: 14px;
        background: color-mix(in srgb, var(--warn) 10%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent); }
      .alert svg { flex: 0 0 auto; color: var(--warn); margin-top: 1px; }
      .alert b { display: block; font-size: 14px; font-weight: 600; color: var(--primary-text-color); }
      .alert span { font-size: 12px; color: var(--secondary-text-color); }
      .top { display: flex; align-items: center; gap: 16px; padding: 14px; border-radius: 16px;
        background: radial-gradient(120% 90% at 0% 0%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 70%),
          color-mix(in srgb, var(--primary-text-color) 2%, transparent); }
      .top.calm { background: radial-gradient(120% 90% at 0% 0%, color-mix(in srgb, var(--accent) 6%, transparent), transparent 70%),
          color-mix(in srgb, var(--primary-text-color) 2%, transparent); }
      .top.solo { justify-content: center; }
      .main-box { flex: 0 0 auto; min-width: 110px; }
      .ring { width: 116px; height: 116px; display: block; }
      .ring-value { font-size: 28px; font-weight: 600; letter-spacing: -.02em; fill: var(--primary-text-color); font-variant-numeric: tabular-nums; }
      .ring-value.muted { fill: var(--secondary-text-color); }
      .ring-unit { font-size: 12px; fill: var(--secondary-text-color); }
      .big { font-size: 30px; font-weight: 600; letter-spacing: -.02em; font-variant-numeric: tabular-nums; color: var(--primary-text-color); }
      .small { font-size: 12px; color: var(--secondary-text-color); }
      .label, .detail { font-size: 11px; font-weight: 500; letter-spacing: .04em; text-transform: uppercase; color: var(--secondary-text-color); }
      .detail.sub { text-transform: none; letter-spacing: 0; font-weight: 400; font-size: 12px; margin: 2px 0 0 80px; }
      .value { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: -.01em; margin-top: 2px; color: var(--primary-text-color); }
      .u { font-size: .62em; font-weight: 500; color: var(--secondary-text-color); margin-left: .2em; letter-spacing: 0; }
      .kpis { flex: 1; min-width: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; }
      .kpis .hero, .kpis .wide { grid-column: 1 / -1; }
      .kpis .hero .value { font-size: 30px; line-height: 1.1; letter-spacing: -.02em; }
      .kpis .hero .u { font-size: .5em; }
      .section { margin-top: 20px; }
      .section > .label { margin-bottom: 8px; }
      .chart { position: relative; touch-action: pan-y; cursor: crosshair; }
      .spark { width: 100%; height: 96px; display: block; overflow: visible; }
      .grid-line { stroke: var(--secondary-text-color); stroke-opacity: .25; stroke-dasharray: 2 4; }
      .base-line { stroke: var(--secondary-text-color); stroke-opacity: .3; }
      .gap-band { fill: color-mix(in srgb, var(--warn) 12%, transparent); }
      .peak { position: absolute; pointer-events: none; transition: opacity .15s; }
      .peak i { position: absolute; width: 8px; height: 8px; margin: -4px 0 0 -4px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 2px var(--card-background-color, #fff); }
      .peak span { position: absolute; left: 9px; top: 0; transform: translateY(-50%); font-size: 11px; font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums;
        padding: 1px 7px; border-radius: 999px; background: var(--card-background-color, #fff); color: var(--primary-text-color);
        border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent); }
      .peak.flip span { left: auto; right: 9px; }
      .chart.hover .peak { opacity: 0; }
      .cursor { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--secondary-text-color); opacity: 0.5; pointer-events: none; }
      .dot { position: absolute; width: 8px; height: 8px; margin: -4px 0 0 -4px; border-radius: 50%; pointer-events: none; box-shadow: 0 0 0 2px var(--card-background-color, #fff); }
      .tip { position: absolute; top: -4px; display: flex; flex-direction: column; padding: 4px 8px; border-radius: 6px; font-size: 12px; white-space: nowrap; pointer-events: none;
        background: var(--card-background-color, #fff); color: var(--primary-text-color); border: 1px solid var(--divider-color); }
      .tip span { font-size: 11px; color: var(--secondary-text-color); }
      .axis { display: flex; justify-content: space-between; font-size: 11px; color: var(--secondary-text-color); margin-top: 6px; font-variant-numeric: tabular-nums; }
      .axis .gap { color: var(--warn); }
      .rows { display: grid; gap: 10px; }
      .row { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--primary-text-color); }
      .name { width: 70px; flex: 0 0 auto; display: flex; align-items: center; gap: 6px; font-weight: 500; }
      .name b { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
      .amount { min-width: 86px; text-align: right; flex: 0 0 auto; font-weight: 500; font-variant-numeric: tabular-nums; }
      .amount small { color: var(--secondary-text-color); font-weight: 400; font-size: 12px; }
      .bar { flex: 1; height: 8px; border-radius: 4px; background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); overflow: hidden; }
      .bar.thick { height: 10px; margin: 8px 0 4px; }
      .bar i { display: block; height: 100%; border-radius: 4px; }
      .tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
      .tiles.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .tiles:not(.three) > .tile:last-child:nth-child(odd):not(:only-child) { grid-column: 1 / -1; }
      .tile { display: flex; align-items: center; gap: 10px; min-width: 0; padding: 10px 12px; border-radius: 12px;
        background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
        border: 1px solid color-mix(in srgb, var(--primary-text-color) 6%, transparent); }
      .tile > div { min-width: 0; }
      .tile .value { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .ico { flex: 0 0 auto; width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
        background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); }
      .ico svg { width: 16px; height: 16px; }
      .cursor[hidden], .dot[hidden], .tip[hidden] { display: none; }
      .empty { padding: 8px 0; color: var(--secondary-text-color); }
    </style>
    <ha-card>
      <div class="head"><span class="title">${esc(this._config.name)}</span>
        ${chipText ? `<span class="chip ${chipClass}"><i></i>${esc(chipText)}</span>` : ""}</div>
      ${empty ? `<div class="empty">${esc(this._t("noData"))}: ${esc(this._config.prefix)}_current_power</div>` : `
      ${alert}
      <div class="top ${standby ? "calm" : ""} ${kpis ? "" : "solo"}">${this._main(power, max, color)}${kpis}</div>
      ${show.includes("history") ? this._historyBlock(color) : ""}
      ${standby ? "" : `${show.includes("strings") ? this._stringsBlock(color) : ""}${show.includes("phases") ? this._phasesBlock() : ""}`}
      ${tiles.length ? `<div class="section tiles">${tiles.join("")}</div>` : ""}`}
    </ha-card>`;
    this._bindChart();
    this._applyHover();
  }
}

const EDITOR_TEXT = {
  en: {
    name: "Title", entity: "Inverter (current power sensor)", main: "Main display", color: "Color",
    show: "Blocks", details: "Voltage and current", show_outage: "Show outage notice", history_hours: "History (hours)",
    max_power: "Ring maximum (W), if no maximum output power is set",
    price: "Price per kWh (shows savings)", co2_factor: "CO₂ per kWh grid power (g)",
    ring: "Ring", bar: "Bar", number: "Number", amber: "Amber", teal: "Teal", blue: "Blue",
    purple: "Purple", green: "Green", kpis: "Key figures", history: "History", strings: "Strings", phases: "Phases",
  },
  de: {
    name: "Titel", entity: "Wechselrichter (Sensor Aktuelle Leistung)", main: "Hauptanzeige", color: "Farbe",
    show: "Blöcke", details: "Spannung und Strom", show_outage: "Ausfall anzeigen", history_hours: "Verlauf (Stunden)",
    max_power: "Maximum des Rings (W), wenn keine maximale Ausgangsleistung gesetzt ist",
    price: "Preis pro kWh (zeigt die Ersparnis)", co2_factor: "CO₂ je kWh Netzstrom (g)",
    ring: "Ring", bar: "Balken", number: "Zahl", amber: "Amber", teal: "Türkis", blue: "Blau",
    purple: "Violett", green: "Grün", kpis: "Kennzahlen", history: "Verlauf", strings: "Strings", phases: "Phasen",
  },
};
const POWER_SUFFIX = "_current_power";

class KostalPikoCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (!previous || !this._config || this._changedSince(previous)) this._render();
  }

  _t(key) {
    return EDITOR_TEXT[(this._hass?.language || "en").startsWith("de") ? "de" : "en"][key];
  }

  _schema() {
    const options = (keys) => keys.map((value) => ({ value, label: this._t(value) }));
    const colors = Object.keys(COLORS);
    const color = this._config.color;
    const colorOptions = options(colors);
    // a custom CSS color from YAML stays selectable
    if (color && !colors.includes(color)) colorOptions.push({ value: color, label: color });
    const sensors = Object.keys(this._hass?.states || {}).filter(
      (id) => id.startsWith("sensor.") && id.endsWith(POWER_SUFFIX)
    );
    return [
      { name: "name", selector: { text: {} } },
      { name: "entity", selector: { entity: { include_entities: sensors } } },
      { name: "main", selector: { select: { mode: "box", options: options(["ring", "bar", "number"]) } } },
      { name: "color", selector: { select: { mode: "dropdown", options: colorOptions } } },
      { name: "show", selector: { select: { multiple: true, mode: "list", options: options(BLOCKS) } } },
      { name: "details", selector: { boolean: {} } },
      { name: "show_outage", selector: { boolean: {} } },
      { name: "history_hours", selector: { number: { min: 1, max: 168, mode: "box" } } },
      { name: "max_power", selector: { number: { min: 0, max: 1000000, step: 100, mode: "box", unit_of_measurement: "W" } } },
      { name: "price", selector: { number: { min: 0, max: 10, step: 0.01, mode: "box" } } },
      { name: "co2_factor", selector: { number: { min: 0, max: 2000, step: 10, mode: "box", unit_of_measurement: "g" } } },
    ];
  }

  _data() {
    const c = this._config;
    return {
      name: c.name || "Kostal Piko",
      entity: `${c.prefix || "sensor.kostal_piko"}${POWER_SUFFIX}`,
      main: c.main || "ring",
      color: c.color || "amber",
      show: c.show === undefined ? BLOCKS : c.show,
      details: Boolean(c.details),
      show_outage: c.show_outage !== false,
      history_hours: c.history_hours || 24,
      max_power: c.max_power || 10000,
      price: c.price,
      co2_factor: c.co2_factor === undefined ? 380 : c.co2_factor,
    };
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => this._t(schema.name);
      this._form.addEventListener("value-changed", (event) => this._changed(event.detail.value));
      this.append(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = this._data();
  }

  _changed(value) {
    const { entity, ...rest } = value;
    // drop cleared fields so the card falls back to its defaults
    for (const key of Object.keys(rest)) {
      if (rest[key] === undefined || rest[key] === null || rest[key] === "") delete rest[key];
    }
    const config = { ...this._config, ...rest };
    for (const key of ["name", "history_hours", "max_power", "price", "co2_factor"]) {
      if (!(key in rest)) delete config[key];
    }
    if (entity && entity.endsWith(POWER_SUFFIX)) {
      config.prefix = entity.slice(0, -POWER_SUFFIX.length);
    }
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }
}

if (!customElements.get("kostal-piko-card-editor")) {
  customElements.define("kostal-piko-card-editor", KostalPikoCardEditor);
}

if (!customElements.get("kostal-piko-card")) {
  customElements.define("kostal-piko-card", KostalPikoCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "kostal-piko-card")) {
  window.customCards.push({
    type: "kostal-piko-card",
    name: "Kostal Piko",
    description: "Power, strings and phases of a Kostal Piko inverter",
  });
}
