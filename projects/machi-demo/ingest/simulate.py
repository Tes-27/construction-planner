"""จำลองความคืบหน้าสำหรับโครงการตัวอย่าง (ไม่ใช่ข้อมูลจริง)
งานช้ากว่าแผนแบบค่อยเป็นค่อยไป: ระยะงานจริงยาวขึ้น 25–45% และห้องในชั้นเดียวกันทยอยเสร็จ
"""
import csv, datetime as dt, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "..", "..", "app"))
import core
random.seed(7)
p = core.Project(PROJ)
sched, end = p.schedule()
TODAY = dt.date(2026, 10, 17)
slip, rows = {}, []
for a in sorted(p.activities, key=lambda a: sched[a["act_id"]]["es"]):
    if p.task[a["task_id"]]["auto_time"]:
        continue
    s = sched[a["act_id"]]
    k = 1.25 + 0.2 * s["es"] / max(1, end)          # ยิ่งท้ายโครงการยิ่งช้า
    st = int(s["es"] * k) + random.randint(0, 3)
    du = max(1, int(s["dur"] * (1.1 + random.random() * 0.3)))
    cells = sorted(a["cells"], key=lambda c: c[1])
    n = len(cells)
    for i, (t, l) in enumerate(cells):
        # ห้องทยอยเริ่ม: ห้องแรกเริ่มก่อน ห้องท้ายเริ่มช้ากว่า
        cs = st + int(du * 0.5 * i / max(1, n))
        cd = max(1, int(du * 0.55))
        steps = p.task[t]["step_list"]
        last = -1
        d = p.cal.date(cs)
        while d <= TODAY:
            if d.weekday() in (1, 3, 5) or d >= p.cal.date(cs + cd):     # บันทึก อ. พฤ. ส.
                n_done = p.cal.idx_on_or_before(d) - cs
                pct = max(0.0, min(100.0, 100.0 * n_done / cd))
                acc, bits, stop = 0.0, "", False
                for stp in steps:  # ขั้นตอนทำตามลำดับ
                    ok = not stop and acc + stp["w"] <= pct + 1e-9
                    stop = stop or not ok
                    bits += "1" if ok else "0"
                    acc += stp["w"] if ok else 0
                pct = acc if pct < 100 else 100.0
                if pct != last:
                    rows.append({"date": d.isoformat(), "task_id": t, "loc_id": l, "pct": pct, "steps": bits,
                                 "note": "", "user": "demo", "saved_at": ""})
                    last = pct
                if pct >= 100:
                    break
            d += dt.timedelta(days=1)
rows.sort(key=lambda r: r["date"])
with open(os.path.join(PROJ, "progress.csv"), "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
meta = json.load(open(os.path.join(PROJ, "project.json"), encoding="utf-8"))
meta["name"] = "[ตัวอย่าง] " + meta["name"]; meta["short"] = "Machi (ตัวอย่าง)"
meta["assumptions"] = ["โครงการนี้เป็นข้อมูลจำลองเพื่อดูการทำงานของโปรแกรม — ความคืบหน้าไม่ใช่ของจริง"] + meta["assumptions"]
json.dump(meta, open(os.path.join(PROJ, "project.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# งวดที่ยื่น/ได้รับเงินแล้ว (จำลอง) → billing.json
p = core.Project(PROJ)
bill = {}
for m in p.milestones:
    conds = [c for c in m["conditions"].split(";") if c.strip()]
    if not all(p.eval_condition(c, TODAY)["ok"] for c in conds):
        continue
    d = p.cal.date(0)
    while d <= TODAY and not all(p.eval_condition(c, d)["ok"] for c in conds):
        d += dt.timedelta(days=7)
    sub = min(TODAY, d + dt.timedelta(days=3))
    b = {"submitted": sub.isoformat(), "evidence_date": d.isoformat(), "invoice_no": f"MCH-{m['no']}"}
    if sub + dt.timedelta(days=7) <= TODAY:
        b["approved"] = (sub + dt.timedelta(days=7)).isoformat()
    if sub + dt.timedelta(days=21) <= TODAY:
        b["paid"] = (sub + dt.timedelta(days=21)).isoformat()
    bill[m["no"]] = b
json.dump(bill, open(os.path.join(PROJ, "billing.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rows), "progress rows ·", sum(1 for b in bill.values() if "paid" in b), "paid ·",
      sum(1 for b in bill.values() if "paid" not in b), "submitted/approved")
print("earned at", TODAY, round(100 * p.earned(TODAY) / p.total_value, 1), "%")
