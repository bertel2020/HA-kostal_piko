/*
 * Kostal Piko card for Home Assistant (part of the kostal integration).
 *
 *   type: custom:kostal-piko-card
 *   prefix: sensor.kostal_piko   # entity_id prefix of the integration
 *   main: ring                   # ring | bar | number
 *   color: amber                 # amber | teal | blue | purple | green | any CSS color
 *   show: [kpis, history, strings, phases]
 *   details: false               # voltage and current for strings and phases
 *   history_hours: 24
 *   max_power: 10000             # fallback if no maximum output power is configured
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
  },
  de: {
    today: "Heute", efficiency: "Wirkungsgrad", average: "Ø 15 min", utilization: "Auslastung",
    yield: "Spez. Ertrag", strings: "Strings", phases: "Phasen", total: "Gesamtertrag",
    history: "Leistungsverlauf", of: "von", string: "String", noData: "Keine Daten",
  },
};
const HISTORY_REFRESH_MS = 5 * 60 * 1000;
const HISTORY_POINTS = 72;

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
    this._config = {
      prefix: "sensor.kostal_piko",
      main: "ring",
      color: "amber",
      details: false,
      history_hours: 24,
      max_power: 10000,
      name: "Kostal Piko",
      ...config,
      show,
    };
    this._historyAt = 0;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
    if (this._config && this._config.show.includes("history")) this._loadHistory();
  }

  getCardSize() {
    return 3 + (this._config?.show.includes("history") ? 1 : 0) + (this._config?.show.includes("strings") ? 2 : 0) + (this._config?.show.includes("phases") ? 1 : 0);
  }

  static getStubConfig() {
    return { type: "custom:kostal-piko-card" };
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
    return COLORS[this._config.color] || this._config.color;
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
      this._history = points.filter((_, index) => index % step === 0);
      this._historyStart = start.getTime();
    } catch (err) {
      this._history = [];
    } finally {
      this._historyBusy = false;
      this._render();
    }
  }

  _ring(power, max, color) {
    const circumference = 2 * Math.PI * 50;
    const fraction = power === null || !max ? 0 : Math.min(Math.max(power / max, 0), 1);
    const value = power === null ? "–" : Math.abs(power) >= 1000 ? this._fmt(power / 1000, 1) : this._fmt(power);
    const unit = power !== null && Math.abs(power) >= 1000 ? "kW" : "W";
    return `<svg class="ring" viewBox="0 0 120 120" role="img" aria-label="${esc(value)} ${unit}">
      <circle cx="60" cy="60" r="50" fill="none" stroke="var(--divider-color)" stroke-width="10" opacity="0.5"/>
      <circle cx="60" cy="60" r="50" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"
        stroke-dasharray="${(fraction * circumference).toFixed(1)} ${circumference.toFixed(1)}" transform="rotate(-90 60 60)"/>
      <text x="60" y="58" text-anchor="middle" class="ring-value">${esc(value)}</text>
      <text x="60" y="77" text-anchor="middle" class="ring-unit">${unit}</text>
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
      return `<div class="main-box"><div class="big">${esc(this._power(power))}</div>
        <div class="bar thick"><i style="width:${(fraction * 100).toFixed(1)}%;background:${color}"></i></div>
        <div class="small">${esc(caption)}</div></div>`;
    }
    if (this._config.main === "number") {
      return `<div class="main-box"><div class="big" style="color:${color}">${esc(this._power(power))}</div>
        <div class="small">${esc(caption)}</div></div>`;
    }
    return `<div class="main-box">${this._ring(power, max, color)}</div>`;
  }

  _kpis() {
    const items = [
      [this._t("today"), `${this._fmt(this._num("daily_energy"), 1)} kWh`, this._entity("daily_energy")],
      [this._t("efficiency"), `${this._fmt(this._num("efficiency"), 1)} %`, this._entity("efficiency")],
      [this._t("average"), this._power(this._num("average_power_15_min")), this._entity("average_power_15_min")],
      [this._t("yield"), `${this._fmt(this._num("specific_yield"), 2)} kWh/kWp`, this._entity("specific_yield")],
    ].filter((item) => item[2]);
    if (this._config.main === "ring" && this._entity("utilization")) {
      items.push([this._t("utilization"), `${this._fmt(this._num("utilization"), 0)} %`, true]);
    }
    return `<div class="kpis">${items
      .map((item) => `<div><div class="label">${esc(item[0])}</div><div class="value">${esc(item[1])}</div></div>`)
      .join("")}</div>`;
  }

  _historyBlock(color) {
    if (this._history.length < 2) return "";
    const end = Date.now();
    const start = this._historyStart || end - this._config.history_hours * 3600 * 1000;
    const max = Math.max(...this._history.map((p) => p.v), 1);
    const points = this._history
      .map((p) => `${(((p.t - start) / (end - start)) * 300).toFixed(1)},${(46 - (Math.max(p.v, 0) / max) * 42).toFixed(1)}`)
      .join(" ");
    return `<div class="section"><div class="label">${esc(this._t("history"))}</div>
      <svg viewBox="0 0 300 50" preserveAspectRatio="none" class="spark" role="img" aria-label="${esc(this._t("history"))}">
        <polyline fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" points="${points}"/>
      </svg></div>`;
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
    const rows = visible
      .map((s) => {
        const fraction = Math.min(Math.max((s.power || 0) / (s.wp || reference), 0), 1);
        const percent = s.wp && s.power !== null ? ` · ${this._fmt((s.power / s.wp) * 100, 0)} %` : "";
        const extra = this._config.details
          ? `<div class="detail">${this._fmt(s.voltage)} V · ${this._fmt(s.current, 2)} A</div>`
          : "";
        return `<div><div class="row"><span class="name">${esc(this._t("string"))} ${s.n}</span>
          <div class="bar"><i style="width:${(fraction * 100).toFixed(1)}%;background:${color}"></i></div>
          <span class="amount">${esc(this._power(s.power))}${esc(percent)}</span></div>${extra}</div>`;
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
        (phase) => `<div class="tile"><div class="detail">L${phase.n}${this._config.details ? ` · ${this._fmt(phase.voltage)} V` : ""}</div>
          <div class="value">${esc(this._power(phase.power))}</div></div>`
      )
      .join("");
    return `<div class="section"><div class="label">${esc(this._t("phases"))}</div><div class="tiles">${tiles}</div></div>`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const color = this._color();
    const power = this._num("current_power");
    const max = this._maxPower();
    const status = this._entity("status");
    const producing = power !== null && power > 0;
    const show = this._config.show;
    const total = this._entity("total_energy") && this._num("total_energy") !== null
      ? `<div class="footer">${esc(this._t("total"))} ${esc(this._fmt(this._num("total_energy")))} kWh</div>` : "";
    const empty = !this._entity("current_power");

    this.shadowRoot.innerHTML = `<style>
      :host { display: block; }
      ha-card { padding: 16px; }
      .head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
      .title { font-size: 16px; font-weight: 500; color: var(--primary-text-color); }
      .chip { font-size: 12px; padding: 2px 10px; border-radius: 8px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
      .chip.on { background: color-mix(in srgb, var(--success-color, #43a047) 18%, transparent); color: var(--success-color, #43a047); }
      .top { display: flex; align-items: center; gap: 16px; }
      .main-box { flex: 0 0 auto; min-width: 110px; }
      .ring { width: 120px; height: 120px; display: block; }
      .ring-value { font-size: 24px; font-weight: 500; fill: var(--primary-text-color); }
      .ring-unit { font-size: 12px; fill: var(--secondary-text-color); }
      .big { font-size: 28px; font-weight: 500; color: var(--primary-text-color); }
      .small, .label, .detail { font-size: 12px; color: var(--secondary-text-color); }
      .kpis { flex: 1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; }
      .value { font-size: 15px; font-weight: 500; color: var(--primary-text-color); }
      .section { border-top: 1px solid var(--divider-color); margin-top: 12px; padding-top: 12px; }
      .section .label { margin-bottom: 8px; }
      .spark { width: 100%; height: 50px; display: block; }
      .rows { display: grid; gap: 8px; }
      .row { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--primary-text-color); }
      .name { width: 58px; flex: 0 0 auto; }
      .amount { min-width: 96px; text-align: right; flex: 0 0 auto; }
      .detail { margin-left: 68px; }
      .bar { flex: 1; height: 6px; border-radius: 3px; background: var(--divider-color); overflow: hidden; }
      .bar.thick { height: 10px; margin: 8px 0 4px; }
      .bar i { display: block; height: 100%; border-radius: 3px; }
      .tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
      .tile { background: var(--secondary-background-color); border-radius: 8px; padding: 8px 10px; }
      .tile .detail { margin: 0; }
      .footer { margin-top: 12px; text-align: right; font-size: 11px; color: var(--secondary-text-color); }
      .empty { padding: 8px 0; color: var(--secondary-text-color); }
    </style>
    <ha-card>
      <div class="head"><span class="title">${esc(this._config.name)}</span>
        ${status ? `<span class="chip ${producing ? "on" : ""}">${esc(status.state)}</span>` : ""}</div>
      ${empty ? `<div class="empty">${esc(this._t("noData"))}: ${esc(this._config.prefix)}_current_power</div>` : `
      <div class="top">${this._main(power, max, color)}${show.includes("kpis") ? this._kpis() : ""}</div>
      ${show.includes("history") ? this._historyBlock(color) : ""}
      ${show.includes("strings") ? this._stringsBlock(color) : ""}
      ${show.includes("phases") ? this._phasesBlock() : ""}
      ${total}`}
    </ha-card>`;
  }
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
