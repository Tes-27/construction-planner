"""สร้างไฟล์รูปแบบกลางของ Machi จาก boq_raw.csv + ความรู้จากแบบ/ตารางงวด

ผลลัพธ์ (ในโฟลเดอร์โครงการ): project.json, locations.csv, tasks.csv, boq.csv, activities.csv, milestones.csv
ทุกอย่างที่เป็น "สมมติฐาน" ถูกเขียนลง project.json → assumptions ให้ผู้ใช้ยืนยัน
"""
import csv, json, os, sys

for _s in (sys.stdout, sys.stderr):  # Windows: คอนโซลอาจเป็น cp874 → พิมพ์ภาษาไทย/สัญลักษณ์ไม่พัง
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)


def write_csv(name, rows, keys=None):
    keys = keys or list(rows[0].keys())
    with open(os.path.join(PROJ, name), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


# ───────────────────────── project.json
TH_HOLIDAYS = [  # วันหยุดราชการโดยประมาณ — แก้ได้ใน project.json
    "2025-10-13", "2025-10-23", "2025-12-05", "2025-12-10", "2025-12-31", "2026-01-01", "2026-01-02",
    "2026-03-03", "2026-04-06", "2026-04-13", "2026-04-14", "2026-04-15", "2026-05-01", "2026-05-04",
    "2026-06-01", "2026-06-03", "2026-07-28", "2026-07-29", "2026-07-30", "2026-08-12", "2026-10-13",
]
project = {
    "name": "Machi Residences — อาคารพักอาศัยรวม ค.ส.ล. 7 ชั้น",
    "short": "Machi",
    "owner": "บริษัท ฤทธิกร ลิฟวิ่ง จำกัด",
    "contractor": "บริษัท ไทรฟ์ ดีเวลลอปเม้นท์ จำกัด",
    "location": "ต.ปลวกแดง อ.ปลวกแดง จ.ระยอง",
    "contract_no": "",          # ใส่เองได้ — แสดงในใบขอเบิก
    "owner_address": "",
    "contractor_address": "",
    "contractor_tax_id": "",
    "ld_cap_pct": 0.10,         # เพดานค่าปรับ (สัดส่วนมูลค่าสัญญารวม VAT) — ค่าปรับต่อวันตั้งในโปรแกรม
    "contract_value_ex_vat": 42056074.77,
    "contract_value_incl_vat": 45000000.00,
    "boq_total": 40215020.00,
    "vat_rate": 0.07,
    "retention_rate": 0.05,
    "wht_rate": 0.03,
    "start_date": "2025-10-06",
    "finish_date": "2026-10-05",
    "calendar": {"workdays": [0, 1, 2, 3, 4, 5], "holidays": TH_HOLIDAYS},
    "plans": {
        "SITE": "A-P00", "F1": "A-P01", "F2": "A-P02", "F3": "A-P03", "F4": "A-P03", "F5": "A-P03",
        "F6": "A-P04", "F7": "A-P05", "RF": "A-P06",
    },
    "assumptions": [
        "ห้อง Type B (EE 4.6) = ห้อง X21 ของชั้น 2–6 ชั้นละ 1 ห้อง — ยังไม่ได้ยืนยันจากแบบ EE",
        "พื้นที่ห้อง/โซน ประมาณจากแบบ A-P01..A-P05 (ห้องพัก ~30 ม² รวมห้องน้ำและระเบียง) ใช้ถ่วงน้ำหนักการกระจาย BOQ",
        "F4 (กระเบื้องห้องน้ำ+ระเบียง 471 ม²) แบ่ง ห้องน้ำ 46% / ระเบียง 54% ตามพื้นที่โดยประมาณ",
        "PT slab / เหล็กพื้น กระจายเท่ากันชั้น 2–7, คาน กระจายเท่ากันชั้น 1–7 (ชั้น 1 = คานคอดิน), เสา/ผนังลิฟต์ ชั้น 1–7",
        "ค่าดำเนินการตามเวลา (PRELIM ค่าน้ำไฟ บริหาร นั่งร้าน ฯลฯ) นับผลงานตามเวลาที่ผ่านไป",
        "ปฏิทิน: ทำงาน จ.–ส. หยุดอาทิตย์และวันหยุดราชการ (ประมาณ)",
        "ค่าปรับล่าช้า 0.1% ของมูลค่าสัญญารวม VAT ต่อวัน (45,000 บาท/วัน) เพดาน 10% — ค่าทั่วไป ยังไม่เห็นสัญญาจริง แก้ได้ในแท็บ VO/EOT",
        "หลังคาเป็นโครงเหล็ก+เมทัลชีท ไม่มีพื้นดาดฟ้า ค.ส.ล. (ตามแบบ A-P06)",
    ],
    "source_issues": [],
}

# ───────────────────────── locations
GUEST = [21, 22, 23, 24, 25, 26, 27, 28, 30, 32, 33, 34, 35, 36]
locs = []


def L(id_, floor, kind, name, area, rtype=""):
    locs.append({"loc_id": id_, "floor": floor, "kind": kind, "name": name, "area": area, "rtype": rtype})


L("FDN", "FDN", "floor", "ฐานรากและเสาเข็ม", 525)
for f in range(1, 8):
    L(f"F{f}", str(f), "floor", f"ชั้น {f} (ทั้งชั้น)", 525)
# ชั้น 1
L("F1-PARK", "1", "parking", "ที่จอดรถ", 380)
L("F1-LOBBY", "1", "common", "โถงทางเข้า", 20)
L("F1-WALK", "1", "common", "ทางเดิน", 25)
L("F1-ELEC", "1", "service", "ห้องไฟฟ้า", 14)
L("F1-STORE", "1", "service", "ห้องเก็บของ", 12)
L("F1-WC1", "1", "wc", "WC-1", 5)
L("F1-ST1", "1", "stair", "บันได ST-1", 14)
L("F1-ST2", "1", "stair", "บันไดหนีไฟ ST-2", 12)
L("F1-LIFT", "1", "lift", "ลิฟต์", 8)
# ชั้น 2–6
for f in range(2, 7):
    for n in GUEST:
        L(f"F{f}-{f}{n}", str(f), "room", f"{f}{n}", 30, "B" if n == 21 else "A")
    L(f"F{f}-CORR", str(f), "common", "โถงทางเดิน", 50)
    L(f"F{f}-PREP", str(f), "common", "เตรียมอาหาร", 10)
    L(f"F{f}-ELEC", str(f), "service", "ห้องไฟฟ้า", 5)
    L(f"F{f}-ST1", str(f), "stair", "บันได ST-1", 14)
    L(f"F{f}-ST2", str(f), "stair", "โถงบันได ST-2", 12)
    L(f"F{f}-LIFT", str(f), "lift", "โถงลิฟต์", 8)
# ชั้น 7 ห้องใต้หลังคา
L("F7-ATTIC", "7", "attic", "ห้องใต้หลังคา", 360)
for i in range(1, 6):
    L(f"F7-STORE{i}", "7", "service", f"ห้องเก็บของ {i}", 9.6)
L("F7-STORE6", "7", "service", "ห้องเก็บของ (ข้างโถงลิฟต์)", 8)
L("F7-STORE7", "7", "service", "ห้องเก็บของ (ข้างบันได)", 8)
L("F7-WC3", "7", "wc", "WC-3", 4)
L("F7-LIFT", "7", "lift", "โถงลิฟต์", 10)
L("F7-ST1", "7", "stair", "บันได ST-1", 14)
for f in range(1, 8):
    L(f"F{f}-EXT", str(f), "facade", f"ผนังภายนอก ชั้น {f}", 330)
L("RF", "RF", "roof", "หลังคา", 525)
L("SITE", "SITE", "site", "ภายนอกอาคาร (ถนน/ลานจอด/ระบายน้ำ)", 700)

# ───────────────────────── tasks (หมวดงานสำหรับวัดผล) + ขั้นตอนการนับ %
ENCL = "kinds=room,common,service,wc,stair,lift,attic"
tasks = [
    # id, ชื่อ, trade, steps
    ("PRE_SETUP", "งานเตรียมการ สิ่งก่อสร้างชั่วคราว", "PRELIM", "วางผัง:20|สำนักงาน/บ้านพัก/โรงเก็บ:60|ป้าย/แผงกันฝุ่น:20"),
    ("PRE_TIME", "ค่าดำเนินการตามเวลา", "PRELIM", "auto-time"),
    ("PILE", "งานเสาเข็ม", "STR", "ตอกเข็ม:80|ทดสอบ:5|ตัดหัวเข็ม:15"),
    ("FDN", "งานดิน + ฐานราก", "STR", "ขุดดิน:10|คอนกรีตหยาบ:5|เหล็กเสริม:35|ไม้แบบ:10|เทคอนกรีต:35|ถมดิน:5"),
    ("STR_SLAB", "โครงสร้างพื้น + คาน + บันได", "STR", "ไม้แบบ:25|เหล็กเสริม/PT:35|เทคอนกรีต:30|ดึงลวด PT:10"),
    ("STR_COL", "โครงสร้างเสา + ผนังลิฟต์", "STR", "เหล็กเสริม:40|ไม้แบบ:25|เทคอนกรีต:35"),
    ("ROOF", "หลังคาโครงเหล็ก + เมทัลชีท", "STR", "โครงเหล็ก:40|ทาสีโครง:10|มุงหลังคา:40|รางน้ำ/ครอบ:10"),
    ("WALL", "ผนังก่ออิฐ + เสาเอ็นทับหลัง", "ARCH", "ก่ออิฐ:65|เสาเอ็น-ทับหลัง:25|จับเฟี้ยม:10"),
    ("EE_CONDUIT", "ท่อร้อยสายไฟฝังผนัง", "EE", "ท่อในผนัง:70|ท่อบนฝ้า/บ็อกซ์:30"),
    ("SN_PIPE", "ท่อน้ำดี-น้ำเสียในอาคาร", "SN", "Sleeve:10|ท่อน้ำเสีย:45|ท่อน้ำดี:35|ทดสอบแรงดัน:10"),
    ("PLASTER_IN", "ฉาบผนังภายใน", "ARCH", "ตั้งเซี้ยม/ทำมุม:20|ฉาบ:80"),
    ("TILE_WALL", "ผนังห้องน้ำ กันซึม + กระเบื้อง", "ARCH", "กันซึม:20|ฉาบหน้าลาย:30|ปูกระเบื้อง:50"),
    ("FLOOR_TILE", "พื้นภายใน (กระเบื้อง/ปรับระดับ)", "ARCH", "ปรับระดับ/กันซึม:40|ปูกระเบื้อง/ผิว:50|บัว/ยาแนว:10"),
    ("BALC_TILE", "พื้นระเบียง กันซึม + กระเบื้อง", "ARCH", "กันซึม:40|ปูกระเบื้อง:60"),
    ("FLOOR_FIN", "พื้นผิวขัด (ลานจอด/ใต้หลังคา)", "ARCH", "ทำผิว:100"),
    ("EE_WIRE", "ร้อยสายไฟ", "EE", "ร้อยสาย:80|ทดสอบฉนวน:20"),
    ("CEIL", "ฝ้าเพดาน", "ARCH", "โครงเคร่า:50|ปิดแผ่น:40|ฉาบรอยต่อ:10"),
    ("PAINT_IN", "ทาสีผนังภายใน", "ARCH", "รองพื้น:40|ทับหน้า:60"),
    ("PAINT_CEIL", "ทาสีฝ้าเพดาน", "ARCH", "รองพื้น:40|ทับหน้า:60"),
    ("DOOR_WIN", "ประตู-หน้าต่าง", "ARCH", "วงกบ:40|บาน/กระจก:50|อุปกรณ์:10"),
    ("RAIL", "ราวระเบียงเหล็ก", "ARCH", "ติดตั้ง:80|ทาสี:20"),
    ("SANITARY", "สุขภัณฑ์ + เคาน์เตอร์", "ARCH", "เคาน์เตอร์/ช่องสบู่:30|สุขภัณฑ์:50|อุปกรณ์:20"),
    ("SN_FIX", "Floor drain / Clean out", "SN", "ติดตั้ง:100"),
    ("EE_FIX", "ดวงโคม สวิตช์ เต้ารับ ตู้ CU", "EE", "ตู้ CU:30|ดวงโคม:40|สวิตช์/เต้ารับ:30"),
    ("STAIR_FIN", "ผิวบันได + ราวบันได", "ARCH", "ผิวลูกนอน/ลูกตั้ง:60|ราวบันได:40"),
    ("PLASTER_EX", "ฉาบผนังภายนอก + บัว + เมทัลชีทผนัง", "ARCH", "ฉาบ:80|บัว/ตกแต่ง:20"),
    ("PAINT_EX", "ทาสีภายนอก", "ARCH", "รองพื้น:40|ทับหน้า:60"),
    ("EE_MDB", "ตู้ MDB + สายป้อน + รางเคเบิล", "EE", "ตั้งตู้:40|สายป้อน:50|ทดสอบ:10"),
    ("EE_LP", "ตู้ LP + มิเตอร์", "EE", "ติดตั้ง:80|ทดสอบ:20"),
    ("EE_LIGHTNING", "ระบบป้องกันฟ้าผ่า", "EE", "ติดตั้ง:80|ทดสอบ:20"),
    ("SN_TANK", "ถังเก็บน้ำ + ปั๊ม + วาล์ว (ชั้น 7)", "SN", "ตั้งถัง/ปั๊ม:60|ต่อท่อ/วาล์ว:30|ทดสอบ:10"),
    ("SN_MAIN", "ท่อเมนประปา + ปั๊มส่งน้ำ (ชั้น 1)", "SN", "วางท่อเมน:60|ปั๊ม/ถัง:30|ทดสอบ:10"),
    ("SN_EXT", "ถังบำบัด + ระบายน้ำรอบอาคาร", "SN", "ขุด/วางท่อ:50|บ่อพัก/ถังบำบัด:40|ถมคืน:10"),
    ("ROAD", "ถนน + ลานจอดรถ", "STR", "เตรียมพื้นทาง:20|เหล็ก/ไวร์เมช:30|เทคอนกรีต:40|ยาแนวรอยต่อ:10"),
]
task_rows = [{"task_id": t, "name": n, "trade": tr, "steps": s} for t, n, tr, s in tasks]

# ───────────────────────── ผูก BOQ → task + ตัวเลือกพื้นที่ (alloc)
FL27 = "floors=2-7"
RULES = {  # code (หรือ prefix ลงท้าย '*') → [(task, share, alloc)]
    # PRELIM
    "1.1": [("PRE_SETUP", 1, "locs=SITE")], "1.2": [("PRE_SETUP", 1, "locs=SITE")],
    "1.3": [("PRE_SETUP", 1, "locs=SITE")], "1.4": [("PRE_SETUP", 1, "locs=SITE")],
    "1.10": [("PRE_SETUP", 1, "locs=SITE")], "1.12": [("PRE_SETUP", 1, "locs=SITE")],
    "1.19": [("PRE_SETUP", 1, "locs=SITE")], "1.20": [("PRE_SETUP", 1, "locs=SITE")],
    "1.*": [("PRE_TIME", 1, "locs=SITE")],
    # STR
    "2.1.5": [("STR_SLAB", 1, "locs=F1")], "2.1.7": [("STR_SLAB", 1, "locs=F1")], "2.1.9": [("STR_SLAB", 1, "locs=F1")],
    "2.1.*": [("FDN", 1, "locs=FDN")],
    "2.2.1": [("PILE", 1, "locs=FDN")], "2.2.2": [("PILE", 1, "locs=FDN")], "2.2.5": [("PILE", 1, "locs=FDN")],
    "2.2.6": [("FDN", 1, "locs=FDN")],
    "2.2.7": [("STR_COL", 1, "kinds=floor;floors=1-7")], "2.2.8": [("STR_COL", 1, "kinds=floor;floors=1-7")],
    "2.2.9": [("STR_SLAB", 1, "kinds=floor;floors=1-7")],
    "2.2.10": [("STR_SLAB", 1, "kinds=floor;floors=2-7")], "2.2.11": [("STR_SLAB", 1, "kinds=floor;floors=2-7")],
    "2.2.12": [("STR_SLAB", 1, "kinds=floor;floors=1-6")],
    "2.3.1": [("FDN", 1, "locs=FDN")],
    "2.3.2": [("STR_COL", 1, "kinds=floor;floors=1-7")], "2.3.3": [("STR_COL", 1, "kinds=floor;floors=1-7")],
    "2.3.4": [("STR_SLAB", 1, "kinds=floor;floors=1-7")], "2.3.5": [("STR_SLAB", 1, "kinds=floor;floors=2-7")],
    "2.3.7": [("STR_SLAB", 1, "kinds=floor;floors=1-6")],
    "2.3.8": [("STR_SLAB", 0.6, "kinds=floor;floors=1-7"), ("STR_COL", 0.4, "kinds=floor;floors=1-7")],
    "2.3.9": [("STR_SLAB", 0.6, "kinds=floor;floors=1-7"), ("STR_COL", 0.4, "kinds=floor;floors=1-7")],
    "2.4.24": [("STR_SLAB", 0.6, "kinds=floor;floors=1-7"), ("STR_COL", 0.4, "kinds=floor;floors=1-7")],
    "2.5.*": [("STR_SLAB", 1, "kinds=floor;floors=2-7")],
    "2.6.*": [("ROOF", 1, "locs=RF")],
    "2.7.*": [("ROAD", 1, "locs=SITE")],
    "2.8.2": [("FDN", 1, "locs=FDN")], "2.8.3": [("SN_EXT", 1, "locs=SITE")],
    # ARCH
    "3.1.*": [("WALL", 1, ENCL)],
    "3.2.1": [("FLOOR_FIN", 1, "locs=F1-PARK,F7-ATTIC")],
    "3.2.2": [("FLOOR_TILE", 1, "kinds=common,lift,service")],
    "3.2.3": [("FLOOR_TILE", 1, "kinds=room")], "3.2.4": [("FLOOR_TILE", 1, "kinds=room")],
    "3.2.6": [("FLOOR_TILE", 0.46, "kinds=room,wc"), ("BALC_TILE", 0.54, "kinds=room")],
    "3.2.8": [("FLOOR_TILE", 0.46, "kinds=room,wc"), ("BALC_TILE", 0.54, "kinds=room")],
    "3.2.7": [("FLOOR_FIN", 1, "locs=F7-ATTIC")], "3.2.9": [("FLOOR_FIN", 1, "locs=F1-LIFT")],
    "3.2.10": [("ROOF", 1, "locs=RF")], "3.2.15": [("ROAD", 1, "locs=SITE")],
    "3.2.*": [("FLOOR_TILE", 1, "kinds=room,common,wc,service,lift")],
    "3.3.1": [("PLASTER_EX", 1, "kinds=facade")], "3.3.7": [("PLASTER_EX", 1, "kinds=facade")],
    "3.3.8": [("PLASTER_EX", 1, "kinds=facade")],
    "3.3.3": [("TILE_WALL", 1, "kinds=room,wc")], "3.3.4": [("TILE_WALL", 1, "kinds=room,wc")],
    "3.3.10": [("TILE_WALL", 1, "kinds=room,wc")], "3.3.11": [("TILE_WALL", 1, "kinds=room,wc")],
    "3.3.*": [("PLASTER_IN", 1, ENCL)],
    "3.4.*": [("CEIL", 1, ENCL)],
    "3.5.24": [("PLASTER_IN", 1, ENCL)],
    "3.5.*": [("DOOR_WIN", 1, ENCL)],
    "3.6.*": [("SANITARY", 1, "kinds=room,wc")],
    "3.7.*": [("STAIR_FIN", 1, "kinds=stair")],
    "3.8.*": [("ROOF", 1, "locs=RF")],
    "3.9.1": [("PAINT_EX", 1, "kinds=facade")], "3.9.2": [("PAINT_IN", 1, ENCL)], "3.9.3": [("PAINT_CEIL", 1, ENCL)],
    "3.10.*": [("RAIL", 1, "kinds=room")],
    # EE
    "4.1.*": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.2.1": [("EE_MDB", 1, "locs=F1-ELEC")], "4.2.2": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.2.3": [("EE_MDB", 1, "locs=F1-ELEC")], "4.2.4": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.2.5": [("EE_MDB", 1, "locs=F1-ELEC")], "4.2.6": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.2.7": [("EE_MDB", 1, "locs=F1-ELEC")], "4.2.8": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.2.9": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.2.*": [("EE_LP", 1, "kinds=floor;floors=1-7;by=equal")],
    "4.3.18": [("EE_CONDUIT", 1, ENCL)],
    "4.3.*": [("EE_MDB", 1, "locs=F1-ELEC")],
    "4.11.*": [("EE_LIGHTNING", 1, "locs=RF")],
}
# EE 4.4 (ส่วนกลาง) และ 4.5/4.6 (ในห้อง) — แยกตามชนิดรายการ
EE_COMMON = "kinds=common,service,wc,stair,lift,attic,parking"


def ee_room_task(desc):
    d = desc.lower()
    if "conduit" in d or "wire way" in d or "ท่อร้อย" in d:
        return "EE_CONDUIT"
    if "iec01" in d or "rg 6" in d or "สายไฟ" in d or "cabel" in d:
        return "EE_WIRE"
    return "EE_FIX"


# SN
SN_RULES = {
    "5.1.6": "SN_MAIN", "5.1.7": "SN_MAIN", "5.1.8": "SN_MAIN", "5.1.9": "SN_MAIN",
    "5.1.10": "SN_TANK", "5.1.11": "SN_TANK", "5.1.15": "SN_TANK", "5.1.16": "SN_TANK", "5.1.17": "SN_TANK",
    "5.1.18": "SN_TANK", "5.1.20": "SN_TANK", "5.1.21": "SN_TANK", "5.1.22": "SN_TANK",
    "5.2.9": "SN_FIX", "5.2.10": "SN_FIX", "5.2.13": "SN_FIX", "5.2.14": "SN_FIX", "5.2.15": "SN_FIX", "5.2.16": "SN_FIX",
    "5.2.11": "SN_TANK", "5.2.17": "SN_TANK", "5.2.18": "SN_TANK", "5.2.19": "SN_TANK", "5.2.20": "SN_TANK",
    "5.3.1": "SN_MAIN", "5.3.2": "SN_MAIN", "5.3.5": "SN_MAIN", "5.3.3": "SN_TANK", "5.3.4": "SN_TANK",
    "5.3.6": "SN_EXT",
}
SN_ALLOC = {"SN_MAIN": "locs=F1", "SN_TANK": "locs=F7-ATTIC", "SN_EXT": "locs=SITE",
            "SN_FIX": "kinds=room,wc,common,lift", "SN_PIPE": "kinds=room,wc,common,service,lift,attic"}


def rule_for(r):
    code, trade = r["code"], r["trade"]
    if trade == "EE" and (code.startswith("4.5.") or code.startswith("4.6.")):
        t = ee_room_task(r["description"])
        return [(t, 1, "kinds=room;rtype=" + ("A" if code.startswith("4.5.") else "B"))]
    if trade == "EE" and code.startswith("4.4."):
        return [(ee_room_task(r["description"]), 1, EE_COMMON)]
    if trade == "SN":
        if code.startswith("5.4."):
            return [("SN_EXT", 1, "locs=SITE")]
        t = SN_RULES.get(code, "SN_PIPE")
        return [(t, 1, SN_ALLOC[t])]
    if code.startswith("2.4.") and code != "2.4.24":  # เหล็กเสริม แยกตามกลุ่มย่อยใน BOQ
        g = r["group"]
        if "ฐานราก" in g:
            return [("FDN", 1, "locs=FDN")]
        if "เสา" in g or "ผนัง" in g:
            return [("STR_COL", 1, "kinds=floor;floors=1-7")]
        if "คาน" in g:
            return [("STR_SLAB", 1, "kinds=floor;floors=1-7")]
        if "พื้น" in g:
            return [("STR_SLAB", 1, "kinds=floor;floors=2-7")]
        if "บันได" in g:
            return [("STR_SLAB", 1, "kinds=floor;floors=1-6")]
    if code in RULES:
        return RULES[code]
    parts = code.split(".")
    for k in range(len(parts) - 1, 0, -1):
        key = ".".join(parts[:k]) + ".*"
        if key in RULES:
            return RULES[key]
    return None


boq_out, unmapped = [], []
with open(os.path.join(HERE, "boq_raw.csv"), encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        base = {k: r[k] for k in ("code", "boq_ref", "trade", "section", "section_name", "group", "description",
                                  "qty", "unit", "mat", "lab", "amount", "scope", "note", "src")}
        if r["scope"] != "in":
            boq_out.append({**base, "task_id": "", "share": "", "alloc": ""})
            continue
        rule = rule_for(r)
        if not rule:
            unmapped.append(r["code"])
            boq_out.append({**base, "task_id": "", "share": "", "alloc": ""})
            continue
        for t, share, alloc in rule:
            boq_out.append({**base, "task_id": t, "share": share, "alloc": alloc})

# ───────────────────────── activities (Gantt) — task × ชั้น
acts = []


FIN_SCALE = 1.2  # ปรับระยะงานสถาปัตย์/ระบบให้แผนจบก่อนวันสัญญาเล็กน้อย


def A(id_, task, floors, dur, preds="", name=None):
    if task not in ("PRE_SETUP", "PRE_TIME", "PILE", "FDN", "STR_SLAB", "STR_COL", "ROOF"):
        dur = int(round(dur * FIN_SCALE))
    acts.append({"act_id": id_, "task_id": task, "floors": floors, "duration": dur, "preds": preds,
                 "name": name or ""})


A("PRE1", "PRE_SETUP", "SITE", 12)
A("PRE2", "PRE_TIME", "SITE", 0, "", "ค่าดำเนินการตามเวลา (ตลอดโครงการ)")
A("PILE", "PILE", "FDN", 14, "PRE1SS+6")
A("FDN", "FDN", "FDN", 22, "PILEFS-6")
A("SLAB1", "STR_SLAB", "1", 10, "FDNFS-4", "คานคอดิน + บันได ชั้น 1")
A("COL1", "STR_COL", "1", 7, "SLAB1FS")
for f in range(2, 8):
    A(f"SLAB{f}", "STR_SLAB", str(f), 14, f"COL{f-1}FS", f"พื้น PT + คาน ชั้น {f}")
    A(f"COL{f}", "STR_COL", str(f), 7, f"SLAB{f}FS", "เสา + ผนังลิฟต์ ชั้น 7–หลังคา" if f == 7 else None)
A("ROOF", "ROOF", "RF", 18, "COL7FS")
for f in range(1, 8):
    p = [f"SLAB{min(f + 1, 7)}FS+3"] if f < 7 else ["ROOFSS+5"]
    if f > 1:
        p.append(f"WALL{f-1}FS-5")
    A(f"WALL{f}", "WALL", str(f), 7 if f in (1, 7) else 13, ";".join(p))
    A(f"EMB{f}", "EE_CONDUIT", str(f), 8 if f in (1, 7) else 12, f"WALL{f}SS+4")
    A(f"PIPE{f}", "SN_PIPE", str(f), 8 if f in (1, 7) else 12, f"WALL{f}SS+4" if f > 1 else "SLAB1SS+2")
    A(f"PLI{f}", "PLASTER_IN", str(f), 8 if f in (1, 7) else 14,
      f"EMB{f}FS;PIPE{f}FS" + (f";PLI{f-1}FS-6" if f > 1 else ""))
    A(f"TW{f}", "TILE_WALL", str(f), 5 if f in (1, 7) else 10, f"PLI{f}SS+6")
    A(f"FT{f}", "FLOOR_TILE", str(f), 6 if f in (1, 7) else 10, f"TW{f}FS-3")
    A(f"WIRE{f}", "EE_WIRE", str(f), 5 if f in (1, 7) else 8, f"PLI{f}FS")
    A(f"CEIL{f}", "CEIL", str(f), 6 if f in (1, 7) else 10, f"WIRE{f}SS+3")
    A(f"PNT{f}", "PAINT_IN", str(f), 6 if f in (1, 7) else 9, f"CEIL{f}FS;FT{f}FS-3")
    A(f"PNC{f}", "PAINT_CEIL", str(f), 4 if f in (1, 7) else 6, f"PNT{f}SS+3")
    A(f"DW{f}", "DOOR_WIN", str(f), 5 if f in (1, 7) else 9, f"FT{f}FS")
    A(f"SAN{f}", "SANITARY", str(f), 3 if f in (1, 7) else 6, f"PNT{f}FS-2")
    A(f"FIXS{f}", "SN_FIX", str(f), 3 if f in (1, 7) else 5, f"SAN{f}SS")
    A(f"FIXE{f}", "EE_FIX", str(f), 3 if f in (1, 7) else 6, f"PNC{f}FS")
    A(f"LP{f}", "EE_LP", str(f), 3, f"WIRE{f}FS")
for f in range(2, 7):
    A(f"BAL{f}", "BALC_TILE", str(f), 6, f"PLX{f}FS;FT{f}SS")
    A(f"RAIL{f}", "RAIL", str(f), 4, f"BAL{f}FS")
A("FF1", "FLOOR_FIN", "1", 6, "ROADFS-10", "พื้นผิวขัด ลานจอดรถ")
A("FF7", "FLOOR_FIN", "7", 5, "ROOFFS")
# ภายนอก: ไล่จากบนลงล่าง
for f in range(7, 0, -1):
    A(f"PLX{f}", "PLASTER_EX", str(f), 8, f"WALL7FS" if f == 7 else f"PLX{f+1}FS-2")
for f in range(7, 0, -1):
    A(f"PEX{f}", "PAINT_EX", str(f), 5, f"PLX{f}FS+10" + ("" if f == 7 else f";PEX{f+1}FS-1"))
A("STAIR", "STAIR_FIN", "1,2,3,4,5,6,7", 20, "PLI7FS")
A("MDB", "EE_MDB", "1", 30, "EMB4FS")
A("LPS", "EE_LIGHTNING", "RF", 8, "ROOFFS")
A("TANK", "SN_TANK", "7", 20, "ROOFFS")
A("WMAIN", "SN_MAIN", "1", 18, "PIPE3FS")
A("SNEXT", "SN_EXT", "SITE", 24, "PLX1FS-5")
A("ROAD", "ROAD", "SITE", 26, "SNEXTSS+10")

# ───────────────────────── milestones (ตาราง Copy of payment)
CV = project["contract_value_ex_vat"]
M = [
    ("1.1", 0.05, "งานรั้วชั่วคราว งานออฟฟิศชั่วคราว งานเตรียมการแล้วเสร็จ 90%", "PRE_SETUP @ SITE >= 90"),
    ("1.2", 0.07, "งานเสาเข็มอาคารหลัก / ขุดหลุมฐานรากและตัดหัวเสาเข็ม / ฐานราก แล้วเสร็จ 90%",
     "PILE @ FDN >= 90 ; FDN @ FDN >= 90"),
    ("2", 0.04, "โครงสร้าง คาน เสาชั้นที่ 1 / ผนังลิฟต์ชั้น 1-2 / Sleeve + ท่อน้ำเสียภายในอาคาร แล้วเสร็จ 90%",
     "STR_SLAB @ 1 >= 90 ; STR_COL @ 1 >= 90 ; SN_PIPE @ 1 >= 90"),
    ("3", 0.08, "โครงสร้างพื้นชั้น 2-3 / เสา-ผนังลิฟต์ชั้น 2-4 แล้วเสร็จ 90%",
     "STR_SLAB @ 2-3 >= 90 ; STR_COL @ 2-3 >= 90"),
    ("4", 0.08, "โครงสร้างพื้นชั้น 4-5 / เสา-ผนังลิฟต์ชั้น 4-6 แล้วเสร็จ 90%",
     "STR_SLAB @ 4-5 >= 90 ; STR_COL @ 4-5 >= 90"),
    ("5", 0.06, "โครงสร้างพื้นชั้น 6-7 / เสา-ผนังลิฟต์ชั้น 6-ดาดฟ้า แล้วเสร็จ 90%",
     "STR_SLAB @ 6-7 >= 90 ; STR_COL @ 6-7 >= 90"),
    ("6", 0.06, "หลังคาคลุมลิฟต์และหลังคาชั้นดาดฟ้า / ผนังก่ออิฐชั้น 1-2 + คาน-เสาเอ็นทับหลัง / ท่อน้ำ-ไฟฟ้าฝังผนัง แล้วเสร็จ 90%",
     "ROOF @ RF >= 90 ; WALL @ 1-2 >= 90 ; EE_CONDUIT @ 1-2 >= 90 ; SN_PIPE @ 2 >= 90"),
    ("7", 0.05, "ผนังก่ออิฐชั้น 3-5 + คาน-เสาเอ็นทับหลัง / ท่อน้ำ-ไฟฟ้าฝังผนัง แล้วเสร็จ 90%",
     "WALL @ 3-5 >= 90 ; EE_CONDUIT @ 3-5 >= 90 ; SN_PIPE @ 3-5 >= 90"),
    ("8", 0.05, "ผนังก่ออิฐชั้น 6-7 + คาน-เสาเอ็นทับหลัง / ท่อน้ำ-ไฟฟ้าฝังผนัง แล้วเสร็จ 90%",
     "WALL @ 6-7 >= 90 ; EE_CONDUIT @ 6-7 >= 90 ; SN_PIPE @ 6-7 >= 90"),
    ("9", 0.05, "ฉาบผนังภายในชั้น 1-3 / ปูกระเบื้องพื้นชั้น 1-3 / ทดสอบท่อน้ำดี-น้ำเสีย / ร้อยสายไฟชั้น 1-3 แล้วเสร็จ 90%",
     "PLASTER_IN @ 1-3 >= 90 ; FLOOR_TILE @ 1-3 >= 90 ; SN_PIPE @ 1-7 >= 90 ; EE_WIRE @ 1-3 >= 90"),
    ("10", 0.08, "ฉาบผนังภายในชั้น 4-7 / กระเบื้องพื้นชั้น 4-5 / ร้อยสายไฟชั้น 4-5 / ฝ้าเพดานชั้น 1-3 / ทาสีผนังภายในชั้น 1-3 แล้วเสร็จ 90%",
     "PLASTER_IN @ 4-7 >= 90 ; FLOOR_TILE @ 4-5 >= 90 ; EE_WIRE @ 4-5 >= 90 ; CEIL @ 1-3 >= 90 ; PAINT_IN @ 1-3 >= 90"),
    ("11", 0.10, "ฉาบผนังภายนอก / กระเบื้องพื้นชั้น 6-7 / ร้อยสายไฟชั้น 6-7 / ฝ้าเพดานชั้น 4-5 / ทาสีผนังภายในชั้น 4-7 / ทาสีฝ้าชั้น 1-3 แล้วเสร็จ 90%",
     "PLASTER_EX @ 1-7 >= 90 ; FLOOR_TILE @ 6-7 >= 90 ; EE_WIRE @ 6-7 >= 90 ; CEIL @ 4-5 >= 90 ; PAINT_IN @ 4-7 >= 90 ; PAINT_CEIL @ 1-3 >= 90"),
    ("12", 0.06, "ฝ้าเพดานชั้น 6-7 / ประตูหน้าต่างชั้น 1-4 / ราวระเบียงเหล็ก / ทาสีฝ้าชั้น 4-7 / กระเบื้องพื้นระเบียงชั้น 4-7 แล้วเสร็จ 90%",
     "CEIL @ 6-7 >= 90 ; DOOR_WIN @ 1-4 >= 90 ; RAIL @ 1-7 >= 90 ; PAINT_CEIL @ 4-7 >= 90 ; BALC_TILE @ 4-7 >= 90"),
    ("13", 0.05, "ทาสีภายนอก / ติดตั้งดวงโคม / ระบบน้ำดีชั้น 7 / ประตูหน้าต่างชั้น 5-7 / กระเบื้องระเบียงชั้น 1-3 / ตู้ MDB / ตู้ LP + มิเตอร์ชั้น 1-3 แล้วเสร็จ 90%",
     "PAINT_EX @ 1-7 >= 90 ; EE_FIX @ 1-7 >= 90 ; SN_TANK @ 7 >= 90 ; DOOR_WIN @ 5-7 >= 90 ; BALC_TILE @ 1-3 >= 90 ; EE_MDB @ 1 >= 90 ; EE_LP @ 1-3 >= 90"),
    ("14", 0.07, "พื้นชั้น 1 (ถนน) / ภายนอกอาคาร / ถนนที่จอดรถ / ระบบน้ำดีชั้น 1 / ถังบำบัด + ระบายน้ำรอบอาคาร / ตู้ LP + มิเตอร์ชั้น 4-7 แล้วเสร็จ 90%",
     "ROAD @ SITE >= 90 ; SN_MAIN @ 1 >= 90 ; SN_EXT @ SITE >= 90 ; EE_LP @ 4-7 >= 90"),
    ("15", 0.05, "Commissioning test / ทำความสะอาด / และอื่นๆ", "ALL >= 100"),
]
ms = [{"no": n, "pct": p, "amount": round(CV * p, 2), "description": d, "conditions": c, "version": "Copy of payment",
       "status": "planned", "submitted": "", "approved": "", "paid": ""} for n, p, d, c in M]

# ───────────────────────── เขียนไฟล์
project["source_issues"] = [
    "BOQ ชีต PRELIM/EE/SN/FP แถว 28: คำอธิบายถูกเขียนทับด้วยข้อความเดียวกัน 'ไฟฟ้าOwnerมีทีมดำเนินการเองเราเริ่มที่ตู้' (น่าจะพิมพ์ตอน group ชีต) — ตัวเลขไม่เสีย",
    "BOQ หน้า SUMMARY: ช่องค่าวัสดุ/ค่าแรงของหมวด EE รวมราคาต่อห้องของ 4.5/4.6 แทนจำนวนเงิน (ขาด 1,162,633.20) — ยอดรวม 3,483,617.50 ถูกต้อง",
    "BOQ ARCH 3.5: บรรทัด 'รวมหมวดงานประตู-หน้าต่าง' = 2,161,750 แต่หน้าสรุปใช้ 2,483,550 (รวมค่าแรงติดตั้งประตูที่ผู้ว่าจ้างจัดหา 321,800) — ใช้ตามหน้าสรุป",
    "BOQ STR หมวด 2.8 หัวข้อในรายละเอียดเขียน 'งานระบบกันซึม' แต่หน้าสรุปเขียน 'งานอื่น ๆ'",
    "BOQ มีเลขข้อซ้ำ (STR 2.2.10 สองครั้ง) และเลขข้อเป็นทศนิยมเพี้ยน — ระบบใช้รหัสใหม่ตามลำดับ (เก็บเลขเดิมใน boq_ref)",
    "ตารางงวด 2 ฉบับ (payment / Copy of payment) งวด 9–13 ต่างกัน — ใช้ Copy of payment ตามที่ผู้ใช้เลือก",
]
old = os.path.join(PROJ, "project.json")
if os.path.exists(old):  # เก็บค่าที่ผู้ใช้ตั้งในโปรแกรม (เช่น Baseline ที่ใช้อยู่)
    with open(old, encoding="utf-8") as fh:
        prev = json.load(fh)
    for k in ("active_baseline", "contract_no", "owner_address", "contractor_address", "contractor_tax_id",
              "ld_per_day", "ld_cap_pct"):
        if k in prev:
            project[k] = prev[k]
with open(old, "w", encoding="utf-8") as fh:
    json.dump(project, fh, ensure_ascii=False, indent=2)
write_csv("locations.csv", locs)
write_csv("tasks.csv", task_rows)
write_csv("boq.csv", boq_out)
write_csv("activities.csv", acts)
write_csv("milestones.csv", ms)
print(f"locations {len(locs)}  tasks {len(task_rows)}  boq rows {len(boq_out)}  activities {len(acts)}  milestones {len(ms)}")
if unmapped:
    print("ยังไม่ผูก task:", unmapped)
    sys.exit(1)
