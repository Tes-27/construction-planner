"""แกนคำนวณของ Construction Planner — อ่านเฉพาะไฟล์รูปแบบกลางในโฟลเดอร์โครงการ

project.json · locations.csv · tasks.csv · boq.csv · activities.csv · milestones.csv · progress.csv · baselines/*.json
ไม่มีโค้ดเฉพาะโครงการในไฟล์นี้
"""
import csv, datetime as dt, json, os, re, sys
from collections import defaultdict

for _s in (sys.stdout, sys.stderr):  # Windows: คอนโซลอาจเป็น cp874 → พิมพ์ภาษาไทย/สัญลักษณ์ไม่พัง
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

D = dt.date


def _csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def parse_date(s):
    return dt.date.fromisoformat(s) if isinstance(s, str) else s


def floor_set(spec):
    """'1-3' → {'1','2','3'} · 'SITE' → {'SITE'} · '1,2,RF' → {...}"""
    out = set()
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            out |= {str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)}
        else:
            out.add(part)
    return out


class Calendar:
    def __init__(self, start, workdays, holidays, horizon_days=1500):
        self.start = start
        hol = {parse_date(h) for h in holidays}
        self.days = []  # รายการวันทำงาน (index → date)
        d = start
        while len(self.days) < horizon_days:
            if d.weekday() in workdays and d not in hol:
                self.days.append(d)
            d += dt.timedelta(days=1)
        self.index = {d: i for i, d in enumerate(self.days)}

    def date(self, i):
        return self.days[max(0, min(i, len(self.days) - 1))]

    def idx_on_or_before(self, d):
        """จำนวนวันทำงานที่ผ่านไปจนถึงสิ้นวัน d (เป็นจำนวนนับ ไม่ใช่ index)"""
        lo, hi = 0, len(self.days)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.days[mid] <= d:
                lo = mid + 1
            else:
                hi = mid
        return lo


PRED_RE = re.compile(r"^([A-Za-z0-9_\-]+?)(FS|SS|FF)([+-]\d+)?$")


