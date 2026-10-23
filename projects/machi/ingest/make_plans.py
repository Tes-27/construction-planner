"""แบบแปลน Machi → plans/*.png + plans.json + zones.json (ขอบเขตห้องเริ่มต้น)

พิกัดวัดจากแบบที่แสดงขนาด 2000×1415 (ทั้งแผ่น A2) แล้วเก็บเป็นสัดส่วน 0–1 · มาตราส่วน 1:100 → 1 ม. ≈ 33.7 px
แก้ไขต่อได้ในโปรแกรม (แท็บแบบแปลน → แก้ขอบเขต) — สคริปต์นี้จะไม่ทับ zones.json ที่มีอยู่ เว้นแต่ใส่ --force
"""
import json, os, shutil, subprocess, sys

for _s in (sys.stdout, sys.stderr):  # Windows: คอนโซลอาจเป็น cp874 → พิมพ์ภาษาไทย/สัญลักษณ์ไม่พัง
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
W, H = 2000.0, 1415.0
SHEETS = {  # id: (หน้าใน ARCH.pdf, ชื่อ, กรอบที่แสดง x0,y0,x1,y1 ในพิกัด 2000×1415)
    "A-P00": (6, "ผังบริเวณ", (130, 250, 1760, 1100)),
    "A-P01": (7, "แปลนพื้นชั้น 1", (30, 180, 1760, 1150)),
    "A-P02": (8, "แปลนพื้นชั้น 2", (150, 180, 1620, 1080)),
    "A-P03": (9, "แปลนพื้นชั้น 3–5", (150, 180, 1620, 1080)),
    "A-P04": (10, "แปลนพื้นชั้น 6", (150, 180, 1620, 1080)),
    "A-P05": (11, "แปลนพื้นห้องใต้หลังคา (ชั้น 7)", (180, 190, 1640, 1100)),
    "A-P06": (12, "แปลนหลังคา", (130, 190, 1640, 1100)),
}
FLOOR_SHEET = {"SITE": "A-P00", "FDN": "A-P00", "1": "A-P01", "2": "A-P02", "3": "A-P03", "4": "A-P03",
               "5": "A-P03", "6": "A-P04", "7": "A-P05", "RF": "A-P06"}


