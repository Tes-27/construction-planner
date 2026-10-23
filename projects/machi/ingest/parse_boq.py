"""แปลง BOQ ของ Machi (TCM Ritthikorn) → boq_raw.csv (ยังไม่ผูก task)

โครงชีต: A=ลำดับ B=รายละเอียด C=qty D=หน่วย E/F=วัสดุ ราคา/เงิน G/H=ค่าแรง ราคา/เงิน I=รวม
แต่ละชีตมีบล็อกสรุปหมวดย่อยด้านบน (จบที่ "รวมราคาหมวด...") แล้วตามด้วยรายละเอียดทีละหมวดย่อย
(จบที่ "รวม...") — บางหมวด (EE 4.5/4.6) รายละเอียดเป็นต่อห้อง ต้องคูณด้วย qty ในบล็อกสรุป
"""
import csv, sys, openpyxl

for _s in (sys.stdout, sys.stderr):  # Windows: คอนโซลอาจเป็น cp874 → พิมพ์ภาษาไทย/สัญลักษณ์ไม่พัง
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SHEETS = [("PRELIM", "PRELIM", "1"), ("STR", "STR", "2"), ("ARCH", "ARCH", "3"),
          ("EE", "EE", "4"), ("SN", "SN", "5"), ("FP", "FP", "6")]
CORRUPT = "ไฟฟ้าOwnerมีทีมดำเนินการเองเราเริ่มที่ตู้"
TEXT_SCOPE = {"excluded": "excluded", "ไม่รวม": "excluded", "by owner": "owner"}


def num(v):
    return float(v) if isinstance(v, (int, float)) else None


def txt(v):
    return str(v).strip() if v is not None else ""


