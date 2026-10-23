"""ตรวจขอบเขตห้อง: วาด zones ทับแบบ แล้ว crop ตาม view"""
import json, os, sys
from PIL import Image, ImageDraw
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plans = json.load(open(os.path.join(P, "plans.json"), encoding="utf-8"))
zones = json.load(open(os.path.join(P, "zones.json"), encoding="utf-8"))
for sid in sys.argv[1:]:
    im = Image.open(os.path.join(P, "plans", plans["sheets"][sid]["file"])).convert("RGB")
    w, h = im.size
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    cols = [(230, 80, 60), (40, 120, 220), (30, 160, 90), (200, 140, 20), (150, 70, 200)]
    for i, (slot, polys) in enumerate(zones.get(sid, {}).items()):
        if slot == "*":
            for poly in polys: d.polygon([(x * w, y * h) for x, y in poly], outline=(0, 0, 0, 255), width=4)
            continue
        c = cols[i % len(cols)]
        for poly in polys:
            d.polygon([(x * w, y * h) for x, y in poly], fill=c + (70,), outline=c + (255,), width=3)
        x, y = polys[0][0]; d.text((x * w + 6, y * h + 6), slot, fill=(0, 0, 0, 255))
    out = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    v = plans["sheets"][sid]["view"]
    out = out.crop((int(v[0] * w), int(v[1] * h), int(v[2] * w), int(v[3] * h)))
    out.thumbnail((1600, 1600)); out.save(os.path.join(P, "ingest", "tmp", f"ov-{sid}.png"))
    print(sid, out.size)
