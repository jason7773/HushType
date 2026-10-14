"""產生使用統計儀表板（單一 HTML 檔，不載入任何外部資源，可離線開啟）。"""

from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>dictate 使用統計</title>
<style>
:root {
  color-scheme: light;
  --bg: #f4f4f2; --surface: #fcfcfb; --border: #e3e2de;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7a7974;
  --grid: #ebeae6; --series: #2a78d6; --series-hover: #1d5fae;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #111110; --surface: #1a1a19; --border: #2e2e2c;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
    --grid: #2a2a28; --series: #3987e5; --series-hover: #6aa6ee;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #111110; --surface: #1a1a19; --border: #2e2e2c;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #8f8e86;
  --grid: #2a2a28; --series: #3987e5; --series-hover: #6aa6ee;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text-primary);
  font: 15px/1.5 system-ui, "Microsoft JhengHei", "PingFang TC", sans-serif;
}
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }
header { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }
h1 { font-size: 24px; margin: 0; }
h2 { font-size: 16px; margin: 0; }
.muted { color: var(--text-muted); font-size: 13px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 24px 0; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; }
.kpi .label { color: var(--text-secondary); font-size: 13px; }
.kpi .value { font-size: 28px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.2; margin-top: 4px; }
.kpi .unit { font-size: 14px; font-weight: 400; color: var(--text-secondary); margin-left: 2px; }
.kpi .sub { color: var(--text-muted); font-size: 12px; margin-top: 2px; }
.chart-card { margin-bottom: 16px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.seg button {
  font: inherit; font-size: 13px; padding: 4px 12px; border: 0; background: transparent;
  color: var(--text-secondary); cursor: pointer;
}
.seg button[aria-pressed="true"] { background: var(--text-primary); color: var(--surface); }
.chart { position: relative; }
.chart svg { display: block; overflow: visible; }
.chart text { fill: var(--text-muted); font-size: 11px; }
.bar { fill: var(--series); pointer-events: none; }
.hit:hover + .bar, .bar.active { fill: var(--series-hover); }
.tip {
  position: absolute; pointer-events: none; background: var(--text-primary); color: var(--surface);
  padding: 6px 10px; border-radius: 6px; font-size: 12px; white-space: nowrap;
  transform: translate(-50%, -100%); margin-top: -8px; display: none;
}
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 8px 6px; white-space: nowrap; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--text-secondary); font-weight: 500; font-size: 13px; }
.table-wrap { overflow-x: auto; }
footer { margin-top: 24px; }
</style>
</head>
<body>
<main>
  <header>
    <h1>使用統計</h1>
    <span class="muted" id="generated"></span>
  </header>
  <section class="kpis" id="kpis"></section>

  <section class="card chart-card">
    <div class="chart-head">
      <h2 id="daily-title">近 30 天</h2>
      <div class="seg" role="group" aria-label="指標" id="metric"></div>
    </div>
    <div class="chart" id="daily"></div>
  </section>

  <section class="card chart-card">
    <div class="chart-head"><h2>一天中的使用時段（次數）</h2></div>
    <div class="chart" id="hourly"></div>
  </section>

  <section class="card chart-card">
    <div class="chart-head"><h2>每月統計</h2></div>
    <div class="table-wrap"><table id="monthly"></table></div>
  </section>

  <footer class="muted" id="note"></footer>
</main>
<script>
const DATA = __DATA__;
const fmt = (n, d = 0) => n == null ? "—" : Number(n).toLocaleString("zh-TW", { maximumFractionDigits: d, minimumFractionDigits: d });
const fmtMin = m => m >= 60 ? [fmt(m / 60, 1), "小時"] : [fmt(m, m < 10 ? 1 : 0), "分鐘"];

document.getElementById("generated").textContent = "更新於 " + DATA.generated_at.replace("T", " ");

function kpi(label, [value, unit], sub) {
  return `<div class="card kpi"><div class="label">${label}</div>
    <div class="value">${value}<span class="unit">${unit}</span></div>
    <div class="sub">${sub}</div></div>`;
}
const t = DATA.today, m = DATA.month, all = DATA.total;
document.getElementById("kpis").innerHTML = [
  kpi("今天說話時間", fmtMin(t.minutes), `${fmt(t.count)} 次・${fmt(t.chars)} 字`),
  kpi("本月說話時間", fmtMin(m.minutes), `${fmt(m.count)} 次`),
  kpi("本月輸出字數", [fmt(m.chars), "字"], `累計 ${fmt(all.chars)} 字`),
  kpi("本月估計省下", fmtMin(m.saved_minutes), `累計 ${fmtMin(all.saved_minutes).join(" ")}`),
  kpi("平均回應時間", [fmt(m.avg_latency ?? all.avg_latency, 1), "秒"], "放開按鍵到文字出現"),
  kpi("連續使用", [fmt(DATA.streak_days), "天"], `累計 ${fmt(all.count)} 次`),
].join("");

function niceMax(v) {
  // 回傳可被 4 整除的漂亮上限，讓 5 條格線的刻度都是整齊的數字
  if (v <= 0) return 4;
  const raw = v / 4, p = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const s of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (s * p >= raw) return s * p * 4;
}