class Project:
    def __init__(self, folder):
        self.folder = folder
        self.reload()

    # ─────────────────────────── load
    def reload(self):
        p = self.folder
        with open(os.path.join(p, "project.json"), encoding="utf-8") as fh:
            self.meta = json.load(fh)
        self.locations = _csv(os.path.join(p, "locations.csv"))
        self.loc = {l["loc_id"]: l for l in self.locations}
        self.tasks = _csv(os.path.join(p, "tasks.csv"))
        self.task = {t["task_id"]: t for t in self.tasks}
        for t in self.tasks:
            t["auto_time"] = t["steps"].strip() == "auto-time"
            t["step_list"] = [] if t["auto_time"] else [
                {"name": s.split(":")[0], "w": _f(s.split(":")[1])} for s in t["steps"].split("|") if ":" in s]
        self.boq = _csv(os.path.join(p, "boq.csv"))
        self.activities = _csv(os.path.join(p, "activities.csv"))
        self.milestones = _csv(os.path.join(p, "milestones.csv"))
        bpath = os.path.join(p, "billing.json")  # สถานะการเบิก — โปรแกรมเป็นเจ้าของ ไฟล์นำเข้าไม่แตะ
        self.billing = {}
        if os.path.exists(bpath):
            with open(bpath, encoding="utf-8") as fh:
                self.billing = json.load(fh)
        self.plans = {"sheets": {}, "floor_sheet": {}}
        if os.path.exists(os.path.join(p, "plans.json")):
            with open(os.path.join(p, "plans.json"), encoding="utf-8") as fh:
                self.plans = json.load(fh)
        self.zones = {}
        if os.path.exists(os.path.join(p, "zones.json")):
            with open(os.path.join(p, "zones.json"), encoding="utf-8") as fh:
                self.zones = json.load(fh)
        self.vo = self._json("vo.json", [])          # งานเพิ่ม-ลด
        self.eot = self._json("eot.json", [])        # ขอขยายเวลา
        self.photos = self._json("photos.json", [])  # รูปถ่ายประกอบ
        self.cal = Calendar(parse_date(self.meta["start_date"]), self.meta["calendar"]["workdays"],
                            self.meta["calendar"]["holidays"])
        self.issues = []
        self._allocate()
        self._apply_vo()
        self._map_activities()
        self.load_progress()

    def _json(self, name, default):
        path = os.path.join(self.folder, name)
        if not os.path.exists(path):
            return default
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _save_json(self, name, data):
        with open(os.path.join(self.folder, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)

    def load_progress(self):
        rows = _csv(os.path.join(self.folder, "progress.csv"))
        hist = defaultdict(list)
        for i, r in enumerate(rows):
            hist[(r["task_id"], r["loc_id"])].append((r["date"], i, _f(r["pct"]), r.get("steps", ""), r.get("note", "")))
        for k in hist:
            hist[k].sort()
        self.progress_hist = hist
        self.progress_rows = rows
        self._auto_cache = {}

    # ─────────────────────────── allocation: BOQ → cells (task × location)
    def select_locs(self, alloc):
        spec = {}
        for part in alloc.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                spec[k.strip()] = v.strip()
        if "locs" in spec:
            ids = [x.strip() for x in spec["locs"].split(",") if x.strip()]
            missing = [x for x in ids if x not in self.loc]
            if missing:
                self.issues.append(("error", f"alloc อ้างพื้นที่ที่ไม่มี: {', '.join(missing)}"))
            locs = [self.loc[x] for x in ids if x in self.loc]
        else:
            locs = list(self.locations)
            if "kinds" in spec:
                kinds = set(spec["kinds"].split(","))
                locs = [l for l in locs if l["kind"] in kinds]
            else:
                locs = [l for l in locs if l["kind"] != "floor"]
            if "floors" in spec:
                fs = floor_set(spec["floors"])
                locs = [l for l in locs if l["floor"] in fs]
            if "rtype" in spec:
                locs = [l for l in locs if l["rtype"] == spec["rtype"]]
        by = spec.get("by", "area")
        w = [(_f(l["area"], 1.0) if by == "area" else 1.0) for l in locs]
        s = sum(w)
        return [(l["loc_id"], wi / s) for l, wi in zip(locs, w)] if s > 0 else []

    def _allocate(self):
        cells = defaultdict(float)
        in_scope = 0.0
        for r in self.boq:
            if r["scope"] != "in":
                continue
            amt = _f(r["amount"]) * _f(r["share"], 1.0)
            in_scope += amt
            if not r["task_id"]:
                self.issues.append(("error", f"BOQ {r['code']} ยังไม่ผูกหมวดงาน ({_f(r['amount']):,.0f} บาท)"))
                continue
            if r["task_id"] not in self.task:
                self.issues.append(("error", f"BOQ {r['code']} อ้างหมวดงาน {r['task_id']} ที่ไม่มี"))
                continue
            sel = self.select_locs(r["alloc"])
            if not sel:
                self.issues.append(("error", f"BOQ {r['code']} alloc '{r['alloc']}' ไม่ตรงกับพื้นที่ใดเลย"))
                continue
            for loc_id, w in sel:
                cells[(r["task_id"], loc_id)] += amt * w
        self.cells = dict(cells)
        self.total_value = sum(self.cells.values())
        self.in_scope = in_scope
        boq_total = _f(self.meta.get("boq_total"))
        if boq_total and abs(in_scope - boq_total) > 1:
            self.issues.append(("error", f"ผลรวม BOQ ในขอบเขต {in_scope:,.2f} ≠ ยอด BOQ {boq_total:,.2f}"))
        # ตัวคูณจากยอด BOQ → มูลค่าสัญญา (ค่าดำเนินการ+กำไร, ส่วนลด)
        self.k_contract = _f(self.meta["contract_value_ex_vat"]) / self.total_value if self.total_value else 1.0
        self.loc_value = defaultdict(float)
        self.task_value = defaultdict(float)
        for (t, l), v in self.cells.items():
            self.loc_value[l] += v
            self.task_value[t] += v

    # ─────────────────────────── VO (งานเพิ่ม-ลด) — ใช้เฉพาะที่อนุมัติแล้ว
    @staticmethod
    def vo_task_id(v):
        return "VO" + re.sub(r"[^A-Za-z0-9]", "", str(v["no"]))

    def _apply_vo(self):
        self.contract_original = _f(self.meta["contract_value_ex_vat"])
        self.vo_approved = 0.0
        for v in self.vo:
            if v.get("status") != "approved":
                continue
            amt = _f(v.get("amount"))
            boq_amt = amt / self.k_contract  # มูลค่าในหน่วย BOQ (ก่อนค่าดำเนินการ/ส่วนลด)
            spec = ";".join(x for x in (f"kinds={v['kinds']}" if v.get("kinds") else "",
                                         f"floors={v['floors']}" if v.get("floors") else "") if x)
            label = f"VO-{v['no']}"
            if v.get("kind") == "adjust":
                t = v.get("task_id")
                fl = floor_set(v["floors"]) if v.get("floors") else None
                sel = {c: val for c, val in self.cells.items()
                       if c[0] == t and (fl is None or self.loc[c[1]]["floor"] in fl)}
                tot = sum(sel.values())
                if not tot:
                    self.issues.append(("error", f"{label}: ไม่มีงาน {t} ในพื้นที่ที่เลือก"))
                    continue
                if boq_amt < -tot:
                    self.issues.append(("warn", f"{label}: ลดมากกว่ามูลค่างานเดิม — ตัดเหลือ 0"))
                for c, val in sel.items():
                    self.cells[c] = max(0.0, val + boq_amt * val / tot)
            else:
                tid = self.vo_task_id(v)
                steps = v.get("steps") or "ดำเนินการ:100"
                t = {"task_id": tid, "name": f"{label} {v.get('title', '')}".strip(), "trade": v.get("trade") or "ARCH",
                     "steps": steps, "auto_time": False, "vo": v["no"],
                     "step_list": [{"name": x.split(":")[0], "w": _f(x.split(":")[1])} for x in steps.split("|") if ":" in x]}
                self.tasks.append(t)
                self.task[tid] = t
                sel = self.select_locs(spec or "kinds=site")
                if not sel:
                    self.issues.append(("error", f"{label}: เลือกพื้นที่ไม่ได้ ({spec})"))
                    continue
                for loc_id, w in sel:
                    self.cells[(tid, loc_id)] = self.cells.get((tid, loc_id), 0.0) + boq_amt * w
                floors = sorted({self.loc[l]["floor"] for l, _ in sel})
                self.activities.append({"act_id": tid, "task_id": tid, "floors": ",".join(floors),
                                        "duration": str(int(_f(v.get("duration"), 5)) or 5),
                                        "preds": v.get("preds", ""), "name": t["name"],
                                        "start_on": "" if v.get("preds") else (v.get("date") or ""), "vo": v["no"]})
            self.vo_approved += amt
            # รายการเบิกของ VO: งานเพิ่ม = เบิกเมื่อเสร็จ 100% · งานลด = หักได้ทันที
            if v.get("kind") == "adjust":
                cond = "" if amt < 0 else f"{v['task_id']} @ {v.get('floors') or ','.join(sorted({self.loc[c[1]]['floor'] for c in self.cells if c[0] == v['task_id']}))} >= 100"
            else:
                cond = f"{self.vo_task_id(v)} @ {','.join(sorted({self.loc[c[1]]['floor'] for c in self.cells if c[0] == self.vo_task_id(v)}))} >= 100"
            self.milestones.append({"no": label, "pct": str(amt / self.contract_original), "amount": str(amt),
                                    "description": f"{'งานเพิ่ม' if amt >= 0 else 'งานลด'}: {v.get('title', '')}",
                                    "conditions": cond, "version": "VO", "kind": "vo"})
        self.contract_value = self.contract_original + self.vo_approved
        self.total_value = sum(self.cells.values())
        self.loc_value = defaultdict(float)
        self.task_value = defaultdict(float)
        for (t, l), v in self.cells.items():
            self.loc_value[l] += v
            self.task_value[t] += v

    def save_vo(self, v):
        v = {k: v.get(k, "") for k in ("no", "title", "date", "status", "kind", "amount", "trade", "task_id",
                                       "floors", "kinds", "duration", "preds", "steps", "reason", "note")}
        if not str(v["no"]).strip():
            raise ValueError("ต้องมีเลขที่ VO")
        if v["kind"] == "adjust" and v["task_id"] not in self.task:
            raise ValueError("เลือกหมวดงานที่จะปรับ")
        v["amount"] = _f(v["amount"])
        self.vo = [x for x in self.vo if str(x["no"]) != str(v["no"])] + [v]
        self._save_json("vo.json", self.vo)

    def delete_vo(self, no):
        self.vo = [x for x in self.vo if str(x["no"]) != str(no)]
        self._save_json("vo.json", self.vo)

    # ─────────────────────────── EOT + ค่าปรับ
    def contract_finish(self):
        base = parse_date(self.meta["finish_date"])
        days = sum(int(_f(e.get("approved_days"))) for e in self.eot if e.get("status") == "approved")
        return base + dt.timedelta(days=days), days

    def save_eot(self, e):
        e = {k: e.get(k, "") for k in ("no", "title", "reason", "date", "requested_days", "approved_days", "status", "note")}
        if not str(e["no"]).strip():
            raise ValueError("ต้องมีเลขที่ EOT")
        self.eot = [x for x in self.eot if str(x["no"]) != str(e["no"])] + [e]
        self._save_json("eot.json", self.eot)

    def delete_eot(self, no):
        self.eot = [x for x in self.eot if str(x["no"]) != str(no)]
        self._save_json("eot.json", self.eot)

    def delay(self, date):
        """สถานะความล่าช้า ณ วันข้อมูล: วันสิ้นสุดสัญญา (รวม EOT) เทียบวันคาดว่าเสร็จ → ค่าปรับประมาณการ"""
        sched, end = self.schedule(status=date)
        forecast = self.cal.date(end)
        fin, eot_days = self.contract_finish()
        vat = _f(self.meta.get("vat_rate", 0.07))
        incl = self.contract_value * (1 + vat)
        ld_day = _f(self.meta.get("ld_per_day")) or 0.001 * incl
        cap = _f(self.meta.get("ld_cap_pct"), 0.10) * incl
        late = max(0, (forecast - fin).days)
        late_now = max(0, (date - fin).days) if self.earned(date) < self.total_value - 1e-6 else 0
        return {"contract_finish_original": self.meta["finish_date"], "eot_days": eot_days,
                "contract_finish": fin.isoformat(), "forecast_finish": forecast.isoformat(), "late_days": late,
                "late_days_now": late_now, "ld_per_day": ld_day, "ld_forecast": min(late * ld_day, cap),
                "ld_now": min(late_now * ld_day, cap), "ld_cap": cap, "cap_days": int(cap / ld_day) if ld_day else 0,
                "ld_default": not _f(self.meta.get("ld_per_day"))}

    # ─────────────────────────── รูปถ่าย
    def add_photo(self, rec):
        self.photos.append(rec)
        self._save_json("photos.json", self.photos)

    def delete_photo(self, pid):
        keep = [x for x in self.photos if x["id"] != pid]
        gone = [x for x in self.photos if x["id"] == pid]
        self._save_json("photos.json", keep)
        self.photos = keep
        return gone[0] if gone else None

    def photos_for(self, loc=None, task=None, floors=None, start=None, end=None):
        out = []
        for ph in self.photos:
            if loc and ph["loc_id"] != loc:
                continue
            if task and ph.get("task_id") and ph["task_id"] != task:
                continue
            if floors is not None and self.loc.get(ph["loc_id"], {}).get("floor") not in floors:
                continue
            if start and ph["date"] <= start:
                continue
            if end and ph["date"] > end:
                continue
            out.append(ph)
        return sorted(out, key=lambda x: (x["date"], x.get("uploaded_at", "")), reverse=True)

    def _map_activities(self):
        self.act = {}
        covered = defaultdict(list)
        for a in self.activities:
            a["floor_set"] = floor_set(a["floors"])
            a["cells"] = [(t, l) for (t, l) in self.cells if t == a["task_id"] and self.loc[l]["floor"] in a["floor_set"]]
            a["value"] = sum(self.cells[c] for c in a["cells"])
            for c in a["cells"]:
                covered[c].append(a["act_id"])
            if a["act_id"] in self.act:
                self.issues.append(("error", f"รหัสกิจกรรมซ้ำ {a['act_id']}"))
            self.act[a["act_id"]] = a
            if a["task_id"] not in self.task:
                self.issues.append(("error", f"กิจกรรม {a['act_id']} อ้างหมวดงาน {a['task_id']} ที่ไม่มี"))
        miss = defaultdict(float)
        for c, v in self.cells.items():
            if not covered.get(c):
                miss[c[0]] += v
            elif len(covered[c]) > 1:
                self.issues.append(("warn", f"{c[0]} @ {c[1]} อยู่ในหลายกิจกรรม: {', '.join(covered[c])}"))
        for t, v in miss.items():
            self.issues.append(("error", f"หมวด {t} มีมูลค่า {v:,.0f} บาทที่ไม่มีแท่ง Gantt รองรับ"))

    # ─────────────────────────── schedule (CPM บนวันทำงาน)
    def act_progress(self, a, date):
        """% ของกิจกรรม (ถ่วงมูลค่า) + วันแรกที่เริ่มมีผลงาน + วันที่ครบ 100% (ถ้าครบ)"""
        v = a["value"]
        if not v:
            return 0.0, None, None
        ds = date.isoformat()
        tot, first, done = 0.0, None, None
        all_done = True
        for c in a["cells"]:
            h = self.progress_hist.get(c) or []
            pct, f100 = 0.0, None
            for r in h:
                if r[0] > ds:
                    break
                pct = r[2]
                if r[2] > 0 and (first is None or r[0] < first):
                    first = r[0]
                if r[2] >= 100 and f100 is None:
                    f100 = r[0]
                if r[2] < 100:
                    f100 = None
            tot += self.cells[c] * pct / 100.0
            if pct < 100:
                all_done = False
            elif f100 and (done is None or f100 > done):
                done = f100
        pct = 100.0 * tot / v
        return pct, first, (done if all_done else None)

    def schedule(self, acts=None, status=None):
        """CPM บนวันทำงาน · status = วันที่ข้อมูล → งานที่ยังไม่เริ่มจะเริ่มได้หลังวันนั้น
        งานที่เริ่มแล้วคิดเฉพาะเนื้องานที่เหลือ งานที่เสร็จแล้วใช้วันจริง"""
        acts = acts or self.activities
        by_id = {a["act_id"]: a for a in acts}
        iss = self.sched_issues = []
        preds = {}
        for a in acts:
            lst = []
            for p in [x.strip() for x in str(a.get("preds", "")).split(";") if x.strip()]:
                m = PRED_RE.match(p)
                if not m or m.group(1) not in by_id:
                    iss.append(("error", f"กิจกรรม {a['act_id']}: predecessor '{p}' อ่านไม่ได้หรือไม่มีอยู่"))
                    continue
                lst.append((m.group(1), m.group(2), int(m.group(3) or 0)))
            preds[a["act_id"]] = lst
        # topological order
        order, state = [], {}

        def visit(n, stack=()):
            if state.get(n) == 2:
                return
            if state.get(n) == 1:
                iss.append(("error", f"ลำดับงานวนกลับ: {' → '.join(stack + (n,))}"))
                return
            state[n] = 1
            for p, _, _ in preds[n]:
                visit(p, stack + (n,))
            state[n] = 2
            order.append(n)

        for a in acts:
            visit(a["act_id"])
        es, ef, dur = {}, {}, {}
        auto = [a["act_id"] for a in acts if self.task.get(a["task_id"], {}).get("auto_time")]
        st_idx = self.cal.idx_on_or_before(status) - 1 if status else None
        state_of = {}
        for n in order:
            a = by_id[n]
            d = max(0, int(_f(a["duration"])))
            dur[n] = d
            if status and n not in auto and "cells" in a:
                pct, first, done = self.act_progress(a, status)
                if pct >= 100 - 1e-9 and first:
                    es[n] = self.cal.idx_on_or_before(parse_date(first)) - 1
                    ef[n] = max(es[n], self.cal.idx_on_or_before(parse_date(done or status.isoformat())) - 1)
                    dur[n], state_of[n] = ef[n] - es[n] + 1, "done"
                    continue
                if pct > 0 and first:
                    es[n] = self.cal.idx_on_or_before(parse_date(first)) - 1
                    remain = max(1, int(-(-d * (100 - pct) // 100)))
                    ef[n] = max(st_idx, es[n]) + remain
                    dur[n], state_of[n] = ef[n] - es[n] + 1, "active"
                    continue
            s = 0 if st_idx is None else st_idx  # งานที่ยังไม่เริ่ม เริ่มได้ตั้งแต่วันที่ข้อมูล
            for p, typ, lag in preds[n]:
                if p not in ef:  # ลำดับงานวนกลับ (รายงานไว้แล้ว)
                    continue
                if typ == "FS":
                    s = max(s, ef[p] + 1 + lag)
                elif typ == "SS":
                    s = max(s, es[p] + lag)
                elif typ == "FF":
                    s = max(s, ef[p] + lag - d + 1)
            if a.get("start_on"):
                s = max(s, self.cal.idx_on_or_before(parse_date(a["start_on"])) - 1)
            es[n] = max(0, s)
            ef[n] = es[n] + max(d, 1) - 1 if d > 0 else es[n] - 1
        proj_end = max([ef[n] for n in order if n not in auto] + [0])
        for n in auto:  # งานตามเวลา ครอบทั้งโครงการ
            es[n], ef[n], dur[n] = 0, proj_end, proj_end + 1
        # backward pass → float
        succ = defaultdict(list)
        for n, lst in preds.items():
            for p, typ, lag in lst:
                succ[p].append((n, typ, lag))
        lf, ls = {}, {}
        for n in reversed(order):
            f = proj_end
            for s_, typ, lag in succ[n]:
                if s_ not in ls:  # ลำดับงานวนกลับ
                    continue
                if typ == "FS":
                    f = min(f, ls[s_] - 1 - lag)
                elif typ == "SS":
                    f = min(f, ls[s_] - lag + max(dur[n], 1) - 1)
                elif typ == "FF":
                    f = min(f, lf[s_] - lag)
            lf[n] = f
            ls[n] = f - max(dur[n], 1) + 1
        out = {}
        for n in order:
            out[n] = {"es": es[n], "ef": ef[n], "dur": dur[n], "float": lf[n] - ef[n],
                      "state": state_of.get(n, "planned"),
                      "start": self.cal.date(es[n]).isoformat(),
                      "finish": self.cal.date(max(ef[n], es[n])).isoformat()}
        return out, proj_end

    # ─────────────────────────── baselines
    def baseline_dir(self):
        return os.path.join(self.folder, "baselines")

    def list_baselines(self):
        d = self.baseline_dir()
        return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []

    def save_baseline(self, name, status=None):
        sch, _ = self.schedule(status=status)
        os.makedirs(self.baseline_dir(), exist_ok=True)
        data = {"name": name, "created": dt.datetime.now().isoformat(timespec="seconds"),
                "activities": {k: {"es": v["es"], "ef": v["ef"], "dur": v["dur"]} for k, v in sch.items()}}
        with open(os.path.join(self.baseline_dir(), name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        self.meta["active_baseline"] = name
        self.save_meta()

    def baseline(self):
        name = self.meta.get("active_baseline")
        if not name:
            return None
        path = os.path.join(self.baseline_dir(), name + ".json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def save_meta(self):
        with open(os.path.join(self.folder, "project.json"), "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh, ensure_ascii=False, indent=2)

    # ─────────────────────────── progress
    def cell_pct(self, task_id, loc_id, date, sched_auto=None):
        t = self.task[task_id]
        if t["auto_time"]:
            return self.auto_time_pct(date)
        h = self.progress_hist.get((task_id, loc_id))
        if not h:
            return 0.0
        ds = date.isoformat()
        v = 0.0
        for r in h:
            if r[0] <= ds:
                v = r[2]
            else:
                break
        return v

    def cell_state(self, task_id, loc_id, date):
        h = self.progress_hist.get((task_id, loc_id)) or []
        ds = date.isoformat()
        last = None
        for r in h:
            if r[0] <= ds:
                last = r
        return {"pct": last[2] if last else 0.0, "steps": last[3] if last else "", "note": last[4] if last else "",
                "date": last[0] if last else ""}

    def auto_time_pct(self, date):
        """งานตามเวลา: % = วันทำงานที่ผ่านไป ÷ ระยะเวลาโครงการที่คาดการณ์ ณ วันนั้น (เสร็จจริงเมื่องานอื่นครบ)"""
        cache = self.__dict__.setdefault("_auto_cache", {})
        if date not in cache:
            n = self.cal.idx_on_or_before(date)
            if n <= 0:
                cache[date] = 0.0
            else:
                _, end = self.schedule(status=date)
                cache[date] = max(0.0, min(100.0, 100.0 * n / (end + 1)))
        return cache[date]

    def earned(self, date, cells=None):
        cells = cells if cells is not None else self.cells
        return sum(v * self.cell_pct(t, l, date) / 100.0 for (t, l), v in cells.items())

    def append_progress(self, date, entries, user=""):
        path = os.path.join(self.folder, "progress.csv")
        keys = ["date", "task_id", "loc_id", "pct", "steps", "note", "user", "saved_at"]
        new = not os.path.exists(path)
        now = dt.datetime.now().isoformat(timespec="seconds")
        with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
            w = csv.DictWriter(fh, keys)
            if new:
                w.writeheader()
            for e in entries:
                if (e["task_id"], e["loc_id"]) not in self.cells:
                    raise ValueError(f"ไม่มีงาน {e['task_id']} ที่ {e['loc_id']}")
                pct = max(0.0, min(100.0, _f(e["pct"])))
                w.writerow({"date": date, "task_id": e["task_id"], "loc_id": e["loc_id"], "pct": round(pct, 2),
                            "steps": e.get("steps", ""), "note": e.get("note", ""), "user": user, "saved_at": now})
        self.load_progress()

    # ─────────────────────────── milestones
    def eval_condition(self, cond, date):
        cond = cond.strip()
        m = re.fullmatch(r"ALL\s*>=\s*([\d.]+)", cond)
        if m:
            pct = 100.0 * self.earned(date) / self.total_value
            return {"text": cond, "pct": pct, "need": float(m.group(1)), "ok": pct >= float(m.group(1)) - 1e-9,
                    "task": "ALL", "floors": "", "value": self.total_value}
        m = re.fullmatch(r"([A-Z0-9_]+)\s*@\s*([A-Za-z0-9,\-]+)\s*>=\s*([\d.]+)", cond)
        if not m:
            self.issues.append(("error", f"เงื่อนไขงวดอ่านไม่ได้: '{cond}'"))
            return {"text": cond, "pct": 0, "need": 0, "ok": False, "task": "?", "floors": "", "value": 0}
        t, fl, need = m.group(1), floor_set(m.group(2)), float(m.group(3))
        cells = {c: v for c, v in self.cells.items() if c[0] == t and self.loc[c[1]]["floor"] in fl}
        val = sum(cells.values())
        if not val:
            self.issues.append(("warn", f"เงื่อนไข '{cond}' ไม่มีมูลค่างานในพื้นที่นั้น"))
            return {"text": cond, "pct": 0, "need": need, "ok": False, "task": t, "floors": m.group(2), "value": 0}
        pct = 100.0 * self.earned(date, cells) / val
        return {"text": cond, "pct": pct, "need": need, "ok": pct >= need - 1e-9, "task": t, "floors": m.group(2),
                "value": val}

    def condition_forecast(self, cond, sched):
        """วันที่คาดว่าเงื่อนไขจะครบ = finish สูงสุดของกิจกรรมที่ครอบคลุม"""
        cond = cond.strip()
        if cond.startswith("ALL"):
            return max(v["ef"] for v in sched.values())
        m = re.fullmatch(r"([A-Z0-9_]+)\s*@\s*([A-Za-z0-9,\-]+)\s*>=\s*([\d.]+)", cond)
        if not m:
            return None
        t, fl = m.group(1), floor_set(m.group(2))
        efs = [sched[a["act_id"]]["ef"] for a in self.activities
               if a["task_id"] == t and a["floor_set"] & fl and a["act_id"] in sched]
        return max(efs) if efs else None

    def milestone_status(self, date, sched, base=None):
        out, cum = [], 0.0
        for m in self.milestones:
            conds = [c for c in m["conditions"].split(";") if c.strip()]
            ev = [self.eval_condition(c, date) for c in conds]
            fc = [self.condition_forecast(c, sched) for c in conds]
            fc = [x for x in fc if x is not None]
            bfc = None
            if base:
                bs = {k: {"ef": v["ef"]} for k, v in base["activities"].items()}
                b = [self.condition_forecast(c, bs) for c in conds]
                b = [x for x in b if x is not None]
                bfc = self.cal.date(max(b)).isoformat() if b else None
            cum += _f(m["pct"])
            b = self.billing.get(m["no"], {})
            row = {**{k: m[k] for k in m}, "pct": _f(m["pct"]), "amount": _f(m["amount"]), "cum_pct": cum,
                   "checks": ev, "ready": all(e["ok"] for e in ev) if ev else m.get("kind") == "vo",
                   "forecast": self.cal.date(max(fc)).isoformat() if fc else None,
                   "baseline_forecast": bfc}
            for k in ("submitted", "approved", "paid", "invoice_no", "evidence_date", "note"):
                row[k] = b.get(k) or row.get(k) or ""
            row["status"] = ("paid" if row["paid"] else "approved" if row["approved"] else
                             "submitted" if row["submitted"] else "ready" if row["ready"] else "planned")
            row["money"] = self.money(row["amount"], None if m.get("kind") == "vo" else row["pct"])
            row["kind"] = m.get("kind") or "contract"
            out.append(row)
        return out

    def money(self, amount, pct=None):
        """แยกยอดตามรูปแบบตารางงวด: (1) มูลค่างวด (2) VAT (3) รวม (4) ประกันผลงาน (5) (3)-(4) (6) หัก ณ ที่จ่าย (7) สุทธิ"""
        m = self.meta
        incl = _f(m.get("contract_value_incl_vat"))
        if pct is not None and incl:  # งวด = % ของยอดรวม VAT แล้วถอด VAT (ไม่ปัดระหว่างทาง)
            amount = _f(pct) * incl / (1 + _f(m.get("vat_rate", 0.07)))
        vat = amount * _f(m.get("vat_rate", 0.07))
        ret = amount * _f(m.get("retention_rate", 0.05))
        wht = amount * _f(m.get("wht_rate", 0.03))
        r2 = lambda x: round(x + 1e-9, 2)
        # คิดจากค่าที่ยังไม่ปัด แล้วปัดตอนท้าย (ตรงกับตารางงวดของสัญญา)
        return {"amount": r2(amount), "vat": r2(vat), "gross": r2(amount + vat), "retention": r2(ret),
                "after_retention": r2(amount + vat - ret), "wht": r2(wht), "net": r2(amount + vat - ret - wht)}

    def save_billing(self, no, fields):
        if no not in {m["no"] for m in self.milestones}:
            raise KeyError(no)
        cur = dict(self.billing.get(no, {}))
        for k, v in fields.items():
            if k in ("submitted", "approved", "paid", "invoice_no", "evidence_date", "note"):
                if v in (None, ""):
                    cur.pop(k, None)
                else:
                    cur[k] = str(v)
        cur["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        self.billing[no] = cur
        with open(os.path.join(self.folder, "billing.json"), "w", encoding="utf-8") as fh:
            json.dump(self.billing, fh, ensure_ascii=False, indent=1)

    # ─────────────────────────── แบบแปลน (heatmap)
    def slot(self, loc):
        """ชื่อขอบเขตบนแบบที่ไม่ขึ้นกับชั้น — ใช้ร่วมกันได้เมื่อหลายชั้นใช้แบบแผ่นเดียวกัน
        ทั้งชั้น → '*' · ผนังภายนอก → 'EXT' · ห้อง F3-321 → '21' · ส่วนกลาง F3-CORR → 'CORR'"""
        if loc["kind"] == "floor":
            return "*"
        if loc["kind"] == "facade":
            return "EXT"
        lid, fl = loc["loc_id"], loc["floor"]
        rest = lid[len("F" + fl + "-"):] if lid.startswith("F" + fl + "-") else lid
        if loc["kind"] == "room" and rest.startswith(fl) and len(rest) > len(fl):
            rest = rest[len(fl):]
        return rest

    def planned_cell_pct(self, date):
        """% ตามแผน (Baseline ถ้ามี) ของแต่ละ cell ณ วันที่ — แผนเป็นเส้นตรงตลอดช่วงกิจกรรม"""
        base = self.baseline()
        sch = base["activities"] if base else self.schedule()[0]
        n = self.cal.idx_on_or_before(date)
        out = {}
        for a in self.activities:
            s = sch.get(a["act_id"])
            if not s:
                continue
            frac = max(0.0, min(1.0, (n - s["es"]) / max(s["ef"] - s["es"] + 1, 1)))
            for c in a["cells"]:
                out[c] = 100.0 * frac
        return out

    def heat(self, floor, date, trade=None, task=None):
        tasks_ok = {t["task_id"] for t in self.tasks if (not trade or t["trade"] == trade) and (not task or t["task_id"] == task)}
        plan = self.planned_cell_pct(date)
        rows = []
        for l in self.locations:
            if l["floor"] != floor:
                continue
            cells = [(c, v) for c, v in self.cells.items() if c[1] == l["loc_id"] and c[0] in tasks_ok]
            v = sum(x[1] for x in cells)
            if not v:
                continue
            act = sum(v_ * self.cell_pct(c[0], c[1], date) for c, v_ in cells) / v
            pl = sum(v_ * plan.get(c, 0.0) for c, v_ in cells) / v
            rows.append({"loc_id": l["loc_id"], "name": l["name"], "kind": l["kind"], "rtype": l["rtype"],
                         "slot": self.slot(l), "value": v, "pct": act, "plan_pct": pl})
        sheet = self.plans.get("floor_sheet", {}).get(floor)
        return {"floor": floor, "sheet": sheet, "rows": rows,
                "zones": self.zones.get(sheet, {}) if sheet else {},
                "sheet_floors": sorted(f for f, sh in self.plans.get("floor_sheet", {}).items() if sh == sheet)}

    def loc_detail(self, loc_id, date):
        plan = self.planned_cell_pct(date)
        out = []
        for t in self.tasks:
            c = (t["task_id"], loc_id)
            if c in self.cells:
                out.append({"task_id": t["task_id"], "name": t["name"], "trade": t["trade"], "value": self.cells[c],
                            "pct": self.cell_pct(c[0], c[1], date), "plan_pct": plan.get(c, 0.0),
                            "auto_time": t["auto_time"]})
        return {"loc": self.loc[loc_id], "tasks": out}

    def save_zone(self, sheet, slot, polys):
        if sheet not in self.plans.get("sheets", {}):
            raise KeyError(sheet)
        z = self.zones.setdefault(sheet, {})
        if polys:
            z[slot] = [[[round(float(x), 5), round(float(y), 5)] for x, y in poly] for poly in polys if len(poly) >= 3]
        else:
            z.pop(slot, None)
        with open(os.path.join(self.folder, "zones.json"), "w", encoding="utf-8") as fh:
            json.dump(self.zones, fh, ensure_ascii=False, indent=1)

    # ─────────────────────────── S-curve
    def scurve(self, data_date, trade=None, step_days=7):
        sched, end_cur = self.schedule(status=data_date)      # คาดการณ์จากความคืบหน้าจริง
        plain, _ = self.schedule()                             # แผนที่ยังไม่สะท้อนความคืบหน้า
        base = self.baseline()
        tasks_ok = {t["task_id"] for t in self.tasks if not trade or t["trade"] == trade}
        cells = {c: v for c, v in self.cells.items() if c[0] in tasks_ok}
        total = sum(cells.values()) or 1.0
        acts = [a for a in self.activities if a["task_id"] in tasks_ok]
        aval = {a["act_id"]: sum(cells.get(c, 0) for c in a["cells"]) for a in acts}

        def planned(sch, d):
            n = self.cal.idx_on_or_before(d)  # วันทำงานที่ผ่านไปถึงสิ้นวัน d
            s = 0.0
            for a in acts:
                v = aval[a["act_id"]]
                if not v or a["act_id"] not in sch:
                    continue
                es, ef = sch[a["act_id"]]["es"], sch[a["act_id"]]["ef"]
                s += v * max(0.0, min(1.0, (n - es) / max(ef - es + 1, 1)))
            return 100.0 * s / total

        # เส้นคาดการณ์: ผลงาน ณ วันข้อมูล + เนื้องานที่เหลือกระจายตามแผนที่ปรับแล้ว
        st_idx = self.cal.idx_on_or_before(data_date) - 1
        earned0 = self.earned(data_date, cells)
        remain = []
        for a in acts:
            v = aval[a["act_id"]]
            if not v:
                continue
            if self.task[a["task_id"]]["auto_time"]:
                pct = self.auto_time_pct(data_date)
            else:
                pct = self.act_progress(a, data_date)[0] if a["value"] else 0.0
            r = v * (1 - pct / 100.0) * (sum(cells.get(c, 0) for c in a["cells"]) / v if v else 0)
            if r <= 1e-6:
                continue
            sc = sched[a["act_id"]]
            lo = max(sc["es"], st_idx + 1)
            remain.append((r, lo, max(sc["ef"], lo)))

        def forecast(d):
            n = self.cal.idx_on_or_before(d)
            return 100.0 * (earned0 + sum(r * max(0.0, min(1.0, (n - lo) / (hi - lo + 1))) for r, lo, hi in remain)) / total

        base_sched = base["activities"] if base else plain
        end_idx = max(end_cur, max((v["ef"] for v in base_sched.values()), default=0))
        start = self.cal.date(0)
        end = max(self.cal.date(end_idx), data_date)
        pts, d = [], start
        while True:
            pts.append(d)
            if d >= end:
                break
            d = min(d + dt.timedelta(days=step_days), end)
        if data_date not in pts and start <= data_date <= end:
            pts.append(data_date)
            pts.sort()
        series = []
        for d in pts:
            row = {"date": d.isoformat(), "baseline": planned(base_sched, d)}
            if d >= data_date:
                row["forecast"] = forecast(d)
            if d <= data_date:
                row["actual"] = 100.0 * self.earned(d, cells) / total
            series.append(row)
        # แผนเบิกงวด (ตาม baseline ถ้ามี) และที่เบิกจริง
        ms = self.milestone_status(data_date, sched, base)
        bill_plan, bill_actual = [], []
        for m in ms:
            when = m["baseline_forecast"] or m["forecast"]
            if when:
                bill_plan.append({"date": when, "pct": m["pct"] * 100, "no": m["no"]})
            for key in ("paid", "submitted"):
                if m.get(key):
                    bill_actual.append({"date": m[key], "pct": m["pct"] * 100, "no": m["no"], "kind": key})
                    break
        return {"series": series, "bill_plan": sorted(bill_plan, key=lambda x: x["date"]),
                "bill_actual": sorted(bill_actual, key=lambda x: x["date"]), "total_value": total,
                "has_baseline": bool(base_sched), "baseline_name": base["name"] if base else None}

    # ─────────────────────────── activity view
    def activity_rows(self, date):
        sched, end = self.schedule(status=date)
        base = self.baseline()
        rows = []
        for a in self.activities:
            s = sched.get(a["act_id"])
            if not s:
                continue
            v = a["value"]
            pct = (100.0 * sum(self.cells[c] * self.cell_pct(c[0], c[1], date) / 100 for c in a["cells"]) / v) if v else 0.0
            t = self.task[a["task_id"]]
            fl = a["floors"]
            label = a["name"] or f"{t['name']} — " + (f"ชั้น {fl}" if fl[0].isdigit() else self.loc.get(fl, {}).get("name", fl))
            b = base["activities"].get(a["act_id"]) if base else None
            rows.append({
                "act_id": a["act_id"], "task_id": a["task_id"], "trade": t["trade"], "name": label,
                "custom_name": a["name"],
                "floors": fl, "duration": s["dur"], "preds": a.get("preds", ""), "start": s["start"],
                "finish": s["finish"], "es": s["es"], "ef": s["ef"], "float": s["float"],
                "critical": s["float"] <= 0, "value": v, "weight": 100.0 * v / self.total_value, "pct": pct,
                "b_start": self.cal.date(b["es"]).isoformat() if b else None,
                "b_finish": self.cal.date(max(b["ef"], b["es"])).isoformat() if b else None,
                "auto_time": t["auto_time"], "state": s["state"],
            })
        rows.sort(key=lambda r: (r["es"], r["ef"]))
        return rows, sched, end

    def update_activity(self, act_id, fields):
        a = self.act.get(act_id)
        if not a:
            raise KeyError(act_id)
        for k in ("duration", "preds", "name", "start_on"):
            if k in fields:
                a[k] = str(fields[k])
        # ตรวจลำดับงานก่อนบันทึก
        self.schedule()
        if self.sched_issues:
            raise ValueError(self.sched_issues[0][1])
        keys = ["act_id", "task_id", "floors", "duration", "preds", "name", "start_on"]
        with open(os.path.join(self.folder, "activities.csv"), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, keys)
            w.writeheader()
            for x in self.activities:
                w.writerow({k: x.get(k, "") for k in keys})
        self._auto_cache = {}

    def validation(self):
        self.schedule()
        out = list(dict.fromkeys(self.issues + self.sched_issues))
        tot_w = 100.0 * self.total_value / self.total_value if self.total_value else 0
        contract_ms = [m for m in self.milestones if m.get("kind") != "vo"]
        ms_sum = sum(_f(m["pct"]) for m in contract_ms)
        if abs(ms_sum - 1.0) > 1e-6:
            out.append(("error", f"งวดงานรวม {ms_sum*100:.2f}% ไม่เท่ากับ 100%"))
        base = self.baseline()
        if base:
            miss = [a["act_id"] for a in self.activities if a.get("vo") and a["act_id"] not in base["activities"]]
            if miss:
                out.append(("warn", f"VO ที่อนุมัติแล้วยังไม่อยู่ใน Baseline ({', '.join(miss)}) — ควรล็อก Baseline ใหม่"))
        cv = _f(self.meta["contract_value_ex_vat"])
        ms_amt = sum(_f(m["amount"]) for m in contract_ms)
        if abs(ms_amt - cv) > 1:
            out.append(("warn", f"มูลค่างวดรวม {ms_amt:,.2f} ≠ มูลค่าสัญญา {cv:,.2f}"))
        for t in self.tasks:
            if not t["auto_time"]:
                s = sum(x["w"] for x in t["step_list"])
                if abs(s - 100) > 1e-6:
                    out.append(("error", f"หมวด {t['task_id']}: น้ำหนักขั้นตอนรวม {s:g} ≠ 100"))
        checks = [
            ("ok", f"ผลรวม BOQ ในขอบเขต {self.in_scope:,.2f} บาท กระจายลงพื้นที่ครบ {self.total_value:,.2f}"),
            ("ok", f"น้ำหนักงานรวม {tot_w:.2f}% · งวดงาน {len(self.milestones)} งวด รวม {ms_sum*100:.2f}%"),
            ("ok", f"กิจกรรม {len(self.activities)} แท่ง · พื้นที่ {len(self.locations)} · หมวดงาน {len(self.tasks)}"),
        ]
        return checks + out
