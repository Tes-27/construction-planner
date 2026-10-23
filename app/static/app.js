/* Construction Planner — หน้าจอ (vanilla JS) */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const TRADE_COLOR = { STR: "var(--str)", ARCH: "var(--arch)", EE: "var(--ee)", SN: "var(--sn)", PRELIM: "var(--prelim)" };
const TRADE_NAME = { STR: "โครงสร้าง", ARCH: "สถาปัตย์", EE: "ไฟฟ้า", SN: "สุขาภิบาล", PRELIM: "เตรียมการ", FP: "ดับเพลิง" };
const S = { state: null, sched: null, view: "overview", floor: null, gGroup: "time", gZoom: 4, boq: null };

const day = iso => new Date(iso + "T00:00:00");
const iso = d => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const addDays = (d, n) => new Date(d.getTime() + n * 86400000);
const diffDays = (a, b) => Math.round((b - a) / 86400000);
const fd = s => s ? day(s).toLocaleDateString("th-TH", { day: "numeric", month: "short", year: "2-digit" }) : "–";
const fdl = s => s ? day(s).toLocaleDateString("th-TH", { day: "numeric", month: "long", year: "numeric" }) : "–";
const money = (v, dp = 0) => Number(v || 0).toLocaleString("th-TH", { minimumFractionDigits: dp, maximumFractionDigits: dp });
const pc = (v, dp = 1) => (v == null ? "–" : Number(v).toFixed(dp) + "%");
const pclass = p => p <= 0 ? "p0" : p < 30 ? "p1" : p < 60 ? "p2" : p < 90 ? "p3" : p < 100 ? "p4" : "p5";
const dataDate = () => $("#dataDate").value;

