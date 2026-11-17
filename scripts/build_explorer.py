#!/usr/bin/env python3
"""
Builds a self-contained, offline HTML "results explorer" for a campaign:
every run x protocol in a sortable / filterable table, the per-condition summary (mean ± 95% CI), and the
per-frame latency trace of any run (click a row) with stalls marked.

Usage:  python scripts/build_explorer.py <campaign>   ->  results/campaigns/<campaign>/analysis/results_explorer.html
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_campaign import load_campaign, summarize  # noqa: E402

COLS = ["run_id", "rep", "order_index", "profile", "buffer", "protocol", "ok", "lat_mean_ms", "lat_p50_ms",
        "lat_p95_ms", "stall_ratio_pct", "stall_count", "longest_stall_ms", "ttff_ms", "fps", "buffer_mean_s",
        "wire_kbps", "wire_drop_pct", "decode_rate", "clock_unc_ms", "path_rtt_min_ms", "fail_reason"]


def clean(v):
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 3)
    if hasattr(v, "item"):
        return clean(v.item())
    return v


def main():
    name = sys.argv[1]
    cdir, meta, runs, df = load_campaign(name)
    rows = [{c: clean(r.get(c)) for c in COLS} for r in df.to_dict("records")]
    summ = summarize(df)
    srows = [{k: clean(v) for k, v in r.items()} for r in summ.to_dict("records")]

    traces = {}
    for r in runs:
        b = r.get("browser")
        if not b:
            continue
        tr = {"warmup": b["meta"]["warmupSec"] * 1000, "end": b["meta"]["endRelMs"], "p": {}}
        for proto, rep in b["protocols"].items():
            pts = [[f[0], f[1]] for f in rep["frames"] if f[1] is not None and f[1] >= 0]
            tr["p"][proto] = {"lat": pts, "stalls": [[s[0], s[1]] for s in rep.get("stalls", [])],
                              "events": rep.get("events", [])[:60]}
        traces[r["run_id"]] = tr

    client = (meta.get("topology") or {}).get("client") or {}
    os_name = client.get("os", "")
    if os_name.startswith("Windows-10-10.0."):   # platform.platform() reports Windows 11 as "Windows-10-10.0.2xxxx"
        build = int(os_name.split(".")[2].split("-")[0])
        client["os"] = f"Windows {'11' if build >= 22000 else '10'} (build {build})"
    data = {"meta": {k: meta.get(k) for k in ("campaign", "created", "plan_name", "reps", "duration_s", "warmup_s",
                                               "topology", "physical_link", "conditions")},
            "rows": rows, "summary": srows, "traces": traces}
    html = TEMPLATE.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    out = cdir / "analysis"
    out.mkdir(exist_ok=True)
    (out / "results_explorer.html").write_text(html, encoding="utf-8")
    print(f"[explorer] {out / 'results_explorer.html'} ({len(html) / 1e6:.1f} MB, {len(rows)} protocol-runs)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Campaign Results Explorer</title>
<style>
  :root {
    color-scheme: light;
    --surface-0: #f4f3ef; --surface-1: #fcfcfb; --border: #dddcd6;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --muted: #7a7974;
    --grid: #e4e3df; --stall: rgba(227, 73, 72, 0.18); --stall-solid: #e34948;
    --webrtc: #2a78d6; --llhls: #eb6834; --httpflv: #1baf7a; --accent: #2a78d6;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) {
      color-scheme: dark;
      --surface-0: #121211; --surface-1: #1a1a19; --border: #33322f;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --muted: #8f8e87;
      --grid: #2c2b28; --stall: rgba(230, 103, 103, 0.22); --stall-solid: #e66767;
      --webrtc: #3987e5; --llhls: #d95926; --httpflv: #199e70; --accent: #3987e5;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--surface-0); color: var(--text-primary); }
  main { max-width: 1280px; margin: 0 auto; padding: 20px 16px 48px; }
  h1 { font-size: 1.35rem; margin: 0 0 4px; }
  h2 { font-size: 1.02rem; margin: 26px 0 10px; }
  .sub { color: var(--text-secondary); font-size: 0.86rem; }
  .card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
  .setup { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 14px; }
  .setup .k { color: var(--muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: .03em; }
  .setup .v { font-size: 0.88rem; margin-top: 2px; }
  .filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 10px; font-size: 0.86rem; color: var(--text-secondary); }
  select, input[type=search] { font: inherit; padding: 5px 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-1); color: var(--text-primary); }
  label.chk { display: inline-flex; gap: 5px; align-items: center; }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; vertical-align: middle; }
  .table-wrap { overflow: auto; max-height: 520px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface-1); }
  table { border-collapse: collapse; width: 100%; font-size: 0.8rem; font-variant-numeric: tabular-nums; }
  th, td { padding: 5px 8px; border-bottom: 1px solid var(--grid); text-align: right; white-space: nowrap; }
  th { position: sticky; top: 0; background: var(--surface-1); color: var(--text-secondary); font-weight: 600; cursor: pointer; user-select: none; }
  th:hover { color: var(--text-primary); }
  td.l, th.l { text-align: left; }
  tbody tr:hover { background: color-mix(in srgb, var(--accent) 8%, transparent); cursor: pointer; }
  tbody tr.sel { background: color-mix(in srgb, var(--accent) 16%, transparent); }
  .fail { color: var(--stall-solid); font-weight: 600; }
  #trace { width: 100%; height: 360px; display: block; }
  .trace-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }
  .legend { display: flex; gap: 14px; font-size: 0.8rem; color: var(--text-secondary); }
  .legend i { display: inline-block; width: 16px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 5px; }
  #tip { position: fixed; pointer-events: none; background: var(--surface-1); border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 0.78rem; box-shadow: 0 4px 14px rgba(0,0,0,.12); display: none; font-variant-numeric: tabular-nums; }
  .events { font-size: 0.76rem; color: var(--text-secondary); margin-top: 8px; max-height: 110px; overflow: auto; }
  .note { font-size: 0.78rem; color: var(--muted); margin-top: 8px; }
</style>
</head>
<body>
<main>
  <h1 id="title">Campaign results</h1>
  <div class="sub" id="subtitle"></div>
  <div class="setup" id="setup"></div>

  <h2>Per-condition summary (mean ± 95% CI over repetitions)</h2>
  <div class="filters">
    <span>Condition</span><select id="condSel"></select>
    <span id="protoChecks"></span>
  </div>
  <div class="table-wrap" style="max-height:360px"><table id="sumTable"></table></div>

  <h2>All runs (click a row to see its trace)</h2>
  <div class="filters"><input type="search" id="q" placeholder="filter: e.g. rtt_160 or r03" size="28" /><span id="count"></span></div>
  <div class="table-wrap"><table id="runTable"></table></div>

  <h2>Run trace</h2>
  <div class="card">
    <div class="trace-head">
      <div><b id="traceTitle">Select a run</b> <span class="sub" id="traceSub"></span></div>
      <div class="legend">
        <span><i style="background:var(--webrtc)"></i>WebRTC</span>
        <span><i style="background:var(--llhls)"></i>LL-HLS</span>
        <span><i style="background:var(--httpflv)"></i>HTTP-FLV</span>
        <span><i style="background:var(--stall-solid)"></i>stall</span>
      </div>
    </div>
    <canvas id="trace"></canvas>
    <div class="events" id="events"></div>
    <div class="note">Latency per sampled frame (≈10 Hz per player). Shaded bands at the bottom = stalls (> 200 ms gap between presented frames), one lane per protocol. Dotted line = end of warm-up.</div>
  </div>
</main>
<div id="tip"></div>
<script>
const DATA = /*__DATA__*/null;
const NAME = { webrtc: 'WebRTC', llhls: 'LL-HLS', httpflv: 'HTTP-FLV' };
const PROTOS = ['webrtc', 'llhls', 'httpflv'];
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const $ = (id) => document.getElementById(id);
const f0 = (v) => v == null ? '–' : Math.round(v).toLocaleString();
const f1 = (v) => v == null ? '–' : (+v).toFixed(1);
const f2 = (v) => v == null ? '–' : (+v).toFixed(2);
const pm = (m, h, f) => m == null ? '–' : (h == null ? f(m) : `${f(m)} ± ${f(h)}`);
const condKey = (p, b) => `${p} @ ${(+b).toString()}s`;

// ---------- header / physical setup
(() => {
  const m = DATA.meta, t = m.topology || {}, s = t.server || {}, c = t.client || {}, link = m.physical_link || {};
  $('title').textContent = `Results explorer: ${m.campaign}`;
  $('subtitle').textContent = `${DATA.rows.length} protocol-runs · ${m.reps} repetitions · ${m.duration_s} s per run (first ${m.warmup_s} s warm-up excluded) · created ${m.created}`;
  const ping = link.ping || {}, dl = link.downlink_tcp || {}, w = link.wifi || {};
  const items = [
    ['Server (media + source + tc/netem)', `${s.host || ''} · ${s.ip || ''}<br>${s.cpu || ''}<br>Linux ${s.kernel || ''} · SRS ${s.srs_version || ''}`],
    ['Viewer (browser + runner)', `${c.host || ''}<br>${c.os || ''}<br>browser ${c.browser_version || ''}`],
    ['Physical path (no emulation)', `ICMP RTT min/median/p95 ${ping.min_ms ?? '–'}/${ping.median_ms ?? '–'}/${ping.p95_ms ?? '–'} ms · loss ${ping.loss_pct ?? '–'}%<br>downlink ≈ ${dl.mbps_median ?? '–'} Mbps (single TCP)<br>${w['Radio type'] ? `${w['Radio type']} ${w['Band'] || ''} ch ${w['Channel']} · signal ${w['Signal']}` : ''}`],
    ['Stream', `${(t.stream || {}).video || ''}<br>${(t.stream || {}).audio || ''}`],
  ];
  $('setup').innerHTML = items.map(([k, v]) => `<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
})();

// ---------- summary table
const conds = [...new Set(DATA.summary.map((r) => condKey(r.profile, r.buffer)))];
$('condSel').innerHTML = '<option value="">All conditions</option>' + conds.map((c) => `<option>${c}</option>`).join('');
$('protoChecks').innerHTML = PROTOS.map((p) => `<label class="chk"><input type="checkbox" checked value="${p}"><span class="swatch" style="background:var(--${p})"></span>${NAME[p]}</label>`).join(' ');
const activeProtos = () => [...document.querySelectorAll('#protoChecks input:checked')].map((i) => i.value);

function renderSummary() {
  const c = $('condSel').value, ps = activeProtos();
  const rows = DATA.summary.filter((r) => (!c || condKey(r.profile, r.buffer) === c) && ps.includes(r.protocol));
  $('sumTable').innerHTML = `<thead><tr><th class="l">Condition</th><th class="l">Protocol</th><th>OK runs</th><th>Mean latency (ms)</th><th>p95 latency (ms)</th><th>Stall ratio (%)</th><th>Stalls / run</th><th>Start-up (ms)</th><th>FPS</th><th>Wire (kbps)</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td class="l">${condKey(r.profile, r.buffer)}</td><td class="l"><span class="swatch" style="background:var(--${r.protocol})"></span> ${NAME[r.protocol]}</td>
      <td>${r.ok_runs}/${r.runs}</td><td>${pm(r.lat_mean_ms_mean, r.lat_mean_ms_ci95, f0)}</td><td>${pm(r.lat_p95_ms_mean, r.lat_p95_ms_ci95, f0)}</td>
      <td>${pm(r.stall_ratio_pct_mean, r.stall_ratio_pct_ci95, f1)}</td><td>${pm(r.stall_count_mean, r.stall_count_ci95, f1)}</td>
      <td>${pm(r.ttff_ms_mean, r.ttff_ms_ci95, f0)}</td><td>${f1(r.fps_mean)}</td><td>${f0(r.wire_kbps_mean)}</td></tr>`).join('') + '</tbody>';
}

// ---------- all-runs table
const COLS = [
  ['run_id', 'Run', 'l', (v) => v], ['rep', 'Rep', '', (v) => v], ['profile', 'Profile', 'l', (v) => v], ['buffer', 'Buffer (s)', '', (v) => v],
  ['protocol', 'Protocol', 'l', (v) => `<span class="swatch" style="background:var(--${v})"></span> ${NAME[v]}`],
  ['lat_mean_ms', 'Mean lat (ms)', '', f0], ['lat_p95_ms', 'p95 lat (ms)', '', f0], ['stall_ratio_pct', 'Stall (%)', '', f1],
  ['stall_count', 'Stalls', '', (v) => v ?? '–'], ['longest_stall_ms', 'Longest stall (ms)', '', f0], ['ttff_ms', 'Start-up (ms)', '', f0],
  ['fps', 'FPS', '', f1], ['buffer_mean_s', 'Buffer (s)', '', f2], ['wire_kbps', 'Wire (kbps)', '', f0],
  ['decode_rate', 'Decode', '', (v) => v == null ? '–' : `${Math.round(v * 100)}%`], ['clock_unc_ms', 'Clock ± (ms)', '', f1],
];
let sortKey = 'order_index', sortDir = 1, selected = null;
function renderRuns() {
  const q = $('q').value.trim().toLowerCase(), c = $('condSel').value, ps = activeProtos();
  let rows = DATA.rows.filter((r) => ps.includes(r.protocol) && (!c || condKey(r.profile, r.buffer) === c) &&
    (!q || `${r.run_id} ${r.profile} ${r.protocol}`.toLowerCase().includes(q)));
  rows.sort((a, b) => { const x = a[sortKey], y = b[sortKey]; return (x == null) - (y == null) || (x < y ? -1 : x > y ? 1 : 0) * sortDir; });
  $('count').textContent = `${rows.length} rows`;
  $('runTable').innerHTML = '<thead><tr>' + COLS.map(([k, h, cl]) => `<th class="${cl}" data-k="${k}">${h}${sortKey === k ? (sortDir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('') + '</tr></thead><tbody>' +
    rows.map((r) => `<tr data-run="${r.run_id}" class="${r.run_id === selected ? 'sel' : ''}">` + COLS.map(([k, , cl, f]) => {
      if (k === 'stall_ratio_pct' && !r.ok) return `<td class="fail" title="${r.fail_reason || ''}">fail</td>`;
      return `<td class="${cl}">${f(r[k])}</td>`; }).join('') + '</tr>').join('') + '</tbody>';
  document.querySelectorAll('#runTable th').forEach((th) => th.onclick = () => { const k = th.dataset.k; sortDir = sortKey === k ? -sortDir : 1; sortKey = k; renderRuns(); });
  document.querySelectorAll('#runTable tbody tr').forEach((tr) => tr.onclick = () => { selected = tr.dataset.run; renderRuns(); drawTrace(selected); });
}

// ---------- trace chart (canvas + hover readout)
let traceGeom = null;
function drawTrace(runId) {
  const tr = DATA.traces[runId];
  const cv = $('trace'), dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
  if (!tr) { traceGeom = null; return; }
  const r0 = DATA.rows.find((r) => r.run_id === runId);
  $('traceTitle').textContent = runId;
  $('traceSub').textContent = r0 ? `profile ${r0.profile} · buffer target ${r0.buffer} s · repetition ${r0.rep}` : '';
  const padL = 56, padR = 12, padT = 10, lane = 7, padB = 26 + lane * 3 + 6;
  let ymax = 500;
  PROTOS.forEach((p) => (tr.p[p]?.lat || []).forEach(([, l]) => { if (l > ymax) ymax = l; }));
  ymax = Math.ceil(ymax * 1.08 / 500) * 500;
  const X = (t) => padL + (t / tr.end) * (w - padL - padR), Y = (v) => padT + (1 - v / ymax) * (h - padT - padB);
  ctx.font = '11px system-ui, sans-serif'; ctx.lineWidth = 1;
  const step = ymax > 8000 ? 2000 : ymax > 4000 ? 1000 : ymax > 2000 ? 500 : 250;
  for (let v = 0; v <= ymax; v += step) {
    ctx.strokeStyle = css('--grid'); ctx.beginPath(); ctx.moveTo(padL, Y(v)); ctx.lineTo(w - padR, Y(v)); ctx.stroke();
    ctx.fillStyle = css('--muted'); ctx.fillText(`${v / 1000} s`, 8, Y(v) + 4);
  }
  for (let s = 0; s <= tr.end / 1000; s += 5) { ctx.fillStyle = css('--muted'); ctx.fillText(`${s}s`, X(s * 1000) - 8, h - 6); }
  ctx.setLineDash([3, 3]); ctx.strokeStyle = css('--text-secondary');
  ctx.beginPath(); ctx.moveTo(X(tr.warmup), padT); ctx.lineTo(X(tr.warmup), h - padB); ctx.stroke(); ctx.setLineDash([]);
  PROTOS.forEach((p, i) => {
    const d = tr.p[p]; if (!d) return;
    ctx.strokeStyle = css(`--${p}`); ctx.lineWidth = 2; ctx.beginPath();
    let prev = null;
    for (const [t, l] of d.lat) { if (prev === null || t - prev > 400) ctx.moveTo(X(t), Y(l)); else ctx.lineTo(X(t), Y(l)); prev = t; }
    ctx.stroke();
    const ly = h - padB + 8 + i * lane;
    ctx.fillStyle = css('--grid'); ctx.fillRect(padL, ly, w - padL - padR, lane - 2);
    ctx.fillStyle = css('--stall-solid');
    for (const [s, dur] of d.stalls) ctx.fillRect(X(s), ly, Math.max(2, X(s + dur) - X(s)), lane - 2);
  });
  traceGeom = { tr, X, Y, padL, padR, w, h, padB };
  const ev = PROTOS.flatMap((p) => (tr.p[p]?.events || []).filter((e) => e[1] !== 'buffer').map((e) => `${(e[0] / 1000).toFixed(1)} s · ${NAME[p]} · ${e[1]}: ${e[2]}`));
  $('events').innerHTML = ev.length ? '<b>Player events:</b><br>' + ev.slice(0, 40).join('<br>') : '';
}
$('trace').addEventListener('mousemove', (e) => {
  const tip = $('tip');
  if (!traceGeom) { tip.style.display = 'none'; return; }
  const rect = e.target.getBoundingClientRect(), x = e.clientX - rect.left;
  const { tr, padL, padR, w } = traceGeom;
  if (x < padL || x > w - padR) { tip.style.display = 'none'; return; }
  const t = ((x - padL) / (w - padL - padR)) * tr.end;
  const lines = PROTOS.map((p) => {
    const d = tr.p[p]; if (!d || !d.lat.length) return null;
    let best = d.lat[0]; for (const pt of d.lat) if (Math.abs(pt[0] - t) < Math.abs(best[0] - t)) best = pt;
    const stalled = d.stalls.some(([s, dur]) => t >= s && t <= s + dur);
    return `<span class="swatch" style="background:var(--${p})"></span> ${NAME[p]}: ${Math.abs(best[0] - t) < 600 ? best[1] + ' ms' : '–'}${stalled ? ' <b class="fail">stalled</b>' : ''}`;
  }).filter(Boolean);
  tip.innerHTML = `<b>t = ${(t / 1000).toFixed(1)} s</b><br>` + lines.join('<br>');
  tip.style.display = 'block'; tip.style.left = `${e.clientX + 14}px`; tip.style.top = `${e.clientY + 10}px`;
});
$('trace').addEventListener('mouseleave', () => { $('tip').style.display = 'none'; });

$('condSel').onchange = () => { renderSummary(); renderRuns(); };
document.querySelectorAll('#protoChecks input').forEach((i) => i.onchange = () => { renderSummary(); renderRuns(); });
$('q').oninput = renderRuns;
window.addEventListener('resize', () => selected && drawTrace(selected));
renderSummary(); renderRuns();
const first = DATA.rows.find((r) => DATA.traces[r.run_id]);
if (first) { selected = first.run_id; renderRuns(); drawTrace(selected); }
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