function barChart(el, items, { value, label, tip, labelWidth = 44 }) {
  const W = Math.max(el.clientWidth, 280), H = 220, L = 40, R = 8, T = 10, B = 26;
  const pw = W - L - R, ph = H - T - B;
  const max = niceMax(Math.max(...items.map(value)));
  const every = Math.ceil(items.length / Math.max(Math.floor(pw / labelWidth), 1));
  const step = pw / items.length, bw = Math.max(Math.min(step - 2, 28), 2);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img">`;
  for (let i = 0; i <= 4; i++) {
    const y = T + ph - (ph * i) / 4;
    s += `<line x1="${L}" x2="${W - R}" y1="${y}" y2="${y}" stroke="var(--grid)" />`;
    s += `<text x="${L - 6}" y="${y + 4}" text-anchor="end">${fmt((max * i) / 4, max < 4 ? 1 : 0)}</text>`;
  }
  items.forEach((d, i) => {
    const v = value(d), h = (v / max) * ph, x = L + i * step + (step - bw) / 2, y = T + ph - h;
    const r = Math.min(4, bw / 2, h);
    const path = h > 0
      ? `M${x},${T + ph} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${T + ph} Z`
      : "";
    s += `<rect class="hit" data-i="${i}" x="${L + i * step}" y="${T}" width="${step}" height="${ph}" fill="transparent" />`;
    s += `<path class="bar" d="${path}" />`;
    if (i % every === 0) s += `<text x="${L + i * step + step / 2}" y="${H - 8}" text-anchor="middle">${label(d)}</text>`;
  });
  s += `<line x1="${L}" x2="${W - R}" y1="${T + ph}" y2="${T + ph}" stroke="var(--text-muted)" /></svg>`;
  el.innerHTML = s + `<div class="tip"></div>`;
  const tipEl = el.querySelector(".tip"), svg = el.querySelector("svg");
  el.querySelectorAll(".hit").forEach(hit => {
    hit.addEventListener("mousemove", () => {
      const i = +hit.dataset.i, d = items[i];
      const scale = svg.getBoundingClientRect().width / W;
      const v = value(d), y = T + ph - (v / max) * ph;
      tipEl.innerHTML = tip(d);
      tipEl.style.left = (L + i * step + step / 2) * scale + "px";
      tipEl.style.top = y * scale + "px";
      tipEl.style.display = "block";
    });
    hit.addEventListener("mouseleave", () => (tipEl.style.display = "none"));
  });
}

const METRICS = [
  { key: "minutes", name: "說話分鐘", unit: "分鐘", d: 1 },
  { key: "count", name: "次數", unit: "次", d: 0 },
  { key: "chars", name: "字數", unit: "字", d: 0 },
];
let metric = METRICS[0];
const metricEl = document.getElementById("metric");
function renderDaily() {
  metricEl.innerHTML = METRICS.map(x =>
    `<button type="button" data-k="${x.key}" aria-pressed="${x === metric}">${x.name}</button>`).join("");
  document.getElementById("daily-title").textContent = `近 ${DATA.daily.length} 天每日${metric.name}`;
  barChart(document.getElementById("daily"), DATA.daily, {
    value: d => d[metric.key],
    label: d => d.date.slice(5).replace("-", "/"),
    tip: d => `${d.date}<br>${fmt(d.minutes, 1)} 分鐘・${fmt(d.count)} 次・${fmt(d.chars)} 字`,
  });
}
metricEl.addEventListener("click", e => {
  const b = e.target.closest("button");
  if (!b) return;
  metric = METRICS.find(x => x.key === b.dataset.k);
  renderDaily();
});
renderDaily();

function renderHourly() {
  barChart(document.getElementById("hourly"), DATA.hourly.map((c, h) => ({ h, c })), {
    value: d => d.c,
    label: d => d.h,
    labelWidth: 30,
    tip: d => `${d.h}:00–${d.h}:59<br>${fmt(d.c)} 次`,
  });
}
renderHourly();
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { renderDaily(); renderHourly(); }, 150);
});

const rows = DATA.monthly.map(r => `<tr><td>${r.month}</td><td>${fmt(r.count)}</td>
  <td>${fmt(r.minutes, 1)}</td><td>${fmt(r.chars)}</td><td>${fmt(r.saved_minutes, 1)}</td>
  <td>${fmt(r.avg_latency, 1)}</td><td>${fmt(r.errors)}</td></tr>`).join("");
document.getElementById("monthly").innerHTML =
  `<thead><tr><th>月份</th><th>次數</th><th>說話（分鐘）</th><th>字數</th><th>省下（分鐘）</th><th>平均回應（秒）</th><th>失敗</th></tr></thead>
   <tbody>${rows || `<tr><td colspan="7" class="muted">還沒有紀錄</td></tr>`}</tbody>`;

document.getElementById("note").textContent =
  `「省下時間」以每分鐘打 ${DATA.typing_cpm} 字估算（打字所需時間減去說話與等待時間），可在設定檔 stats.typing_cpm 調整。` +
  "統計只記錄時間與字數，不記錄任何說話內容，資料只存在這台電腦。";
</script>
</body>
</html>
"""


def render_dashboard(summary: dict) -> str:
    data = json.dumps(summary, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA__", data)


def write_dashboard(summary: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(summary), encoding="utf-8")
    return path
