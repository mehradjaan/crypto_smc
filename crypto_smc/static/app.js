/* SmartFlow dashboard */

const $ = (id) => document.getElementById(id);
const form = $("search-form");
const qInput = $("q");
const statusEl = $("status");
const emptyEl = $("empty");
const resultEl = $("result");

let LAST = null;
let ACTIVE_TF = "4h";
let CURRENT_QUERY = "";
let REFRESH_TIMER = null;
let COUNT_TIMER = null;
let NEXT_REFRESH = 0;
const REFRESH_MS = 120000;
const TF_ORDER = ["4h", "1h", "30m", "15m", "5m", "1m"];
const TF_COLOR = {
  "4h": "#7aa2ff",
  "1h": "#b49cff",
  "30m": "#2ee6c5",
  "15m": "#5ee7ff",
  "5m": "#ffc857",
  "1m": "#ff8aa0",
};

function showStatus(msg, err = false) {
  statusEl.classList.remove("hidden");
  statusEl.className = "status" + (err ? " err" : "");
  statusEl.innerHTML = msg;
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function fmt(n, d) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const x = Number(n);
  const ax = Math.abs(x);
  if (d != null) return x.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
  if (ax >= 1000) return x.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (ax >= 1) return x.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (ax >= 0.01) return x.toLocaleString("en-US", { maximumFractionDigits: 6 });
  return x.toLocaleString("en-US", { maximumFractionDigits: 8 });
}

function biasClass(bias) {
  if (!bias) return "flat";
  if (bias.includes("bull")) return "bull";
  if (bias.includes("bear")) return "bear";
  return "flat";
}

function faStatus(s) {
  return (
    {
      fresh: "تازه / لمس‌نشده",
      tapped: "لمس‌شده",
      filled: "پر شده",
      invalidated: "باطل",
      bullish: "صعودی",
      bearish: "نزولی",
      overbought: "اشباع خرید",
      oversold: "اشباع فروش",
      neutral: "خنثی",
      mixed: "ترکیبی",
      strong: "قوی",
      very_strong: "خیلی قوی",
      moderate: "متوسط",
      weak_range: "ضعیف / رنج",
      premium: "پرمیوم",
      discount: "دیسکانت",
      equilibrium: "تعادل",
      high: "بالا",
      low: "پایین",
      climax: "اوج حجم",
      normal: "عادی",
      above: "بالای VWAP",
      below: "زیر VWAP",
      bullish_cross: "کراس صعودی",
      bearish_cross: "کراس نزولی",
    }[s] || s || "—"
  );
}

function armRefresh() {
  NEXT_REFRESH = Date.now() + REFRESH_MS;
  if (REFRESH_TIMER) clearInterval(REFRESH_TIMER);
  REFRESH_TIMER = setInterval(() => {
    if (CURRENT_QUERY) analyze(CURRENT_QUERY, true);
  }, REFRESH_MS);
  if (!COUNT_TIMER) COUNT_TIMER = setInterval(updateCountdown, 1000);
  updateCountdown();
}

function updateCountdown() {
  const el = $("refresh-note");
  if (!el) return;
  if (!CURRENT_QUERY) {
    el.textContent = "رفرش خودکار هر ۲ دقیقه";
    return;
  }
  const left = Math.max(0, Math.ceil((NEXT_REFRESH - Date.now()) / 1000));
  const m = Math.floor(left / 60);
  const s = String(left % 60).padStart(2, "0");
  const sym = LAST && LAST.symbol ? LAST.symbol : CURRENT_QUERY;
  el.textContent = `به‌روزرسانی ${sym} تا ${m}:${s}`;
}

async function analyze(query, silent = false) {
  const q = (query || "").trim();
  if (!q) return;
  CURRENT_QUERY = q;
  qInput.value = q;
  emptyEl.classList.add("hidden");
  if (!silent) {
    resultEl.classList.add("hidden");
    showStatus('<span class="spin"></span> در حال دریافت کندل و اجرای تحلیل شش تایم‌فریم…');
    $("go").disabled = true;
  } else {
    const note = $("refresh-note");
    if (note) note.innerHTML = '<span class="spin"></span> در حال به‌روزرسانی…';
  }
  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    const data = await res.json();
    if (!res.ok) {
      const detail = data.detail || data.message || "خطا";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    LAST = data;
    if (!silent) ACTIVE_TF = "4h";
    hideStatus();
    render(data);
    resultEl.classList.remove("hidden");
    armRefresh();
  } catch (err) {
    if (silent) {
      const note = $("refresh-note");
      if (note) note.textContent = "به‌روزرسانی ناموفق — دوباره تلاش می‌شود";
    } else {
      showStatus(err.message || String(err), true);
    }
  } finally {
    $("go").disabled = false;
  }
}