def read_sheet(ws, sheet, trade, cat):
    rows = [[ws.cell(r, c).value for c in range(1, 10)] for r in range(1, min(ws.max_row, 2000) + 1)]
    # --- บล็อกสรุป: ชื่อหมวดย่อย + ยอดรวม + qty (ตัวคูณ)
    summary, i = [], 6
    while i < len(rows):
        a, b, c, d, e, f, g, h, tot = rows[i]
        if txt(b).startswith("รวมราคาหมวด"):
            break
        if txt(b) and i > 6 and (num(tot) is not None or txt(tot)):
            summary.append({"name": txt(b), "qty": num(c) or 1, "total": num(tot) or 0.0, "text": txt(tot)})
        i += 1
    sheet_total = num(rows[i][8]) or 0.0
    detail_start = i + 1

    items, issues = [], []
    if sheet == "PRELIM":  # PRELIM ไม่มีหมวดย่อย — รายการอยู่ในบล็อกบนเลย
        summary = [{"name": "หมวดงานเตรียมพื้นที่", "qty": 1, "total": sheet_total, "text": ""}]
        detail_start = 6
    sec_idx, sec, n_in_sec, group, sec_items = -1, None, 0, "", []

    def close_section(stated):
        if sec is None:
            return
        s = sum(x["amount"] for x in sec_items)
        mult = 1.0
        if stated is not None and s > 0 and abs(s - stated) > 1:
            issues.append(f"{sheet} {sec['code']}: ผลรวมรายการ {s:,.2f} ≠ บรรทัดรวม {stated:,.2f}")
        target = sec["total"]
        if stated is not None and abs(s - target) <= 1 and abs(s - stated) > 1:
            issues[-1] += " — ใช้ยอดหน้าสรุป (รวมค่าแรงติดตั้งของวัสดุผู้ว่าจ้าง)"
        if s > 0 and abs(s - target) > 1:
            ratio = target / s
            if abs(ratio - round(ratio)) < 1e-6 and round(ratio) == sec["qty"]:
                mult = ratio  # รายละเอียดเป็นต่อหน่วย (เช่นต่อห้อง) → คูณ
                issues.append(f"{sheet} {sec['code']}: รายละเอียดเป็นต่อหน่วย ×{ratio:g} ({sec['name']})")
            else:
                issues.append(f"{sheet} {sec['code']}: รายละเอียดรวม {s:,.2f} ≠ สรุป {target:,.2f}")
        for x in sec_items:
            x["qty"] = round(x["qty"] * mult, 4) if x["qty"] is not None else None
            x["amount"] = round(x["amount"] * mult, 2)
            x["mat"] = round(x["mat"] * mult, 2)
            x["lab"] = round(x["lab"] * mult, 2)
            x["multiplier"] = mult
        items.extend(sec_items)

    for r in range(detail_start, len(rows)):
        a, b, c, d, e, f, g, h, tot = rows[r]
        A, B = txt(a), txt(b)
        if not B and not A:
            continue
        if B.startswith("รวม"):
            if sheet != "PRELIM":
                close_section(num(tot))
                sec = None
            else:
                break
            continue
        has_val = num(tot) is not None or txt(tot) or num(f) or num(h)
        has_qty = num(c) is not None or txt(d)
        is_header_like = not has_val and not has_qty
        # หัวหมวดย่อยในส่วนรายละเอียด = มีเลขลำดับ ไม่มีตัวเลข และชื่อตรงกับบล็อกสรุปลำดับถัดไป
        if sheet != "PRELIM" and A and is_header_like and sec is None:
            sec_idx += 1
            if sec_idx >= len(summary):
                break
            sm = summary[sec_idx]
            sec = {"code": f"{cat}.{sec_idx + 1}", "name": sm["name"], "qty": sm["qty"], "total": sm["total"]}
            if B[:12] != sm["name"][:12]:
                issues.append(f"{sheet} แถว {r+1}: หัวหมวด '{B}' ไม่ตรงกับสรุป '{sm['name']}'")
            n_in_sec, group, sec_items = 0, "", []
            continue
        if sheet == "PRELIM" and sec is None:
            sec = {"code": "1", "name": "หมวดงานเตรียมพื้นที่", "qty": 1, "total": sheet_total}
            sec_items = []
        if sec is None:
            continue
        if is_header_like:
            group = B if B != CORRUPT else group
            continue
        if not B or B == "***":
            continue
        n_in_sec += 1
        code = f"{sec['code']}.{n_in_sec}" if sheet != "PRELIM" else f"1.{n_in_sec}"
        scope, amount, note = "in", num(tot), ""
        t = txt(tot).lower()
        if amount is None:
            amount = (num(f) or 0) + (num(h) or 0)
            if t in TEXT_SCOPE:
                if amount > 0:  # วัสดุผู้ว่าจ้าง แต่ผู้รับเหมาคิดค่าติดตั้ง (หน้าสรุปนับรวม F+H)
                    note = "วัสดุโดยผู้ว่าจ้าง (คิดค่าแรง)"
                else:
                    scope = TEXT_SCOPE[t]
        if txt(e).lower() == "by owner" or txt(g).lower() == "by owner":
            note = note or "วัสดุโดยผู้ว่าจ้าง"
        if txt(e) == "ไม่รวม":
            note = note or "ไม่รวมค่าวัสดุ"
        desc = B
        if B == CORRUPT:
            desc = f"[คำอธิบายเสียในต้นฉบับ แถว {r+1}]"
            issues.append(f"{sheet} แถว {r+1}: คำอธิบายถูกเขียนทับด้วย '{CORRUPT}' (น่าจะแก้ไขตอน group ชีต)")
        if desc.startswith("-"):
            desc = (group + " " + desc).strip()
        if amount == 0 and scope == "in":
            scope = "zero"
        sec_items.append({
            "code": code, "boq_ref": A, "trade": trade, "section": sec["code"], "section_name": sec["name"],
            "description": desc, "group": group, "qty": num(c), "unit": txt(d),
            "mat": num(f) or 0.0, "lab": num(h) or 0.0, "amount": round(amount, 2), "scope": scope,
            "src": f"{sheet}!{r+1}", "multiplier": 1.0, "note": note,
        })
    if sheet == "PRELIM":
        close_section(None)
    elif sec is not None:
        close_section(None)
    got = sum(x["amount"] for x in items)
    if abs(got - sheet_total) > 1:
        issues.append(f"{sheet}: รวมทุกรายการ {got:,.2f} ≠ ยอดหมวด {sheet_total:,.2f}")
    return items, issues, sheet_total


def main(src, out):
    wb = openpyxl.load_workbook(src, data_only=True)
    all_items, all_issues = [], []
    for sheet, trade, cat in SHEETS:
        items, issues, total = read_sheet(wb[sheet], sheet, trade, cat)
        all_items += items
        all_issues += issues
        print(f"{sheet:7s} {len(items):4d} รายการ  รวม {sum(x['amount'] for x in items):>15,.2f}  (ยอดในชีต {total:,.2f})")
    keys = list(all_items[0].keys())
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        w.writerows(all_items)
    print(f"\nรวมทั้งหมด {sum(x['amount'] for x in all_items):,.2f}")
    print("\n".join("! " + s for s in all_issues))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