def R(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# ── ชั้นพักอาศัย (A-P02/03/04 ผังเดียวกัน) · grid x: 1=397 2=652 2A=697 2B=770 2C=797 3=907 4=1162 5=1419
#    y: ขอบระเบียงบน 420 · B=646 · ขอบล่างทางเดิน 696 · C=905 · ขอบระเบียงล่าง 982
X = [397, 524.5, 652, 779.5, 907, 1034.5, 1162, 1290.5, 1419]
TOP, B, CB, BOT = 420, 646, 696, 982
typ = {
    "*": [R(397, 420, 1419, 982)],
    "35": [R(X[0], TOP, X[1], B)], "33": [R(X[1], TOP, X[2], B)],
    "27": [R(X[4], TOP, X[5], B)], "25": [R(X[5], TOP, X[6], B)],
    "23": [R(X[6], TOP, X[7], B)], "21": [R(X[7], TOP, X[8], B)],
    "36": [R(X[0], CB, X[1], BOT)], "34": [R(X[1], CB, X[2], BOT)], "32": [R(X[2], CB, X[3], BOT)],
    "30": [R(X[3], CB, X[4], BOT)], "28": [R(X[4], CB, X[5], BOT)], "26": [R(X[5], CB, X[6], BOT)],
    "24": [R(X[6], CB, X[7], BOT)], "22": [R(X[7], CB, X[8], BOT)],
    "ST1": [R(652, TOP, 790, 540)],
    "LIFT": [R(652, 540, 775, B)],
    "PREP": [R(850, 540, 907, B)],
    "ELEC": [R(652, B, 722, CB)],
    "CORR": [R(397, B, 652, CB), R(722, B, 1419, CB), R(775, 540, 850, B), R(790, TOP, 907, 540)],
    "ST2": [R(1419, 545, 1492, 700)],
}
# ── ชั้น 1 · grid x: 1=366 2=622 3=877 4=1133 5=1389 · y: แนวอาคารบน 470 · B=640 · C=905 · ขอบที่จอดล่าง 1065
f1 = {
    "*": [R(366, 425, 1389, 1065)],
    "PARK": [R(366, 470, 622, 905), R(877, 470, 1389, 905), R(366, 905, 1389, 1065), R(622, 700, 877, 905)],
    "STORE": [R(622, 425, 735, 492)],
    "WC1": [R(735, 425, 830, 492)],
    "ST1": [R(675, 492, 830, 545)],
    "LIFT": [R(622, 545, 745, 640)],
    "ELEC": [R(560, 640, 622, 700)],
    "LOBBY": [R(622, 640, 770, 700)],
    "WALK": [R(770, 545, 877, 700)],
    "ST2": [R(1389, 590, 1462, 700)],
}
# ── ชั้น 7 ห้องใต้หลังคา · grid x: 1=428 2=684 2A=730 2B=805 2C=832 3=940 4=1196 5=1452 · y: 1a=445 B=668 ขอบล่าง 1000
f7 = {
    "*": [R(428, 445, 1452, 1000)],
    "ATTIC": [R(428, 445, 684, 1000), R(684, 668, 1452, 1000), R(940, 445, 1452, 540), R(1381, 540, 1452, 668),
              R(940, 660, 1381, 668)],
    "STORE1": [R(945, 540, 1030, 660)], "STORE2": [R(1033, 540, 1118, 660)], "STORE3": [R(1120, 540, 1205, 660)],
    "STORE4": [R(1208, 540, 1293, 660)], "STORE5": [R(1296, 540, 1381, 660)],
    "STORE6": [R(838, 445, 885, 600)],
    "STORE7": [R(684, 668, 760, 720)],
    "WC3": [R(885, 600, 940, 700)],
    "ST1": [R(730, 445, 830, 560)],
    "LIFT": [R(684, 560, 838, 668)],
}
# ── ผังบริเวณ (A-P00): ฐานราก = รอยอาคาร, SITE = ทั้งแปลง · grid 1≈467 5≈1287 · A≈470 C≈930
site = {"*": [R(467, 467, 1287, 968)], "SITE": [[[205, 395], [1690, 385], [1690, 1015], [205, 1035]]]}
# ── หลังคา (A-P06)
roof = {"RF": [R(434, 454, 1459, 1021)]}


def shift(z, dx, dy):
    """แบบบางแผ่นวางตำแหน่งเหลื่อมกัน — วัดด้วย phase correlation เทียบ A-P03"""
    return {k: [[[x + dx, y + dy] for x, y in poly] for poly in polys] for k, polys in z.items()}


ZONES = {"A-P00": site, "A-P01": f1, "A-P02": shift(typ, 19.4, -14.0), "A-P03": typ,
         "A-P04": shift(typ, 18.7, 21.8), "A-P05": f7, "A-P06": roof}


def norm(z):
    return {k: [[[round(x / W, 5), round(y / H, 5)] for x, y in poly] for poly in polys] for k, polys in z.items()}


def render_page(pdf, page, png, dpi=110):
    """แปลงหน้า PDF → PNG · ใช้ PyMuPDF (pip, ใช้ได้ทุกระบบ) ถ้าไม่มีค่อยใช้ pdftoppm"""
    try:
        import fitz  # PyMuPDF
        with fitz.open(pdf) as doc:
            doc[page - 1].get_pixmap(dpi=dpi).save(png)
        return
    except ImportError:
        pass
    if not shutil.which("pdftoppm"):
        sys.exit("ต้องติดตั้ง pymupdf (pip install pymupdf) หรือ poppler (pdftoppm)")
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", "-f", str(page), "-l", str(page), pdf, png[:-4]],
                   check=True)


def main(force=False):
    out = os.path.join(PROJ, "plans")
    os.makedirs(out, exist_ok=True)
    sheets = {}
    for sid, (page, title, view) in SHEETS.items():
        png = os.path.join(out, sid + ".png")
        if not os.path.exists(png) or "--render" in sys.argv:
            render_page(os.path.join(PROJ, "source", "ARCH.pdf"), page, png)
        sheets[sid] = {"file": sid + ".png", "title": title, "source": f"ARCH.pdf หน้า {page}",
                       "view": [round(view[0] / W, 4), round(view[1] / H, 4), round(view[2] / W, 4), round(view[3] / H, 4)]}
    with open(os.path.join(PROJ, "plans.json"), "w", encoding="utf-8") as fh:
        json.dump({"sheets": sheets, "floor_sheet": FLOOR_SHEET}, fh, ensure_ascii=False, indent=1)
    zpath = os.path.join(PROJ, "zones.json")
    if os.path.exists(zpath) and not force:
        print("zones.json มีอยู่แล้ว — ไม่ทับ (ใช้ --force)")
    else:
        with open(zpath, "w", encoding="utf-8") as fh:
            json.dump({sid: norm(z) for sid, z in ZONES.items()}, fh, ensure_ascii=False, indent=1)
        print("เขียน zones.json")
    print("sheets:", ", ".join(sheets))


if __name__ == "__main__":
    main("--force" in sys.argv)