function render(d) {
  $("sym").textContent = d.symbol;
  $("meta").textContent = `${d.exchange_label} · ${d.generated_at} · ${d.base}/${d.quote}`;
  $("price").textContent = fmt(d.price);
  const chg = d.change_pct;
  const chgEl = $("chg");
  if (chg == null) {
    chgEl.textContent = "۲۴س: —";
    chgEl.className = "chg";
  } else {
    chgEl.textContent = `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}٪  ۲۴ساعته`;
    chgEl.className = "chg " + (chg >= 0 ? "up" : "down");
  }
  $("range24").textContent =
    d.high_24h != null ? `۲۴س  H ${fmt(d.high_24h)}   L ${fmt(d.low_24h)}` : "";

  const c = d.confluence;
  const pill = $("conf-pill");
  pill.textContent = c.bias_fa;
  pill.className = "pill " + biasClass(c.bias);
  $("gauge-val").textContent = c.score;
  $("headline").textContent = c.headline;
  $("disclaimer").textContent = d.disclaimer;

  const row = $("tf-row");
  row.innerHTML = "";
  (c.cards || []).forEach((card) => {
    const el = document.createElement("div");
    el.className = "tf-chip";
    el.dataset.tf = card.tf;
    el.innerHTML = `<span>${card.title}</span><b class="bias ${biasClass(card.bias)}">${card.bias_fa}</b><span>${card.score}</span>`;
    el.onclick = () => {
      ACTIVE_TF = card.tf;
      drawChart(d, card.tf);
      highlightTab(card.tf);
    };
    row.appendChild(el);
  });

  const s = c.setup || {};
  const bits = [`<div>${s.idea || ""}</div>`];
  if (s.entry_zone && s.entry_zone.low != null) {
    bits.push(
      `<div class="kv">ناحیه تمرکز (${s.entry_zone.kind}): <b>${fmt(s.entry_zone.low)} – ${fmt(s.entry_zone.high)}</b></div>`
    );
  }
  if (s.invalidation != null) bits.push(`<div class="kv">باطل‌شدن نسبی: <b>${fmt(s.invalidation)}</b></div>`);
  if (s.targets && s.targets.length) {
    bits.push(`<div class="kv">اهداف نقدینگی: <b>${s.targets.map(fmt).join("  ·  ")}</b></div>`);
  }
  $("setup").innerHTML = bits.join("");
  $("report").textContent = d.report || "";

  const tabs = $("tf-tabs");
  tabs.innerHTML = "";
  TF_ORDER.forEach((tf) => {
    if (!d.timeframes[tf]) return;
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = d.timeframes[tf].title;
    b.dataset.tf = tf;
    b.onclick = () => {
      ACTIVE_TF = tf;
      drawChart(d, tf);
      highlightTab(tf);
    };
    tabs.appendChild(b);
  });
  if (!d.timeframes[ACTIVE_TF]) ACTIVE_TF = TF_ORDER.find((t) => d.timeframes[t]) || "4h";
  highlightTab(ACTIVE_TF);
  drawChart(d, ACTIVE_TF);
  renderPanels(d);
}

function highlightTab(tf) {
  document.querySelectorAll("#tf-tabs button").forEach((b) => {
    b.classList.toggle("on", b.dataset.tf === tf);
  });
}

function drawChart(d, tf) {
  const block = d.timeframes[tf];
  if (!block || !window.Plotly) return;
  const ch = block.chart;
  const xs = ch.candles.map((c) => c.t);
  const candle = {
    type: "candlestick",
    x: xs,
    open: ch.candles.map((c) => c.o),
    high: ch.candles.map((c) => c.h),
    low: ch.candles.map((c) => c.l),
    close: ch.candles.map((c) => c.c),
    name: d.symbol,
    increasing: { line: { color: "#2ee6c5" }, fillcolor: "#2ee6c5" },
    decreasing: { line: { color: "#ff6b7a" }, fillcolor: "#ff6b7a" },
    whiskerwidth: 0.8,
  };
  const ema21 = {
    type: "scatter",
    mode: "lines",
    x: xs,
    y: ch.ema21,
    name: "EMA21",
    line: { color: "#5ee7ff", width: 1.5 },
    hoverinfo: "skip",
  };
  const ema50 = {
    type: "scatter",
    mode: "lines",
    x: xs,
    y: ch.ema50,
    name: "EMA50",
    line: { color: "#b49cff", width: 1.5 },
    hoverinfo: "skip",
  };
  const shapes = (ch.shapes || []).map((s) => ({
    type: "rect",
    xref: "x",
    yref: "y",
    x0: s.x0,
    x1: s.x1,
    y0: s.y0,
    y1: s.y1,
    fillcolor: s.fill,
    line: { width: 1, color: s.line },
    layer: "below",
  }));
  (ch.levels || []).forEach((lv) => {
    shapes.push({
      type: "line",
      xref: "paper",
      yref: "y",
      x0: 0,
      x1: 1,
      y0: lv.price,
      y1: lv.price,
      line: { color: lv.kind === "eq" ? "#b49cff" : "#7aa2ff", width: 1, dash: "dot" },
    });
  });
  const annot = (ch.markers || []).map((m) => ({
    x: m.t,
    y: m.price,
    text: m.text,
    showarrow: true,
    arrowhead: 0,
    arrowsize: 0.8,
    ay: m.direction === "bullish" ? 18 : -18,
    font: { size: 10, color: m.direction === "bullish" ? "#2ee6c5" : "#ff6b7a" },
    bgcolor: "rgba(6,16,24,.8)",
    borderpad: 2,
  }));

  const layout = {
    paper_bgcolor: "#0e2430",
    plot_bgcolor: "#07161d",
    font: { color: "#8fb3b8", family: "IBM Plex Sans, Vazirmatn, sans-serif", size: 11 },
    margin: { l: 56, r: 16, t: 18, b: 40 },
    xaxis: {
      rangeslider: { visible: false },
      gridcolor: "#1d3a48",
      tickangle: -20,
      fixedrange: false,
    },
    yaxis: { gridcolor: "#1d3a48", side: "right", fixedrange: false, autorange: true },
    showlegend: false,
    shapes,
    annotations: annot,
    dragmode: "pan",
    hovermode: "x unified",
    uirevision: tf,
  };
  Plotly.react("chart", [candle, ema21, ema50], layout, {
    scrollZoom: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    responsive: true,
  });
}