async function api(path, body) {
  const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg, isErr) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast" + (isErr ? " err" : ""); t.style.display = "block";
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.style.display = "none"), isErr ? 5000 : 2200);
}
function openPop(html) { $("#pop").innerHTML = html; $("#popBg").classList.add("on"); }
function closePop() { $("#popBg").classList.remove("on"); }
$("#popBg").addEventListener("click", e => { if (e.target.id === "popBg") closePop(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closePop(); });

/* ───────────── boot */
async function boot() {
  const pr = await api("/api/projects");
  S.project = pr.current;
  $("#projSel").innerHTML = pr.projects.map(p => `<option ${p === pr.current ? "selected" : ""}>${esc(p)}</option>`).join("");
  $("#projSel").onchange = async e => { await api("/api/open", { name: e.target.value }); S.project = e.target.value; S.floor = null; S.boq = null; S.dateSet = false; await refresh(); };
  $("#dataDate").onchange = () => { try { localStorage.setItem("cp.date." + S.project, dataDate()); } catch {} refresh(); };
  $$("#tabs button").forEach(b => b.onclick = () => show(b.dataset.v));
  let v = "overview"; try { v = localStorage.getItem("cp.view") || v; } catch {}
  await refresh();
  show(v);
}
function show(v) {
  S.view = v;
  try { localStorage.setItem("cp.view", v); } catch {}
  $$("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  $$(".view").forEach(s => s.classList.toggle("on", s.id === "v-" + v));
  render();
}
async function refresh() {
  S.state = await api("/api/state");
  if (!S.dateSet) {  // วันที่ข้อมูล: ที่เคยเลือก → วันนี้ (ถ้ามีความคืบหน้าแล้ว) → วันเริ่มโครงการ
    let d = null; try { d = localStorage.getItem("cp.date." + S.project); } catch {}
    const today = S.state.today, start = S.state.meta.start_date;
    $("#dataDate").value = d || (S.state.progress_last || today < start ? today : start);
    S.dateSet = true;
  }
  S.sched = await api("/api/schedule?date=" + dataDate());
  $("#projName").textContent = " · " + S.state.meta.name;
  document.title = S.state.meta.short + " · Construction Planner";
  render();
}
function render() {
  if (!S.state) return;
  S.seq = (S.seq || 0) + 1;  // ใช้ทิ้งผลลัพธ์ของการโหลดรอบเก่า
  ({ overview: renderOverview, gantt: renderGantt, progress: renderProgress, plan: renderPlan, scurve: renderSCurve,
     milestones: renderMilestones, changes: renderChanges, boq: renderBoq })[S.view]();
}

/* ───────────── overview */
async function renderOverview() {
  const seq = S.seq, st = S.state, sc = await api("/api/scurve?date=" + dataDate());
  if (seq !== S.seq || S.view !== "overview") return;
  const at = sc.series.filter(r => r.date <= dataDate()).pop() || sc.series[0];
  const plan = at.baseline, act = at.actual ?? 0;
  const spi = plan > 0 ? act / plan : null;
  const cv = st.contract_value;
  const fin = S.sched.finish, cfin = S.sched.contract_finish;
  const dl = (await api("/api/changes?date=" + dataDate())).delay;
  if (seq !== S.seq || S.view !== "overview") return;
  const late = diffDays(day(cfin), day(fin));
  const ms = S.sched.milestones;
  const billed = ms.filter(m => ["submitted", "approved", "paid"].includes(m.status)).reduce((s, m) => s + m.pct, 0);
  $("#kpis").innerHTML = [
    ["แผน ณ วันที่", pc(plan), sc.has_baseline ? "ตาม Baseline: " + sc.baseline_name : "ยังไม่ล็อก Baseline (ใช้แผนปัจจุบัน)"],
    ["ผลงานจริง", pc(act), "มูลค่าผลงาน " + money(act / 100 * cv) + " บาท"],
    ["SPI", spi == null || plan < 1 ? "–" : spi.toFixed(2), spi == null || plan < 1 ? "ยังเร็วเกินไปที่จะวัด" : spi >= 1 ? "เร็วกว่าหรือตรงแผน" : "ช้ากว่าแผน"],
    ["คาดว่าเสร็จ", fd(fin), (late > 0 ? `ช้ากว่าสัญญา ${late} วัน` : `ก่อนสัญญา ${-late} วัน`) + ` · สัญญา ${fd(cfin)}${S.sched.eot_days ? " (รวม EOT " + S.sched.eot_days + " วัน)" : ""}`],
    ["ค่าปรับประมาณการ", money(dl.ld_forecast), dl.late_days ? `${dl.late_days} วัน × ${money(dl.ld_per_day)}${dl.ld_forecast >= dl.ld_cap - 1 ? " · ถึงเพดานแล้ว" : ""}` : "ไม่ล่าช้า"],
    ["เบิกแล้ว", pc(billed * 100), money(billed * cv) + " บาท (ก่อน VAT)"],
    ["มูลค่าสัญญา", money(cv), st.contract_value !== st.contract_original ? `รวม VO ${money(st.contract_value - st.contract_original)} · ไม่รวม VAT` : "บาท ไม่รวม VAT"],
  ].map(([k, v, s]) => `<div class="card"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${esc(s)}</div></div>`).join("");
  drawCurve($("#miniCurve"), sc, 260);
  const next = ms.filter(m => ["ready", "planned"].includes(m.status)).slice(0, 4);
  $("#nextMs").innerHTML = next.length ? next.map(m => {
    const done = m.checks.filter(c => c.ok).length;
    return `<div style="display:flex;gap:10px;align-items:center;padding:7px 0;border-bottom:1px dashed var(--line)">
      <b style="min-width:58px">งวด ${esc(m.no)}</b>
      <span class="pill ${m.ready ? "ok" : ""}">${m.ready ? "พร้อมเบิก" : `เงื่อนไขครบ ${done}/${m.checks.length}`}</span>
      <span class="small" style="flex:1">${money(m.amount)} บาท${m.ready ? ` · <a href="/billing/${encodeURIComponent(m.no)}?date=${dataDate()}" target="_blank">ใบขอเบิก</a>` : ""}</span>
      <span class="small muted">คาดว่า ${fd(m.forecast)}</span></div>`;
  }).join("") : `<p class="muted">เบิกครบทุกงวดแล้ว</p>`;
  $("#validation").innerHTML = st.validation.map(([k, t]) => `<li class="${k}">${esc(t)}</li>`).join("");
  $("#assumptions").innerHTML = (st.meta.assumptions || []).map(t => `<li class="note">${esc(t)}</li>`).join("") || `<li class="ok">ไม่มี</li>`;
  $("#srcIssues").innerHTML = (st.meta.source_issues || []).map(t => `<li class="warn">${esc(t)}</li>`).join("") || `<li class="ok">ไม่มี</li>`;
}

/* ───────────── Gantt */
$$("#gGroup button").forEach(b => b.onclick = () => { S.gGroup = b.dataset.g; $$("#gGroup button").forEach(x => x.classList.toggle("on", x === b)); renderGantt(); });
$$("#gZoom button").forEach(b => b.onclick = () => { S.gZoom = +b.dataset.z; $$("#gZoom button").forEach(x => x.classList.toggle("on", x === b)); renderGantt(); });
$("#gCrit").onchange = () => renderGantt();
$("#btnXlsx").onclick = () => (location.href = "/api/export/schedule.xlsx?date=" + dataDate());
$("#btnPrint").onclick = () => window.print();
$("#btnBaseline").onclick = () => {
  openPop(`<h4>ล็อก Baseline</h4><div class="sub">เก็บวันเริ่ม-เสร็จของทุกกิจกรรมตอนนี้ไว้เป็นแผนอ้างอิง ใช้เป็นเส้น "แผน" ใน S-Curve</div>
    <div class="row"><label>ชื่อ</label><input id="blName" value="baseline-${dataDate()}"></div>
    <div class="actions"><button onclick="closePop()">ยกเลิก</button><button class="primary" id="blOk">ล็อก</button></div>`);
  $("#blOk").onclick = async () => {
    try { const r = await api("/api/baseline", { name: $("#blName").value, date: dataDate() }); closePop(); toast("ล็อก Baseline: " + r.name); await refresh(); }
    catch (e) { toast(e.message, true); }
  };
};

function ganttRows() {
  let acts = S.sched.activities.slice();
  if ($("#gCrit").checked) acts = acts.filter(a => a.critical);
  const st = S.state, tname = Object.fromEntries(st.tasks.map(t => [t.task_id, t.name]));
  if (S.gGroup === "time") return acts.map(a => ({ a }));
  const key = S.gGroup === "floor" ? a => a.floors : a => a.task_id;
  const order = S.gGroup === "floor"
    ? ["SITE", "FDN", "1", "2", "3", "4", "5", "6", "7", "RF"]
    : st.tasks.map(t => t.task_id);
  const groups = {};
  acts.forEach(a => { const k = key(a); (groups[k] = groups[k] || []).push(a); });
  const keys = Object.keys(groups).sort((x, y) => {
    const ix = order.indexOf(x), iy = order.indexOf(y);
    return (ix < 0 ? 999 : ix) - (iy < 0 ? 999 : iy) || x.localeCompare(y);
  });
  const rows = [];
  const label = k => S.gGroup === "floor" ? (/^\d$/.test(k) ? "ชั้น " + k : k.includes(",") ? "หลายชั้น" : ({ SITE: "ภายนอกอาคาร", FDN: "ฐานราก", RF: "หลังคา" }[k] || k)) : tname[k] || k;
  keys.forEach(k => {
    const g = groups[k], v = g.reduce((s, a) => s + a.value, 0);
    const p = v ? g.reduce((s, a) => s + a.value * a.pct, 0) / v : 0;
    rows.push({ group: label(k), n: g.length, pct: p, start: g.reduce((m, a) => a.start < m ? a.start : m, g[0].start), finish: g.reduce((m, a) => a.finish > m ? a.finish : m, g[0].finish) });
    g.forEach(a => rows.push({ a }));
  });
  return rows;
}

function renderGantt() {
  if (!S.sched) return;
  const RH = 24, rows = ganttRows(), px = S.gZoom;
  const acts = S.sched.activities;
  const minD = addDays(day(S.sched.start), -7);
  const ends = [S.sched.finish, S.sched.contract_finish, ...acts.map(a => a.b_finish).filter(Boolean)].sort();
  const maxD = addDays(day(ends[ends.length - 1]), 21);
  const W = Math.max(600, diffDays(minD, maxD) * px), H = rows.length * RH + 30;
  const X = s => diffDays(minD, day(s)) * px;
  S.gX = X;
  $("#gInfo").textContent = `${acts.length} กิจกรรม · แผนเสร็จ ${fd(S.sched.finish)} · สัญญา ${fd(S.sched.contract_finish)}` + (S.sched.baseline ? ` · Baseline: ${S.sched.baseline}` : "");
  // left
  $("#gLeft").innerHTML = `<div style="height:30px" class="g-row group"><span class="g-c name">◆ งวดงาน</span></div>` + rows.map(r => r.a
    ? `<div class="g-row" data-id="${r.a.act_id}" title="${esc(r.a.name)}"><span class="g-c name">${r.a.critical && !r.a.auto_time ? '<span class="crit-dot">●</span> ' : ""}${esc(r.a.name)}</span><span class="g-c w1">${r.a.duration}</span><span class="g-c w2">${fd(r.a.start)}</span><span class="g-c w2">${fd(r.a.finish)}</span><span class="g-c w3">${r.a.pct ? Math.round(r.a.pct) : ""}</span></div>`
    : `<div class="g-row group"><span class="g-c name">${esc(r.group)} <span class="muted small">(${r.n})</span></span><span class="g-c w2">${fd(r.start)}</span><span class="g-c w2">${fd(r.finish)}</span><span class="g-c w3">${Math.round(r.pct)}</span></div>`).join("");
  // header (months + weeks)
  let hd = "";
  for (let d = new Date(minD.getFullYear(), minD.getMonth(), 1); d < maxD; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
    const x = Math.max(0, X(iso(d))), nx = X(iso(new Date(d.getFullYear(), d.getMonth() + 1, 1)));
    hd += `<line x1="${x}" x2="${x}" y1="0" y2="52" stroke="#d9dee4"/>`;
    if (nx - x > 34) hd += `<text x="${x + 4}" y="18" font-size="12" fill="#52606d">${d.toLocaleDateString("th-TH", { month: px >= 4 ? "short" : "narrow", year: "2-digit" })}</text>`;
  }
  if (px >= 4) for (let d = new Date(minD); d < maxD; d = addDays(d, 1)) {
    if (d.getDay() !== 1) continue;
    const x = X(iso(d));
    hd += `<line x1="${x}" x2="${x}" y1="32" y2="52" stroke="#e8ebef"/>` + (px >= 9 ? `<text x="${x + 2}" y="46" font-size="10" fill="#8a96a3">${d.getDate()}</text>` : "");
  }
  $("#gHead").innerHTML = `<svg width="${W}" height="52">${hd}</svg>`;
  // body
  let b = "";
  for (let d = new Date(minD.getFullYear(), minD.getMonth() + 1, 1); d < maxD; d = new Date(d.getFullYear(), d.getMonth() + 1, 1))
    b += `<line x1="${X(iso(d))}" x2="${X(iso(d))}" y1="0" y2="${H}" stroke="#eef0f3"/>`;
  // milestones row
  S.sched.milestones.forEach(m => {
    if (!m.forecast) return;
    const x = X(m.forecast) + px;
    b += `<g><title>งวด ${m.no} · ${m.description}\nคาดว่าเบิกได้ ${fd(m.forecast)}${m.baseline_forecast ? " (Baseline " + fd(m.baseline_forecast) + ")" : ""}</title>
      <path d="M${x} 5 l6 7 l-6 7 l-6 -7z" fill="${m.ready ? "var(--ok)" : "#7b8794"}"/>
      <text x="${x}" y="28" font-size="9" text-anchor="middle" fill="#52606d">${m.no}</text></g>`;
  });
  rows.forEach((r, i) => {
    const y = 30 + i * RH;
    if (!r.a) { b += `<rect x="0" y="${y}" width="${W}" height="${RH}" fill="#f3f5f8"/>`; if (r.start) b += `<rect x="${X(r.start)}" y="${y + 9}" width="${Math.max(2, X(r.finish) - X(r.start) + px)}" height="6" fill="#9aa5b1" rx="2"/>`; return; }
    const a = r.a, x1 = X(a.start), x2 = X(a.finish) + px, col = TRADE_COLOR[a.trade] || "#888";
    if (a.b_start) b += `<rect x="${X(a.b_start)}" y="${y + 17}" width="${Math.max(2, X(a.b_finish) - X(a.b_start) + px)}" height="4" fill="#c3cad3" rx="1"/>`;
    const op = a.auto_time ? 0.25 : 0.45;
    b += `<g class="bar" data-id="${a.act_id}" style="cursor:pointer"><title>${esc(a.name)}\n${fd(a.start)} – ${fd(a.finish)} · ${a.duration} วันทำงาน\nน้ำหนัก ${a.weight.toFixed(2)}% · คืบหน้า ${a.pct.toFixed(0)}% · float ${a.float} วัน${a.preds ? "\nก่อนหน้า: " + a.preds : ""}</title>
      <rect x="${x1}" y="${y + 4}" width="${Math.max(3, x2 - x1)}" height="13" rx="3" fill="${col}" fill-opacity="${op}" ${a.critical && !a.auto_time ? 'stroke="var(--danger)" stroke-width="1.5"' : ""}/>
      ${a.pct > 0 ? `<rect x="${x1}" y="${y + 4}" width="${Math.max(2, (x2 - x1) * a.pct / 100)}" height="13" rx="3" fill="${col}"/>` : ""}</g>`;
  });
  const tx = X(dataDate()), cx = X(S.sched.contract_finish) + px;
  b += `<line x1="${tx}" x2="${tx}" y1="0" y2="${H}" stroke="var(--danger)" stroke-dasharray="4 3"/><text x="${tx + 3}" y="${H - 4}" font-size="10" fill="var(--danger)">ข้อมูล ณ ${fd(dataDate())}</text>`;
  b += `<line x1="${cx}" x2="${cx}" y1="0" y2="${H}" stroke="#1f2933" stroke-dasharray="6 3"/><text x="${cx + 3}" y="12" font-size="10" fill="#1f2933">สัญญาสิ้นสุด${S.sched.eot_days ? " (รวม EOT)" : ""}</text>`;
  if (S.sched.eot_days) { const ox = X(S.sched.contract_finish_original) + px; b += `<line x1="${ox}" x2="${ox}" y1="0" y2="${H}" stroke="#9aa5b1" stroke-dasharray="2 3"/><text x="${ox + 3}" y="24" font-size="10" fill="#7b8794">สัญญาเดิม</text>`; }
  $("#gRight").innerHTML = `<svg width="${W}" height="${H}">${b}</svg>`;
  const L = $("#gLeft"), R = $("#gRight");
  R.onscroll = () => { L.scrollTop = R.scrollTop; $("#gHead").scrollLeft = R.scrollLeft; };
  L.onwheel = e => { R.scrollTop += e.deltaY; e.preventDefault(); };
  $$("#gLeft .g-row[data-id], #gRight .bar").forEach(el => el.onclick = () => editActivity(el.dataset.id));
  if (!renderGantt._scrolled) { R.scrollLeft = Math.max(0, tx - 300); renderGantt._scrolled = true; }
}

function editActivity(id) {
  const a = S.sched.activities.find(x => x.act_id === id);
  if (!a) return;
  if (a.auto_time) { toast("กิจกรรมนี้คำนวณตามระยะเวลาโครงการอัตโนมัติ"); return; }
  openPop(`<h4>${esc(a.name)}</h4><div class="sub">${esc(a.act_id)} · ${TRADE_NAME[a.trade] || a.trade} · น้ำหนัก ${a.weight.toFixed(2)}% (${money(a.value)} บาท BOQ)</div>
    <div class="row"><label>ชื่อแสดง</label><input id="eaName" value="${esc(a.custom_name)}" placeholder="${esc(a.name)}"></div>
    <div class="row"><label>ระยะเวลา</label><input id="eaDur" type="number" min="0" value="${a.duration}" style="max-width:90px"> <span class="small muted">วันทำงาน</span></div>
    <div class="row"><label>งานก่อนหน้า</label><input id="eaPred" value="${esc(a.preds)}"></div>
    <div class="small muted">รูปแบบ: <code>WALL3FS+2</code> = เริ่มหลัง WALL3 เสร็จ 2 วัน · <code>SS</code> = เริ่มพร้อมกัน · <code>FF</code> = เสร็จพร้อมกัน · คั่นด้วย ;</div>
    <div class="money" style="margin-top:10px"><span>เริ่ม <b>${fd(a.start)}</b></span><span>เสร็จ <b>${fd(a.finish)}</b></span><span>Float <b>${a.float}</b> วัน</span>${a.b_start ? `<span>Baseline <b>${fd(a.b_start)} – ${fd(a.b_finish)}</b></span>` : ""}</div>
    <div class="actions"><button onclick="closePop()">ยกเลิก</button><button class="primary" id="eaOk">บันทึก + คำนวณใหม่</button></div>`);
  $("#eaOk").onclick = async () => {
    try {
      await api("/api/activity/" + id, { duration: +$("#eaDur").value, preds: $("#eaPred").value.trim(), name: $("#eaName").value.trim() });
      closePop(); await refresh(); toast("บันทึกแล้ว · แผนเสร็จ " + fd(S.sched.finish));
    } catch (e) { toast(e.message, true); }
  };
}

/* ───────────── progress grid */
function floorsAvailable() {
  const order = ["FDN", "1", "2", "3", "4", "5", "6", "7", "RF", "SITE"];
  const fs = new Set(S.state.locations.filter(l => l.value > 0).map(l => l.floor));
  return order.filter(f => fs.has(f)).concat([...fs].filter(f => !order.includes(f)));
}
const floorLabel = f => /^\d+$/.test(f) ? "ชั้น " + f : ({ FDN: "ฐานราก", RF: "หลังคา", SITE: "ภายนอก" }[f] || f);

async function renderProgress() {
  const fs = floorsAvailable();
  if (!S.floor || !fs.includes(S.floor)) { try { S.floor = localStorage.getItem("cp.floor"); } catch {} if (!fs.includes(S.floor)) S.floor = fs[0]; }
  $("#floorTabs").innerHTML = fs.map(f => `<button data-f="${f}" class="${f === S.floor ? "on" : ""}">${floorLabel(f)}</button>`).join("");
  $$("#floorTabs button").forEach(b => b.onclick = () => { S.floor = b.dataset.f; try { localStorage.setItem("cp.floor", S.floor); } catch {} renderProgress(); });
  const want = S.floor + "|" + dataDate();
  const g = await api(`/api/grid?floor=${encodeURIComponent(S.floor)}&date=${dataDate()}`);
  if (want !== S.floor + "|" + dataDate()) return;  // ผู้ใช้เปลี่ยนชั้นระหว่างโหลด
  S.grid = g;
  const T = Object.fromEntries(S.state.tasks.map(t => [t.task_id, t]));
  const head = `<thead><tr><th class="rowh corner">${floorLabel(S.floor)}</th>${g.tasks.map(t => `<th data-t="${t}" title="บันทึกทั้งชั้น: ${esc(T[t].name)}"><span class="th-trade">${TRADE_NAME[T[t].trade] || ""}</span>${esc(T[t].name)}</th>`).join("")}</tr></thead>`;
  const body = g.locations.map(l => `<tr><th class="rowh">${esc(l.name)}${l.rtype === "B" ? ' <span class="pill">B</span>' : ""}</th>${g.tasks.map(t => {
    const c = g.cells[t + "|" + l.loc_id];
    if (!c) return `<td class="na"></td>`;
    if (T[t].auto_time) return `<td class="cell auto ${pclass(c.pct)}" title="คิดตามเวลาอัตโนมัติ">${Math.round(c.pct)}</td>`;
    return `<td class="cell ${pclass(c.pct)}" data-t="${t}" data-l="${l.loc_id}" title="${esc(T[t].name)} · ${esc(l.name)} · ${money(c.value)} บาท${c.date ? "\nบันทึกล่าสุด " + fd(c.date) : ""}">${c.pct ? Math.round(c.pct) : "·"}</td>`;
  }).join("")}</tr>`).join("");
  $("#pgTable").innerHTML = head + `<tbody>${body}</tbody>`;
  $$("#pgTable td.cell[data-t]").forEach(td => td.onclick = () => editCells(td.dataset.t, [td.dataset.l]));
  $$("#pgTable thead th[data-t]").forEach(th => th.onclick = () => editCells(th.dataset.t, g.locations.filter(l => g.cells[th.dataset.t + "|" + l.loc_id]).map(l => l.loc_id)));
}

async function editCells(taskId, locIds) {
  const t = S.state.tasks.find(x => x.task_id === taskId);
  if (t.auto_time) return;
  const single = locIds.length === 1;
  const c = single ? S.grid.cells[taskId + "|" + locIds[0]] : null;
  const L = Object.fromEntries(S.grid.locations.map(l => [l.loc_id, l]));
  const bits = c && c.steps ? c.steps.split("") : [];
  const hist = single ? await api(`/api/history?task=${taskId}&loc=${locIds[0]}`) : [];
  const where = single ? L[locIds[0]].name : `ทั้ง${floorLabel(S.floor)} (${locIds.length} พื้นที่)`;
  openPop(`<h4>${esc(t.name)}</h4><div class="sub">${esc(where)} · บันทึกวันที่ ${fd(dataDate())}${single ? ` · ปัจจุบัน ${Math.round(c.pct)}%` : ""}</div>
    <div class="steps">${t.steps.map((s, i) => `<label><input type="checkbox" data-w="${s.w}" ${bits[i] === "1" ? "checked" : ""}> ${esc(s.name)} <span class="w">${s.w}%</span></label>`).join("")}</div>
    <div class="quick">${[0, 25, 50, 75, 90, 100].map(v => `<button data-q="${v}">${v}</button>`).join("")}</div>
    <div class="row"><label>% รวม</label><input id="ecPct" type="number" min="0" max="100" step="1" value="${single ? Math.round(c.pct) : ""}" placeholder="${single ? "" : "ไม่เปลี่ยน"}"></div>
    <div class="row"><label>หมายเหตุ</label><input id="ecNote" value="" placeholder="ไม่บังคับ"></div>
    ${single ? `<div class="row"><label>รูปถ่าย</label>${uploadInput("ecPh")}<span class="small muted" id="ecPhN"></span></div><div id="ecPhList"></div>` : ""}
    ${hist.length ? `<div class="hist">ประวัติ: ${hist.slice(-8).reverse().map(h => `${fd(h.date)} ${h.pct}%${h.note ? " (" + esc(h.note) + ")" : ""}`).join(" · ")}</div>` : ""}
    <div class="actions"><button onclick="closePop()">ยกเลิก</button><button class="primary" id="ecOk">บันทึก</button></div>`);
  if (single) {
    const loadPh = async () => { const list = await api(`/api/photos?loc=${encodeURIComponent(locIds[0])}&task=${taskId}`); $("#ecPhList").innerHTML = list.length ? photoGrid(list.slice(0, 8)) : ""; bindPhotos($("#ecPhList"), list, loadPh); };
    loadPh();
    $("#ecPh").onchange = async e => { try { const r = await uploadPhotos(e.target.files, locIds[0], taskId, $("#ecNote").value); $("#ecPhN").textContent = `แนบแล้ว ${r.length} รูป`; loadPh(); } catch (er) { toast(er.message, true); } };
  }
  const boxes = $$("#pop .steps input");
  const sync = () => { $("#ecPct").value = boxes.reduce((s, b) => s + (b.checked ? +b.dataset.w : 0), 0); };
  boxes.forEach(b => b.onchange = sync);
  $$("#pop .quick button").forEach(b => b.onclick = () => {
    const v = +b.dataset.q; $("#ecPct").value = v;
    let acc = 0, stop = false;  // ขั้นตอนทำตามลำดับ
    boxes.forEach(x => { x.checked = !stop && acc + +x.dataset.w <= v + 1e-9; if (x.checked) acc += +x.dataset.w; else stop = true; });
  });
  $("#ecOk").onclick = async () => {
    const raw = $("#ecPct").value;
    if (raw === "") { toast("ใส่ % หรือเลือกขั้นตอน", true); return; }
    const pct = Math.max(0, Math.min(100, +raw));
    const steps = boxes.map(b => (b.checked ? "1" : "0")).join("");
    try {
      await api("/api/progress", { date: dataDate(), entries: locIds.map(l => ({ task_id: taskId, loc_id: l, pct, steps, note: $("#ecNote").value })) });
      closePop(); toast(`บันทึก ${t.name} ${pct}% · ${where}`);
      S.sched = await api("/api/schedule?date=" + dataDate());
      render();
    } catch (e) { toast(e.message, true); }
  };
}

/* ───────────── แบบแปลน (heatmap) */
S.plan = { mode: "actual", edit: false, slot: null, tool: "rect", draft: [], sel: null };
$$("#planMode button").forEach(b => b.onclick = () => { S.plan.mode = b.dataset.m; $$("#planMode button").forEach(x => x.classList.toggle("on", x === b)); renderPlan(); });
$("#planTrade").onchange = () => { fillTaskSelect(); $("#planTask").value = ""; renderPlan(); };
$("#planTask").onchange = () => renderPlan();
$("#planLabels").onchange = () => renderPlan();
$("#planEdit").onclick = () => { S.plan.edit = !S.plan.edit; S.plan.slot = null; S.plan.draft = []; $("#planEdit").classList.toggle("primary", S.plan.edit); $("#planEdit").textContent = S.plan.edit ? "เสร็จสิ้นการแก้" : "แก้ขอบเขต"; renderPlan(); };
function fillTaskSelect() {
  const tr = $("#planTrade").value;
  $("#planTask").innerHTML = `<option value="">— ทุกหมวดงานย่อย —</option>` + S.state.tasks.filter(t => t.value > 0 && (!tr || t.trade === tr)).map(t => `<option value="${t.task_id}">${esc(t.name)}</option>`).join("");
}
const DIFF = d => d >= -1 ? "#4cb08f" : d >= -10 ? "#fbc56b" : d >= -30 ? "#f08c4a" : "#d64545";
const ACT = p => p <= 0 ? "#dfe3e8" : p < 30 ? "#fde7c2" : p < 60 ? "#fbc56b" : p < 90 ? "#9fd3c7" : p < 100 ? "#4cb08f" : "#1f8a5b";
function polyArea(poly) { let a = 0; for (let i = 0; i < poly.length; i++) { const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % poly.length]; a += x1 * y2 - x2 * y1; } return Math.abs(a / 2); }
function polyCenter(poly) { let x = 0, y = 0; poly.forEach(p => { x += p[0]; y += p[1]; }); return [x / poly.length, y / poly.length]; }

async function renderPlan() {
  if (!S.plans) S.plans = await api("/api/plans");
  if ($("#planTask").options.length <= 1) fillTaskSelect();
  const fs = floorsAvailable().filter(f => S.plans.floor_sheet[f]);
  if (!S.planFloor || !fs.includes(S.planFloor)) S.planFloor = fs.includes(S.floor) ? S.floor : fs[0];
  $("#planFloors").innerHTML = fs.map(f => `<button data-f="${f}" class="${f === S.planFloor ? "on" : ""}">${floorLabel(f)}</button>`).join("");
  $$("#planFloors button").forEach(b => b.onclick = () => { S.planFloor = b.dataset.f; S.plan.sel = null; S.plan.slot = null; S.plan.draft = []; renderPlan(); });
  const seq = S.seq, want = S.planFloor;
  const q = new URLSearchParams({ floor: S.planFloor, date: dataDate(), trade: $("#planTrade").value, task: $("#planTask").value });
  const h = await api("/api/heat?" + q);
  if (seq !== S.seq || want !== S.planFloor) return;
  S.heat = h;
  const sh = S.plans.sheets[h.sheet];
  const img = new Image();
  img.src = "/plans/" + sh.file;
  await img.decode().catch(() => {});
  if (want !== S.planFloor) return;
  const W = img.naturalWidth || 2573, H = img.naturalHeight || 1820;
  S.planWH = [W, H];
  const [vx0, vy0, vx1, vy1] = sh.view || [0, 0, 1, 1];
  const fsz = Math.max(14, (vx1 - vx0) * W / 90);
  const byslot = {}; h.rows.forEach(r => { (byslot[r.slot] = byslot[r.slot] || []).push(r); });
  const mode = S.plan.mode, labels = $("#planLabels").checked;
  const color = r => mode === "diff" ? (r.plan_pct <= 0 && r.pct <= 0 ? "#dfe3e8" : DIFF(r.pct - r.plan_pct)) : ACT(r.pct);
  const P = poly => poly.map(([x, y]) => `${(x * W).toFixed(1)},${(y * H).toFixed(1)}`).join(" ");
  const zones = Object.entries(h.zones).map(([slot, polys]) => ({ slot, polys, area: polys.reduce((a, p) => a + polyArea(p), 0) }))
    .sort((a, b) => (a.slot === "*" ? -1 : b.slot === "*" ? 1 : b.area - a.area));
  let g = "", lab = "";
  zones.forEach(z => {
    const rs = byslot[z.slot] || [];
    const r = rs[0];
    const isOutline = z.slot === "*";
    const ext = isOutline ? (byslot["EXT"] || [])[0] : null;
    const sel = S.plan.edit ? z.slot === S.plan.slot : r && S.plan.sel === r.loc_id;
    if (r) {
      const op = isOutline ? (byslot["*"] && Object.keys(byslot).length > 2 ? 0.28 : 0.55) : 0.6;
      z.polys.forEach(poly => { g += `<polygon class="zone ${sel ? "sel" : ""}" data-loc="${r.loc_id}" points="${P(poly)}" fill="${color(r)}" fill-opacity="${op}" stroke="#52606d" stroke-opacity=".6"/>`; });
    } else if (S.plan.edit) {
      z.polys.forEach(poly => { g += `<polygon class="zone ${sel ? "sel" : ""}" data-slot="${esc(z.slot)}" points="${P(poly)}" fill="#2f6fdf" fill-opacity=".08" stroke="#2f6fdf" stroke-dasharray="6 4"/>`; });
    }
    if (ext) z.polys.forEach(poly => { g += `<polygon class="zone" data-loc="${ext.loc_id}" points="${P(poly)}" fill="none" stroke="${color(ext)}" stroke-width="${fsz * 0.7}" stroke-opacity=".9"/>`; });
    if (r && labels && !isOutline) {
      const big = z.polys.slice().sort((a, b) => polyArea(b) - polyArea(a))[0];
      const [cx, cy] = polyCenter(big);
      const val = mode === "diff" ? (r.pct - r.plan_pct >= 0 ? "+" : "") + Math.round(r.pct - r.plan_pct) : Math.round(r.pct) + "%";
      const small = polyArea(big) * W * H < (fsz * 4) ** 2;
      lab += `<text class="zlabel" x="${cx * W}" y="${cy * H}" text-anchor="middle" font-size="${small ? fsz * 0.7 : fsz}" stroke-width="${fsz / 4}">${esc(r.kind === "room" ? r.name : "")}${r.kind === "room" ? `<tspan x="${cx * W}" dy="${fsz * 1.1}">${val}</tspan>` : val}</text>`;
    }
  });
  // ขอบเขตที่กำลังวาด
  let draft = "";
  if (S.plan.edit && S.plan.draft.length) {
    draft = `<polyline points="${P(S.plan.draft)}" fill="rgba(47,111,223,.15)" stroke="#2f6fdf" stroke-width="3"/>` + S.plan.draft.map(([x, y]) => `<circle cx="${x * W}" cy="${y * H}" r="${fsz / 3}" fill="#2f6fdf"/>`).join("");
  }
  const vb = `${vx0 * W} ${vy0 * H} ${(vx1 - vx0) * W} ${(vy1 - vy0) * H}`;
  $("#planWrap").classList.toggle("editing", S.plan.edit);
  $("#planWrap").innerHTML = `<svg viewBox="${vb}" id="planSvg"><image href="/plans/${sh.file}" x="0" y="0" width="${W}" height="${H}"/>${g}${lab}<g id="drawLayer">${draft}</g></svg>`;
  // legend
  $("#planLegend").innerHTML = (mode === "diff"
    ? [["#4cb08f", "ตามแผนหรือเร็วกว่า"], ["#fbc56b", "ช้า 1–10%"], ["#f08c4a", "ช้า 10–30%"], ["#d64545", "ช้ากว่า 30%"], ["#dfe3e8", "ยังไม่ถึงกำหนด"]]
    : [["#dfe3e8", "0"], ["#fde7c2", "1–29"], ["#fbc56b", "30–59"], ["#9fd3c7", "60–89"], ["#4cb08f", "90–99"], ["#1f8a5b", "100"]])
    .map(([c, t]) => `<span><i style="background:${c}"></i>${t}</span>`).join("") +
    `<span class="muted">· ${esc(sh.title)}${h.sheet_floors.length > 1 ? " (ใช้ร่วมกับ " + h.sheet_floors.map(floorLabel).join(", ") + ")" : ""}${byslot["EXT"] ? " · ขอบหนา = ผนังภายนอก" : ""}${byslot["*"] && S.planFloor !== "SITE" ? " · พื้นจาง = งานทั้งชั้น" : ""}</span>`;
  const svg = $("#planSvg");
  if (S.plan.edit) { bindDraw(svg, W, H); renderSlotList(); return; }
  $$("#planSvg .zone[data-loc]").forEach(el => {
    el.onmousemove = e => {
      const r = h.rows.find(x => x.loc_id === el.dataset.loc);
      $("#tip").innerHTML = `<b>${esc(r.name)}</b><br>ผลงาน ${pc(r.pct)} · แผน ${pc(r.plan_pct)}<br>${money(r.value * S.state.k_contract)} บาท`;
      Object.assign($("#tip").style, { display: "block", left: e.pageX + 14 + "px", top: e.pageY - 10 + "px" });
    };
    el.onmouseleave = () => ($("#tip").style.display = "none");
    el.onclick = () => { S.plan.sel = el.dataset.loc; $$("#planSvg .zone").forEach(z => z.classList.toggle("sel", z.dataset.loc === S.plan.sel)); showLocSide(el.dataset.loc); };
  });
  if (S.plan.sel && h.rows.some(r => r.loc_id === S.plan.sel)) showLocSide(S.plan.sel); else floorSide();
}

function floorSide() {
  const rows = S.heat.rows, v = rows.reduce((a, r) => a + r.value, 0);
  const act = v ? rows.reduce((a, r) => a + r.value * r.pct, 0) / v : 0, pl = v ? rows.reduce((a, r) => a + r.value * r.plan_pct, 0) / v : 0;
  const worst = rows.filter(r => r.kind !== "floor").map(r => ({ ...r, d: r.pct - r.plan_pct })).sort((a, b) => a.d - b.d).slice(0, 8);
  $("#planSide").innerHTML = `<h4>${floorLabel(S.planFloor)}</h4><div class="small muted">${$("#planTask").selectedOptions[0].value ? esc($("#planTask").selectedOptions[0].text) : $("#planTrade").selectedOptions[0].text}</div>
    <div class="money" style="grid-template-columns:1fr 1fr"><span>ผลงาน <b>${pc(act)}</b></span><span>แผน <b>${pc(pl)}</b></span><span>มูลค่า <b>${money(v * S.state.k_contract)}</b></span><span>ส่วนต่าง <b style="color:${act - pl < -1 ? "var(--danger)" : "var(--ok)"}">${(act - pl).toFixed(1)}%</b></span></div>
    <h4 style="margin-top:14px">ช้ากว่าแผนมากที่สุด</h4>${worst.map(r => `<div class="trow" data-loc="${r.loc_id}"><span>${esc(r.name)}</span><span class="pbar"><i style="width:${Math.min(100, r.pct)}%"></i><b style="left:${Math.min(100, r.plan_pct)}%"></b></span><span class="num small">${r.d >= 0 ? "+" : ""}${r.d.toFixed(0)}</span></div>`).join("") || '<p class="muted">–</p>'}
    <p class="small muted" style="margin-top:12px">คลิกห้องบนแบบเพื่อดูรายหมวดและบันทึก % · ขีดดำในแถบ = แผน</p>`;
  $$("#planSide .trow").forEach(el => el.onclick = () => { S.plan.sel = el.dataset.loc; renderPlan(); });
}

async function showLocSide(locId) {
  const d = await api(`/api/locinfo?loc=${encodeURIComponent(locId)}&date=${dataDate()}`);
  const v = d.tasks.reduce((a, t) => a + t.value, 0), act = v ? d.tasks.reduce((a, t) => a + t.value * t.pct, 0) / v : 0;
  $("#planSide").innerHTML = `<h4>${esc(d.loc.name)} <span class="small muted">${floorLabel(d.loc.floor)}</span></h4>
    <div class="small muted">ผลงานรวม ${pc(act)} · ${money(v * S.state.k_contract)} บาท${d.loc.area ? " · ~" + d.loc.area + " ม²" : ""}</div>
    <div style="margin-top:8px">${d.tasks.map(t => `<div class="trow" data-t="${t.task_id}" title="${t.auto_time ? "คิดตามเวลาอัตโนมัติ" : "แตะเพื่อบันทึก %"}"><span>${esc(t.name)}<span class="th-trade">${TRADE_NAME[t.trade] || ""}</span></span>
      <span class="pbar ${t.pct >= 100 ? "ok" : ""}"><i style="width:${Math.min(100, t.pct)}%"></i><b style="left:${Math.min(100, t.plan_pct)}%"></b></span><span class="num small">${Math.round(t.pct)}</span></div>`).join("")}</div>
    <h4 style="margin-top:14px">รูปถ่าย</h4>
    <div class="row" style="margin:4px 0"><select id="phTask" style="flex:1"><option value="">ไม่ระบุหมวด</option>${d.tasks.filter(t => !t.auto_time).map(t => `<option value="${t.task_id}">${esc(t.name)}</option>`).join("")}</select>${uploadInput("phUp")}</div>
    <div id="phList"></div>
    <div class="actions"><button id="sideBack">← ภาพรวมชั้น</button></div>`;
  const loadPh = async () => { const list = await api("/api/photos?loc=" + encodeURIComponent(locId)); $("#phList").innerHTML = photoGrid(list); bindPhotos($("#phList"), list, loadPh); };
  loadPh();
  $("#phUp").onchange = async e => {
    try { const r = await uploadPhotos(e.target.files, locId, $("#phTask").value); toast(`แนบ ${r.length} รูป`); loadPh(); } catch (er) { toast(er.message, true); }
  };
  $("#sideBack").onclick = () => { S.plan.sel = null; $$("#planSvg .zone").forEach(z => z.classList.remove("sel")); floorSide(); };
  $$("#planSide .trow").forEach(el => el.onclick = async () => {
    const t = d.tasks.find(x => x.task_id === el.dataset.t);
    if (t.auto_time) return toast("หมวดนี้คิดตามเวลาอัตโนมัติ");
    S.floor = d.loc.floor;
    S.grid = await api(`/api/grid?floor=${encodeURIComponent(d.loc.floor)}&date=${dataDate()}`);
    editCells(t.task_id, [locId]);
  });
}

/* แก้ขอบเขต: ลากสี่เหลี่ยม / คลิกทีละจุด (ดับเบิลคลิกหรือ Enter เพื่อจบ) */
function renderSlotList() {
  const h = S.heat;
  const slots = [...new Map(h.rows.filter(r => r.slot !== "EXT").map(r => [r.slot, r])).values()];
  $("#planSide").innerHTML = `<h4>แก้ขอบเขต · ${esc(S.plans.sheets[h.sheet].title)}</h4>
    ${h.sheet_floors.length > 1 ? `<p class="small" style="color:var(--warn)">แบบแผ่นนี้ใช้กับ ${h.sheet_floors.map(floorLabel).join(", ")} — แก้ครั้งเดียวมีผลทุกชั้น</p>` : ""}
    <div class="seg" style="margin:6px 0"><button data-tool="rect" class="${S.plan.tool === "rect" ? "on" : ""}">ลากสี่เหลี่ยม</button><button data-tool="poly" class="${S.plan.tool === "poly" ? "on" : ""}">คลิกทีละจุด</button></div>
    <label class="small" style="display:block;margin:4px 0"><input type="checkbox" id="zAdd"> เพิ่มชิ้นต่อจากเดิม (เช่น ทางเดินหลายช่วง)</label>
    <p class="small muted">เลือกพื้นที่ด้านล่าง แล้ววาดบนแบบ · ตัวแดง = ยังไม่มีขอบเขต</p>
    <div class="slot-list">${slots.map(r => `<button data-slot="${esc(r.slot)}" class="${r.slot === S.plan.slot ? "on" : ""}">${h.zones[r.slot] ? "" : '<span class="miss">● </span>'}${esc(r.slot === "*" ? "ทั้งชั้น (เส้นรอบอาคาร)" : r.name)} <span class="small">${esc(r.slot)}</span></button>`).join("")}</div>
    ${S.plan.slot && h.zones[S.plan.slot] ? `<div class="actions"><button id="zDel" style="color:var(--danger)">ลบขอบเขตนี้</button></div>` : ""}`;
  $$("#planSide [data-tool]").forEach(b => b.onclick = () => { S.plan.tool = b.dataset.tool; S.plan.draft = []; renderPlan(); });
  $$("#planSide .slot-list button").forEach(b => b.onclick = () => { S.plan.slot = b.dataset.slot; S.plan.draft = []; renderPlan(); });
  if ($("#zDel")) $("#zDel").onclick = () => saveZone(null);
}
function svgPt(svg, e, W, H) {
  const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  return [+(p.x / W).toFixed(5), +(p.y / H).toFixed(5)];
}
function bindDraw(svg, W, H) {
  const layer = svg.querySelector("#drawLayer");
  let start = null;
  const need = () => { if (!S.plan.slot) { toast("เลือกพื้นที่ทางขวาก่อน", true); return false; } return true; };
  if (S.plan.tool === "rect") {
    svg.onpointerdown = e => { if (!need()) return; start = svgPt(svg, e, W, H); svg.setPointerCapture(e.pointerId); };
    svg.onpointermove = e => {
      if (!start) return;
      const p = svgPt(svg, e, W, H);
      layer.innerHTML = `<rect x="${Math.min(start[0], p[0]) * W}" y="${Math.min(start[1], p[1]) * H}" width="${Math.abs(p[0] - start[0]) * W}" height="${Math.abs(p[1] - start[1]) * H}" fill="rgba(47,111,223,.2)" stroke="#2f6fdf" stroke-width="3"/>`;
    };
    svg.onpointerup = e => {
      if (!start) return;
      const p = svgPt(svg, e, W, H), s0 = start; start = null;
      if (Math.abs(p[0] - s0[0]) < 0.003 || Math.abs(p[1] - s0[1]) < 0.003) { layer.innerHTML = ""; return; }
      const [x0, x1] = [Math.min(s0[0], p[0]), Math.max(s0[0], p[0])], [y0, y1] = [Math.min(s0[1], p[1]), Math.max(s0[1], p[1])];
      saveZone([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]);
    };
  } else {
    svg.onclick = e => { if (!need()) return; S.plan.draft.push(svgPt(svg, e, W, H)); renderPlan(); };
    svg.ondblclick = e => { e.preventDefault(); finishPoly(); };
  }
}
function finishPoly() {
  const d = S.plan.draft.filter((p, i, a) => !i || Math.abs(p[0] - a[i - 1][0]) + Math.abs(p[1] - a[i - 1][1]) > 1e-4);
  if (d.length < 3) { toast("ต้องมีอย่างน้อย 3 จุด", true); return; }
  S.plan.draft = []; saveZone(d);
}
document.addEventListener("keydown", e => {
  if (S.view !== "plan" || !S.plan.edit) return;
  if (e.key === "Enter" && S.plan.draft.length) finishPoly();
  if (e.key === "Escape" && S.plan.draft.length) { S.plan.draft = []; renderPlan(); }
  if (e.key === "Backspace" && S.plan.draft.length && e.target === document.body) { S.plan.draft.pop(); renderPlan(); }
});
async function saveZone(poly) {
  const h = S.heat, slot = S.plan.slot;
  const polys = poly == null ? null : ($("#zAdd") && $("#zAdd").checked && h.zones[slot] ? h.zones[slot].concat([poly]) : [poly]);
  try { await api("/api/zones", { sheet: h.sheet, slot, polys }); toast(poly == null ? "ลบขอบเขตแล้ว" : "บันทึกขอบเขตแล้ว"); }
  catch (e) { toast(e.message, true); }
  renderPlan();
}

/* ───────────── S-curve */
$("#scTrade").onchange = () => renderSCurve();
async function renderSCurve() {
  const tr = $("#scTrade").value;
  const seq = S.seq, sc = await api(`/api/scurve?date=${dataDate()}&trade=${tr}`);
  if (seq !== S.seq) return;
  $("#scInfo").textContent = `มูลค่า BOQ ${money(sc.total_value)} บาท` + (sc.has_baseline ? ` · Baseline: ${sc.baseline_name}` : " · ยังไม่ล็อก Baseline");
  drawCurve($("#scChart"), sc, 420, !tr);
  // ตารางรายเดือน (จุดสุดท้ายของแต่ละเดือน)
  const byM = {};
  sc.series.forEach(r => (byM[r.date.slice(0, 7)] = r));
  const billCum = d => sc.bill_plan.filter(b => b.date <= d).reduce((s, b) => s + b.pct, 0);
  $("#scTable").innerHTML = `<table class="t"><thead><tr><th>เดือน</th><th class="num">แผน</th><th class="num">ผลงานจริง</th><th class="num">คาดการณ์</th><th class="num">ต่าง</th>${tr ? "" : '<th class="num">แผนเบิกสะสม</th>'}</tr></thead><tbody>${Object.values(byM).map(r => {
    const p = r.baseline, dv = r.actual == null ? null : r.actual - p;
    return `<tr><td>${day(r.date).toLocaleDateString("th-TH", { month: "long", year: "numeric" })}</td><td class="num">${pc(r.baseline)}</td><td class="num">${pc(r.actual)}</td><td class="num">${pc(r.forecast)}</td><td class="num" style="color:${dv == null ? "" : dv < 0 ? "var(--danger)" : "var(--ok)"}">${dv == null ? "–" : (dv > 0 ? "+" : "") + dv.toFixed(1)}</td>${tr ? "" : `<td class="num">${pc(billCum(r.date))}</td>`}</tr>`;
  }).join("")}</tbody></table>`;
}

function drawCurve(el, sc, h, withBill = true) {
  const W = Math.max(320, el.clientWidth || 800), H = h, m = { l: 40, r: 14, t: 12, b: 28 };
  const ser = sc.series;
  if (!ser.length) { el.innerHTML = ""; return; }
  const t0 = day(ser[0].date), t1 = day(ser[ser.length - 1].date);
  const X = d => m.l + (W - m.l - m.r) * diffDays(t0, day(d)) / Math.max(1, diffDays(t0, t1));
  const Y = v => m.t + (H - m.t - m.b) * (1 - v / 100);
  const line = (key, pts = ser) => pts.filter(r => r[key] != null).map((r, i) => `${i ? "L" : "M"}${X(r.date).toFixed(1)},${Y(r[key]).toFixed(1)}`).join("");
  const step = arr => { let s = 0, d = `M${X(ser[0].date)},${Y(0)}`; arr.forEach(b => { d += `L${X(b.date)},${Y(s)}`; s += b.pct; d += `L${X(b.date)},${Y(s)}`; }); return d + `L${X(ser[ser.length - 1].date)},${Y(s)}`; };
  let g = "";
  for (let v = 0; v <= 100; v += 20) g += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#eef0f3"/><text x="${m.l - 6}" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="#8a96a3">${v}%</text>`;
  for (let d = new Date(t0.getFullYear(), t0.getMonth() + 1, 1); d <= t1; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
    const x = X(iso(d));
    g += `<line x1="${x}" x2="${x}" y1="${m.t}" y2="${H - m.b}" stroke="#f3f4f6"/>`;
    if (W > 600 || d.getMonth() % 2 === 0) g += `<text x="${x}" y="${H - 10}" font-size="10.5" text-anchor="middle" fill="#8a96a3">${d.toLocaleDateString("th-TH", { month: "short", year: "2-digit" })}</text>`;
  }
  const tx = X(dataDate());
  if (dataDate() >= ser[0].date && dataDate() <= ser[ser.length - 1].date)
    g += `<line x1="${tx}" x2="${tx}" y1="${m.t}" y2="${H - m.b}" stroke="var(--danger)" stroke-dasharray="4 3"/>`;
  if (withBill && sc.bill_plan.length) g += `<path d="${step(sc.bill_plan)}" fill="none" stroke="#8f6bc2" stroke-width="1.5" stroke-dasharray="2 2"/>`;
  if (withBill && sc.bill_actual.length) g += `<path d="${step(sc.bill_actual)}" fill="none" stroke="#1f9d55" stroke-width="2"/>`;
  g += `<path d="${line("baseline")}" fill="none" stroke="#7b8794" stroke-width="2" stroke-dasharray="6 4"/>`;
  g += `<path d="${line("forecast")}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="3 3"/>`;
  g += `<path d="${line("actual")}" fill="none" stroke="#e8590c" stroke-width="2.5"/>`;
  const lg = [[1, "#7b8794", sc.has_baseline ? "แผน (Baseline)" : "แผน (ยังไม่ล็อก Baseline)", "6 4"], [1, "#e8590c", "ผลงานจริง", ""], [1, "var(--accent)", "คาดการณ์จากความคืบหน้า", "3 3"],
    [withBill, "#8f6bc2", "แผนเบิกงวด", "2 2"], [withBill && sc.bill_actual.length, "#1f9d55", "เบิกจริง", ""]].filter(x => x[0]);
  const legend = `<div class="legend" style="margin-bottom:6px">${lg.map(x => `<span><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="${x[1]}" stroke-width="2.5" stroke-dasharray="${x[3]}"/></svg> ${x[2]}</span>`).join("")}</div>`;
  el.innerHTML = legend + `<svg class="chart" width="${W}" height="${H}" style="display:block">${g}<line id="hov" y1="${m.t}" y2="${H - m.b}" stroke="#52606d" stroke-width="1" style="display:none"/><rect x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}" fill="transparent" class="hit"/></svg>`;
  const svg = el.querySelector("svg.chart"), hov = svg.querySelector("#hov"), tip = $("#tip");
  svg.querySelector(".hit").onmousemove = e => {
    const r = svg.getBoundingClientRect(), x = e.clientX - r.left;
    let best = ser[0];
    ser.forEach(s => { if (Math.abs(X(s.date) - x) < Math.abs(X(best.date) - x)) best = s; });
    hov.setAttribute("x1", X(best.date)); hov.setAttribute("x2", X(best.date)); hov.style.display = "";
    const bill = sc.bill_plan.filter(b => b.date <= best.date).reduce((s, b) => s + b.pct, 0);
    tip.innerHTML = `<b>${fdl(best.date)}</b><br>แผน ${pc(best.baseline)}${best.actual != null ? "<br>ผลงานจริง " + pc(best.actual) : ""}${best.forecast != null ? "<br>คาดการณ์ " + pc(best.forecast) : ""}${withBill ? "<br>แผนเบิกสะสม " + pc(bill) : ""}`;
    tip.style.display = "block"; tip.style.left = e.pageX + 14 + "px"; tip.style.top = e.pageY - 10 + "px";
  };
  svg.querySelector(".hit").onmouseleave = () => { hov.style.display = "none"; tip.style.display = "none"; };
}

/* ───────────── milestones */
const MS_STAT = { paid: ["ok", "ได้รับเงินแล้ว"], approved: ["ok", "อนุมัติแล้ว"], submitted: ["warn", "ยื่นเบิกแล้ว"], ready: ["ok", "เงื่อนไขครบ · พร้อมเบิก"], planned: ["", "ยังไม่ครบ"] };
async function renderMilestones() {
  const seq = S.seq, ms = S.sched.milestones;
  const sm = await api("/api/billing_summary?date=" + dataDate());
  if (seq !== S.seq) return;
  const cv = S.state.meta.contract_value_ex_vat;
  const card = (k, v, s) => `<div class="card"><div class="k">${k}</div><div class="v" style="font-size:20px">${v}</div><div class="s">${s}</div></div>`;
  $("#msSummary").innerHTML = `<div class="cards">
    ${card("ยื่นเบิกแล้ว (ไม่รวม VAT)", money(sm.billed.amount), pc(100 * sm.billed.amount / cv) + " ของสัญญา")}
    ${card("ได้รับเงินแล้ว (สุทธิ)", money(sm.paid.net), "จาก " + ms.filter(m => m.status === "paid").length + " งวด")}
    ${card("ค้างรับ (ยื่น/อนุมัติแล้ว)", money(sm.outstanding.net), "สุทธิหลังหักประกันและ ณ ที่จ่าย")}
    ${card("พร้อมเบิกแต่ยังไม่ยื่น", money(sm.ready_not_billed.amount), ms.filter(m => m.status === "ready").length + " งวด")}
    ${card("เงินประกันผลงานถูกหักไว้", money(sm.billed.retention), "รอคืนหลังพ้นระยะประกัน")}
    ${card("ภาษีหัก ณ ที่จ่ายสะสม", money(sm.billed.wht), "ใช้เป็นเครดิตภาษี")}</div>`;
  $("#msList").innerHTML = ms.map(m => {
    const [cl, label] = MS_STAT[m.status];
    const dates = [m.submitted && "ยื่น " + fd(m.submitted), m.approved && "อนุมัติ " + fd(m.approved), m.paid && "รับเงิน " + fd(m.paid)].filter(Boolean).join(" · ");
    const late = m.baseline_forecast && m.forecast ? diffDays(day(m.baseline_forecast), day(m.forecast)) : 0;
    const q = m.money;
    const act = m.status === "paid" ? `<button data-a="reset">ยกเลิกสถานะ</button>`
      : m.status === "approved" ? `<button class="primary" data-a="pay">บันทึกได้รับเงิน</button><button data-a="reset">ยกเลิก</button>`
      : m.status === "submitted" ? `<button data-a="approve">บันทึกอนุมัติ</button><button class="primary" data-a="pay">บันทึกได้รับเงิน</button><button data-a="reset">ยกเลิก</button>`
      : `<button class="${m.ready ? "primary" : ""}" data-a="submit">บันทึกยื่นเบิก</button>`;
    return `<div class="ms" data-no="${esc(m.no)}"><div class="ms-h"><b>${m.kind === "vo" ? "" : "งวดที่ "}${esc(m.no)}</b>${m.kind === "vo" ? '<span class="pill warn">VO</span>' : ""}<span>${m.kind === "vo" ? "" : (m.pct * 100).toFixed(0) + "% · "}${money(q.amount, 2)} บาท</span><span class="pill ${cl}">${label}</span>
      ${m.invoice_no ? `<span class="small muted">เลขที่ ${esc(m.invoice_no)}</span>` : ""}<span class="small muted">${dates}</span>
      <span class="spacer"></span><span class="small muted">${m.ready ? "เงื่อนไขครบเมื่อ" : "คาดว่าเบิกได้"} ${fd(m.forecast)}${m.baseline_forecast ? ` · Baseline ${fd(m.baseline_forecast)}` : ""}${late > 0 ? ` <span style="color:var(--danger)">(ช้า ${late} วัน)</span>` : ""}</span></div>
      <div class="small" style="margin:6px 0 8px;color:var(--ink2)">${esc(m.description)}</div>
      ${m.checks.map(c => `<div class="chk"><span>${c.ok ? "✅" : "⬜"}</span><span>${esc(checkLabel(c))} ≥ ${c.need}%</span>
        <span class="pbar ${c.ok ? "ok" : ""}"><i style="width:${Math.min(100, c.pct)}%"></i><b style="left:${c.need}%"></b></span><span class="num">${c.pct.toFixed(1)}%</span></div>`).join("")}
      <div class="money"><span>(1) มูลค่างวด <b>${money(q.amount, 2)}</b></span><span>(2) VAT <b>${money(q.vat, 2)}</b></span><span>(4) ประกันผลงาน <b>−${money(q.retention, 2)}</b></span><span>(6) ณ ที่จ่าย <b>−${money(q.wht, 2)}</b></span><span>(7) สุทธิ <b>${money(q.net, 2)}</b></span></div>
      <div class="toolbar no-print" style="margin:10px 0 0">${act}<span class="spacer"></span><button data-a="doc">ใบขอเบิก</button><button data-a="xlsx">Excel</button></div></div>`;
  }).join("");
  $$("#msList .ms button[data-a]").forEach(b => b.onclick = () => msAction(b.closest(".ms").dataset.no, b.dataset.a));
}
function checkLabel(c) {
  const T = Object.fromEntries(S.state.tasks.map(t => [t.task_id, t.name]));
  return c.task === "ALL" ? "งานทั้งโครงการ" : (T[c.task] || c.task) + " · " + (/^[\d,-]+$/.test(c.floors) ? "ชั้น " + c.floors : floorLabel(c.floors));
}
function msAction(no, a) {
  const m = S.sched.milestones.find(x => x.no === no);
  const evq = m.evidence_date ? "" : "?date=" + dataDate();
  if (a === "doc") return window.open("/billing/" + encodeURIComponent(no) + evq, "_blank");
  if (a === "xlsx") return (location.href = "/api/export/billing/" + encodeURIComponent(no) + ".xlsx" + evq);
  const today = iso(new Date()), dd = dataDate() < today ? dataDate() : today;
  const title = { submit: "บันทึกยื่นเบิก", approve: "บันทึกผู้ว่าจ้างอนุมัติ", pay: "บันทึกได้รับเงิน", reset: "ยกเลิกสถานะการเบิก" }[a];
  const warn = a === "submit" && !m.ready ? `<p class="small" style="color:var(--danger)">เงื่อนไขงวดนี้ยังไม่ครบ ณ วันที่ข้อมูล — ยืนยันว่าจะบันทึกยื่นเบิก?</p>` : "";
  openPop(`<h4>${title} · งวดที่ ${esc(no)}</h4><div class="sub">สุทธิ ${money(m.money.net, 2)} บาท</div>${warn}
    ${a === "reset" ? `<p class="small">ล้างวันที่ยื่น/อนุมัติ/รับเงิน และเลขที่เอกสารของงวดนี้</p>` : `<div class="row"><label>วันที่</label><input type="date" id="baDate" value="${dd}" max="${today}"></div>`}
    ${a === "submit" ? `<div class="row"><label>เลขที่เอกสาร</label><input id="baInv" value="${esc(m.invoice_no || (S.state.meta.short || "").replace(/\W+/g, "").toUpperCase().slice(0, 4) + "-" + no)}"></div>
      <div class="row"><label>ผลงาน ณ</label><input type="date" id="baEv" value="${dataDate()}" max="${today}"></div>
      <div class="row"><label>หมายเหตุ</label><input id="baNote" placeholder="ไม่บังคับ"></div>` : ""}
    <div class="actions"><button onclick="closePop()">ยกเลิก</button><button class="primary" id="baOk">${a === "reset" ? "ล้างสถานะ" : "บันทึก"}</button></div>`);
  $("#baOk").onclick = async () => {
    const body = { action: a, date: a === "reset" ? today : $("#baDate").value };
    if (a === "submit") Object.assign(body, { invoice_no: $("#baInv").value.trim(), evidence_date: $("#baEv").value, note: $("#baNote").value });
    try { await api("/api/billing/" + encodeURIComponent(no), body); closePop(); toast(title + " · งวด " + no); await refresh(); }
    catch (e) { toast(e.message, true); }
  };
}

/* ───────────── VO / EOT / ค่าปรับ */
const VO_ST = { approved: ["ok", "อนุมัติ"], pending: ["warn", "รออนุมัติ"], rejected: ["no", "ไม่อนุมัติ"] };
const KIND_OPT = [["room", "ห้องพัก"], ["common,service,lift,stair,wc", "ส่วนกลาง"], ["room,common,service,wc,stair,lift,attic,parking", "ทุกพื้นที่ในอาคาร"],
  ["floor", "ทั้งชั้น (โครงสร้าง/ระบบ)"], ["facade", "ผนังภายนอก"], ["site", "ภายนอกอาคาร"], ["roof", "หลังคา"]];
async function renderChanges() {
  const seq = S.seq, c = await api("/api/changes?date=" + dataDate());
  if (seq !== S.seq) return;
  S.changes = c;
  const d = c.delay;
  const card = (k, v, s, col) => `<div class="card"><div class="k">${k}</div><div class="v" style="font-size:20px${col ? ";color:" + col : ""}">${v}</div><div class="s">${s}</div></div>`;
  $("#chgCards").innerHTML =
    card("มูลค่าสัญญาเดิม", money(c.contract_original), "ไม่รวม VAT") +
    card("VO อนุมัติแล้ว", (c.vo_approved >= 0 ? "+" : "") + money(c.vo_approved), c.vo.filter(v => v.status === "approved").length + " รายการ · รออนุมัติ " + c.vo.filter(v => v.status === "pending").length) +
    card("มูลค่าสัญญาปัจจุบัน", money(c.contract_value), "ไม่รวม VAT") +
    card("วันสิ้นสุดสัญญา", fd(d.contract_finish), d.eot_days ? `เดิม ${fd(d.contract_finish_original)} + EOT ${d.eot_days} วัน` : "ยังไม่มี EOT ที่อนุมัติ") +
    card("คาดว่าเสร็จ", fd(d.forecast_finish), d.late_days ? `ช้ากว่าสัญญา ${d.late_days} วัน` : "ทันสัญญา", d.late_days ? "var(--danger)" : "") +
    card("ค่าปรับประมาณการ", money(d.ld_forecast), `${money(d.ld_per_day)}/วัน · เพดาน ${money(d.ld_cap)} (${d.cap_days} วัน)${d.ld_now ? " · ถึงวันนี้ " + money(d.ld_now) : ""}`, d.ld_forecast ? "var(--danger)" : "");
  const T = Object.fromEntries(S.state.tasks.map(t => [t.task_id, t.name]));
  $("#voList").innerHTML = c.vo.length ? `<table class="t"><thead><tr><th>เลขที่</th><th>รายการ</th><th class="num">จำนวนเงิน</th><th>สถานะ</th><th></th></tr></thead><tbody>${c.vo.slice().sort((a, b) => String(a.no).localeCompare(String(b.no), "th", { numeric: true })).map(v => `<tr class="${v.status === "approved" ? "" : "inactive"}">
    <td>VO-${esc(v.no)}</td><td>${esc(v.title)}<div class="small muted">${v.kind === "adjust" ? "ปรับ " + esc(T[v.task_id] || v.task_id) : "งานใหม่"} · ${v.floors ? "ชั้น " + esc(v.floors) : "ทุกชั้น"}${v.date ? " · " + fd(v.date) : ""}</div></td>
    <td class="num" style="color:${+v.amount < 0 ? "var(--danger)" : ""}">${money(v.amount, 2)}</td><td><span class="pill ${VO_ST[v.status]?.[0] || ""}">${VO_ST[v.status]?.[1] || esc(v.status)}</span></td>
    <td><button class="ghost" data-vo="${esc(v.no)}">แก้</button></td></tr>`).join("")}</tbody></table>` : `<p class="muted">ยังไม่มี VO</p>`;
  $("#eotList").innerHTML = c.eot.length ? `<table class="t"><thead><tr><th>เลขที่</th><th>เหตุผล</th><th class="num">ขอ</th><th class="num">อนุมัติ</th><th>สถานะ</th><th></th></tr></thead><tbody>${c.eot.map(e => `<tr class="${e.status === "approved" ? "" : "inactive"}">
    <td>EOT-${esc(e.no)}</td><td>${esc(e.title)}<div class="small muted">${esc(e.reason || "")}${e.date ? " · " + fd(e.date) : ""}</div></td><td class="num">${esc(e.requested_days)}</td><td class="num">${esc(e.approved_days || "–")}</td>
    <td><span class="pill ${VO_ST[e.status]?.[0] || ""}">${VO_ST[e.status]?.[1] || esc(e.status)}</span></td><td><button class="ghost" data-eot="${esc(e.no)}">แก้</button></td></tr>`).join("")}</tbody></table>` : `<p class="muted">ยังไม่มี EOT</p>`;
  $("#ldDay").value = c.ld_per_day ?? ""; $("#ldDay").placeholder = money(d.ld_per_day);
  $("#ldCap").value = Math.round((c.ld_cap_pct ?? 0.1) * 1000) / 10;
  $$("#voList [data-vo]").forEach(b => b.onclick = () => voDialog(c.vo.find(v => String(v.no) === b.dataset.vo)));
  $$("#eotList [data-eot]").forEach(b => b.onclick = () => eotDialog(c.eot.find(v => String(v.no) === b.dataset.eot)));
}
$("#btnVoAdd").onclick = () => voDialog(null);
$("#btnEotAdd").onclick = () => eotDialog(null);
$("#ldSave").onclick = async () => {
  try { await api("/api/settings", { ld_per_day: $("#ldDay").value, ld_cap_pct: $("#ldCap").value === "" ? "" : +$("#ldCap").value / 100 }); toast("บันทึกค่าปรับแล้ว"); await refresh(); }
  catch (e) { toast(e.message, true); }
};
function nextNo(list) { return String(list.reduce((m, x) => Math.max(m, parseInt(x.no) || 0), 0) + 1); }
function voDialog(v) {
  const isNew = !v; v = v || { no: nextNo(S.changes.vo), status: "pending", kind: "new", trade: "ARCH", kinds: "room", duration: 5, date: iso(new Date()) };
  const tasks = S.state.tasks.filter(t => t.value > 0 && !t.auto_time && !t.task_id.startsWith("VO"));
  openPop(`<h4>${isNew ? "เพิ่ม" : "แก้"} VO</h4><div class="sub">จำนวนเงินไม่รวม VAT · ติดลบ = งานลด</div>
    <div class="row"><label>เลขที่</label><input id="voNo" value="${esc(v.no)}" ${isNew ? "" : "disabled"} style="max-width:90px"><label style="min-width:auto">วันที่</label><input type="date" id="voDate" value="${esc(v.date || "")}"></div>
    <div class="row"><label>รายการ</label><input id="voTitle" value="${esc(v.title || "")}"></div>
    <div class="row"><label>จำนวนเงิน</label><input id="voAmt" type="number" step="0.01" value="${esc(v.amount ?? "")}"></div>
    <div class="row"><label>สถานะ</label><select id="voSt">${Object.entries(VO_ST).map(([k, [, t]]) => `<option value="${k}" ${v.status === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="row"><label>ประเภท</label><select id="voKind"><option value="new" ${v.kind !== "adjust" ? "selected" : ""}>งานใหม่ (หมวดงานใหม่ + แท่ง Gantt)</option><option value="adjust" ${v.kind === "adjust" ? "selected" : ""}>ปรับมูลค่างานเดิม</option></select></div>
    <div id="voNew">
      <div class="row"><label>หมวด</label><select id="voTrade">${["ARCH", "STR", "EE", "SN", "PRELIM"].map(t => `<option value="${t}" ${v.trade === t ? "selected" : ""}>${TRADE_NAME[t]}</option>`).join("")}</select></div>
      <div class="row"><label>พื้นที่</label><select id="voKinds">${KIND_OPT.map(([k, t]) => `<option value="${k}" ${v.kinds === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="row"><label>ระยะเวลา</label><input id="voDur" type="number" min="1" value="${esc(v.duration || 5)}" style="max-width:80px"><span class="small muted">วันทำงาน</span></div>
      <div class="row"><label>เริ่มหลัง</label><input id="voPred" value="${esc(v.preds || "")}" placeholder="เช่น FIXE6FS (ว่าง = เริ่มวันที่ VO)"></div>
    </div>
    <div id="voAdj"><div class="row"><label>หมวดงานเดิม</label><select id="voTask">${tasks.map(t => `<option value="${t.task_id}" ${v.task_id === t.task_id ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select></div></div>
    <div class="row"><label>ชั้น</label><input id="voFl" value="${esc(v.floors || "")}" placeholder="เช่น 2-6 หรือ 1,7 (ว่าง = ทุกชั้น)"></div>
    <div class="row"><label>หมายเหตุ</label><input id="voNote" value="${esc(v.note || "")}"></div>
    <div class="actions">${isNew ? "" : '<button id="voDel" style="color:var(--danger);margin-right:auto">ลบ</button>'}<button onclick="closePop()">ยกเลิก</button><button class="primary" id="voOk">บันทึก</button></div>`);
  const sync = () => { const adj = $("#voKind").value === "adjust"; $("#voNew").style.display = adj ? "none" : ""; $("#voAdj").style.display = adj ? "" : "none"; };
  $("#voKind").onchange = sync; sync();
  $("#voOk").onclick = async () => {
    const body = { no: $("#voNo").value.trim(), date: $("#voDate").value, title: $("#voTitle").value.trim(), amount: $("#voAmt").value, status: $("#voSt").value,
      kind: $("#voKind").value, trade: $("#voTrade").value, kinds: $("#voKinds").value, duration: $("#voDur").value, preds: $("#voPred").value.trim(),
      task_id: $("#voTask").value, floors: $("#voFl").value.trim(), note: $("#voNote").value };
    if (!body.title || body.amount === "") return toast("ใส่รายการและจำนวนเงิน", true);
    try { const r = await api("/api/vo", body); closePop(); toast(r.warnings.length ? r.warnings[0] : "บันทึก VO-" + body.no, r.warnings.length > 0); S.boq = null; await refresh(); }
    catch (e) { toast(e.message, true); }
  };
  if ($("#voDel")) $("#voDel").onclick = async () => { await api("/api/vo", { no: v.no, delete: true }); closePop(); toast("ลบ VO-" + v.no); await refresh(); };
}
function eotDialog(e) {
  const isNew = !e; e = e || { no: nextNo(S.changes.eot), status: "pending", date: iso(new Date()) };
  openPop(`<h4>${isNew ? "เพิ่ม" : "แก้"} EOT</h4><div class="sub">จำนวนวันเป็นวันปฏิทิน · เฉพาะที่อนุมัติจึงเลื่อนวันสิ้นสุดสัญญา</div>
    <div class="row"><label>เลขที่</label><input id="eoNo" value="${esc(e.no)}" ${isNew ? "" : "disabled"} style="max-width:90px"><label style="min-width:auto">วันที่</label><input type="date" id="eoDate" value="${esc(e.date || "")}"></div>
    <div class="row"><label>เรื่อง</label><input id="eoTitle" value="${esc(e.title || "")}"></div>
    <div class="row"><label>เหตุผล</label><input id="eoReason" value="${esc(e.reason || "")}" placeholder="เช่น ฝนตก, ผู้ว่าจ้างเปลี่ยนแบบ, รอวัสดุผู้ว่าจ้าง"></div>
    <div class="row"><label>ขอ (วัน)</label><input id="eoReq" type="number" min="0" value="${esc(e.requested_days ?? "")}" style="max-width:90px"><label style="min-width:auto">อนุมัติ (วัน)</label><input id="eoApp" type="number" min="0" value="${esc(e.approved_days ?? "")}" style="max-width:90px"></div>
    <div class="row"><label>สถานะ</label><select id="eoSt">${Object.entries(VO_ST).map(([k, [, t]]) => `<option value="${k}" ${e.status === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="actions">${isNew ? "" : '<button id="eoDel" style="color:var(--danger);margin-right:auto">ลบ</button>'}<button onclick="closePop()">ยกเลิก</button><button class="primary" id="eoOk">บันทึก</button></div>`);
  $("#eoOk").onclick = async () => {
    const body = { no: $("#eoNo").value.trim(), date: $("#eoDate").value, title: $("#eoTitle").value.trim(), reason: $("#eoReason").value.trim(),
      requested_days: $("#eoReq").value, approved_days: $("#eoApp").value, status: $("#eoSt").value };
    if (body.status === "approved" && !(+body.approved_days > 0)) return toast("ใส่จำนวนวันที่อนุมัติ", true);
    try { await api("/api/eot", body); closePop(); toast("บันทึก EOT-" + body.no); await refresh(); } catch (er) { toast(er.message, true); }
  };
  if ($("#eoDel")) $("#eoDel").onclick = async () => { await api("/api/eot", { no: e.no, delete: true }); closePop(); toast("ลบ EOT-" + e.no); await refresh(); };
}

/* ───────────── รูปถ่าย */
function photoGrid(list) {
  return list.length ? `<div class="photos">${list.map(p => `<a href="#" data-ph="${p.id}" title="${esc(p.note || p.name || "")}"><img loading="lazy" src="/photos/thumbs/${p.file}"><span>${fd(p.date)}</span></a>`).join("")}</div>` : `<p class="small muted">ยังไม่มีรูป</p>`;
}
function bindPhotos(root, list, after) {
  $$("[data-ph]", root).forEach(a => a.onclick = ev => {
    ev.preventDefault();
    const p = list.find(x => x.id === a.dataset.ph), T = Object.fromEntries(S.state.tasks.map(t => [t.task_id, t.name]));
    const lb = document.createElement("div"); lb.className = "lightbox";
    lb.innerHTML = `<img src="/photos/${p.file}"><div class="cap">${fdl(p.date)}${p.task_id ? " · " + esc(T[p.task_id] || p.task_id) : ""}${p.note ? " · " + esc(p.note) : ""}<button>ลบรูป</button></div>`;
    lb.onclick = e => { if (e.target === lb || e.target.tagName === "IMG") lb.remove(); };
    lb.querySelector("button").onclick = async () => {
      if (!confirm("ลบรูปนี้?")) return;
      await fetch("/api/photos/" + p.id, { method: "DELETE" }); lb.remove(); toast("ลบรูปแล้ว"); after && after();
    };
    document.body.appendChild(lb);
  });
}
function uploadInput(id, label = "📷 แนบรูป") { return `<label class="upl">${label}<input type="file" id="${id}" accept="image/*" multiple></label>`; }
async function uploadPhotos(files, loc, task, note) {
  const fd_ = new FormData();
  [...files].forEach(f => fd_.append("files", f));
  fd_.append("loc_id", loc); fd_.append("task_id", task || ""); fd_.append("date", dataDate() <= iso(new Date()) ? dataDate() : iso(new Date())); fd_.append("note", note || "");
  const r = await fetch("/api/photos", { method: "POST", body: fd_ });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error);
  return j.photos;
}

/* ───────────── BOQ */
["#boqQ", "#boqTrade", "#boqIn"].forEach(s => $(s).addEventListener("input", () => renderBoq()));
async function renderBoq() {
  if (!S.boq) S.boq = await api("/api/boq");
  const q = $("#boqQ").value.trim().toLowerCase(), tr = $("#boqTrade").value, only = $("#boqIn").checked;
  const T = Object.fromEntries(S.state.tasks.map(t => [t.task_id, t.name]));
  const rows = S.boq.filter(r => (!tr || r.trade === tr) && (!only || r.scope === "in") &&
    (!q || (r.code + " " + r.description + " " + r.task_id + " " + (T[r.task_id] || "") + " " + r.section_name).toLowerCase().includes(q)));
  const sum = rows.reduce((s, r) => s + (r.scope === "in" ? +r.amount * (+r.share || 1) : 0), 0);
  $("#boqInfo").textContent = `${rows.length} แถว · ${money(sum, 2)} บาท`;
  const scope = { in: "", excluded: '<span class="pill no">ไม่รวม</span>', owner: '<span class="pill warn">ผู้ว่าจ้าง</span>', zero: '<span class="pill">0 บาท</span>' };
  $("#boqTable").innerHTML = `<thead><tr><th>รหัส</th><th>รายการ</th><th class="num">ปริมาณ</th><th>หน่วย</th><th class="num">จำนวนเงิน</th><th>หมวดงาน</th><th class="num">สัดส่วน</th><th>กระจายลงพื้นที่</th><th>ที่มา</th></tr></thead><tbody>${rows.slice(0, 800).map(r => `<tr>
    <td>${esc(r.code)}</td><td>${esc(r.description)}${r.note ? `<div class="small muted">${esc(r.note)}</div>` : ""}<div class="small muted">${esc(r.section_name)}${r.group ? " · " + esc(r.group) : ""}</div></td>
    <td class="num">${r.qty ? money(+r.qty, 2) : ""}</td><td>${esc(r.unit)}</td><td class="num">${money(+r.amount, 2)} ${scope[r.scope] || ""}</td>
    <td>${r.task_id ? esc(T[r.task_id] || r.task_id) : ""}</td><td class="num">${r.share && +r.share !== 1 ? (+r.share * 100).toFixed(0) + "%" : ""}</td>
    <td class="small">${esc(r.alloc)}</td><td class="small muted">${esc(r.src)}</td></tr>`).join("")}</tbody>`;
}

window.addEventListener("resize", () => { if (S.view === "scurve" || S.view === "overview") render(); });
boot().catch(e => toast(e.message, true));