function zoneLine(z) {
  if (!z) return "—";
  const dir = z.direction === "bullish" ? "صعودی" : "نزولی";
  return `${dir} ${fmt(z.bottom)} – ${fmt(z.top)} · ${faStatus(z.status)}${z.inside ? " · قیمت داخل ناحیه" : ""}`;
}

function renderPanels(d) {
  const host = $("tf-panels");
  host.innerHTML = "";
  TF_ORDER.forEach((tf) => {
    const b = d.timeframes[tf];
    if (!b) return;
    const smc = b.smc || {};
    const ta = b.ta || {};
    const sc = b.score || {};
    const near = smc.nearby || {};
    const liq = smc.liquidity || {};
    const ev = smc.last_event;
    const card = document.createElement("article");
    card.className = "card panel";
    card.dataset.tf = tf;
    card.innerHTML = `
      <h3>${b.title} <span class="bias ${biasClass(sc.bias)}">${sc.bias_fa} · ${sc.score}</span></h3>
      <div class="stats">
        <div class="stat"><div class="k">ساختار</div><div class="v">${smc.structure_label || "—"}</div></div>
        <div class="stat"><div class="k">آخرین شکست</div><div class="v">${
          ev ? `${ev.kind} ${faStatus(ev.direction)} (${ev.bars_ago} کندل)` : "—"
        }</div></div>
        <div class="stat"><div class="k">پرمیوم / دیسکانت</div><div class="v">${faStatus(smc.premium_discount)}</div></div>
        <div class="stat"><div class="k">RSI / MACD / ADX</div><div class="v">${fmt(ta.rsi, 1)} · ${faStatus(ta.macd_cross)} · ${fmt(ta.adx, 1)}</div></div>
        <div class="stat"><div class="k">EMA</div><div class="v">${faStatus(ta.ema_stack)}</div></div>
        <div class="stat"><div class="k">نقدینگی</div><div class="v">BSL ${fmt(liq.nearest_bsl)} · SSL ${fmt(liq.nearest_ssl)}</div></div>
      </div>
      <ul class="list">
        <li>اردر بلاک صعودی نزدیک: ${zoneLine(near.bullish_ob)}</li>
        <li>اردر بلاک نزولی نزدیک: ${zoneLine(near.bearish_ob)}</li>
        <li>FVG صعودی نزدیک: ${zoneLine(near.bullish_fvg)}</li>
        <li>FVG نزولی نزدیک: ${zoneLine(near.bearish_fvg)}</li>
        <li>جلسه جاری (UTC): ${smc.session || "—"}</li>
        ${(smc.notes || []).slice(0, 3).map((n) => `<li>${n}</li>`).join("")}
        ${(sc.reasons || []).slice(0, 4).map((n) => `<li>دلیل امتیاز: ${n}</li>`).join("")}
      </ul>
    `;
    host.appendChild(card);
  });
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  analyze(qInput.value);
});

document.querySelectorAll("#chips button").forEach((b) => {
  b.addEventListener("click", () => analyze(b.dataset.q));
});

$("refresh-now").addEventListener("click", () => {
  if (CURRENT_QUERY) analyze(CURRENT_QUERY, true);
});

$("copy-report").addEventListener("click", async () => {
  if (!LAST) return;
  try {
    await navigator.clipboard.writeText(LAST.report || "");
    $("copy-report").textContent = "کپی شد";
    setTimeout(() => ($("copy-report").textContent = "کپی گزارش"), 1500);
  } catch {
    $("copy-report").textContent = "ناموفق";
  }
});

// demo on first load
analyze("BTCUSDT");
