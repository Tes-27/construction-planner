# รับโครงการใหม่ (สำหรับ Claude)

ผู้ใช้จะส่ง assets ของโครงการมา (BOQ, แบบ PDF, ตารางงวดเงิน, สัญญา/ระยะเวลา) — รูปแบบไม่แน่นอน
หน้าที่: แปลงเป็นไฟล์รูปแบบกลางใน `projects/<ชื่อ>/` **โดยไม่แก้โค้ดใน app/** ดูตัวอย่างครบที่ `projects/machi/ingest/`

## ขั้นตอน
1. `projects/<ชื่อ>/source/` ← คัดลอกไฟล์ต้นฉบับ (อ่านอย่างเดียว) · Python ใช้ของ `.venv` (`.venv\Scripts\python.exe` บน Windows, `.venv/bin/python` บน Mac — start.bat สร้างให้)
2. **BOQ → `ingest/boq_raw.csv`** (เขียน parser เฉพาะโครงการ เช่น `parse_boq.py`)
   - เลขข้อให้สร้างใหม่ตามลำดับ (`code`) เก็บเลขเดิมใน `boq_ref` — Excel มักเก็บเลขข้อเป็น float เพี้ยน
   - ตรวจผลรวมทุกระดับเทียบหน้าสรุป ถ้ารายละเอียดเป็น "ต่อหน่วย" (เช่น ต่อห้อง) ให้คูณ
   - ข้อความในช่องตัวเลข (Excluded / ไม่รวม / By Owner) → `scope` = excluded / owner / zero; ถ้ามีค่าแรงจริงให้คงไว้เป็น `in`
3. **ดูแบบ** (render ด้วย PyMuPDF: `fitz.open(pdf)[i].get_pixmap(dpi=40)` แล้วทำ contact sheet ด้วย Pillow) → ชั้น, ห้อง, ชื่อเฉพาะ, พื้นที่โดยประมาณ, แผ่นแบบของแต่ละชั้น
   - เลขห้องตามที่ผู้ใช้กำหนด (Machi: X = ชั้น เช่น 221–236) ห้องมีชื่อเฉพาะให้ใช้ชื่อนั้น
4. **`ingest/build_project.py`** สร้าง:
   - `project.json` — สัญญา, VAT/ประกัน/หัก ณ ที่จ่าย, วันเริ่ม-สิ้นสุด, ปฏิทิน, `assumptions`, `source_issues`
   - `locations.csv` — `loc_id, floor, kind, name, area, rtype` · kind: floor (ทั้งชั้น), room, common, service, wc, stair, lift, parking, attic, facade, roof, site
   - `tasks.csv` — `task_id, name, trade, steps` (`ชื่อ:น้ำหนัก|...` รวม 100 หรือ `auto-time`)
   - `boq.csv` — แถว BOQ + `task_id, share, alloc` (alloc: `locs=A,B` · `kinds=room,wc;floors=2-6;rtype=A;by=area|equal`)
   - `activities.csv` — `act_id, task_id, floors, duration (วันทำงาน), preds (ID+FS/SS/FF±lag; คั่น ;), name, start_on`
   - `milestones.csv` — `no, pct, amount, description, conditions (TASK @ ชั้น >= 90 ; ... | ALL >= 100), version, status, submitted, approved, paid`
5. **แบบแปลน** (`ingest/make_plans.py` ตามตัวอย่าง Machi): render หน้าแบบที่ 110 dpi (ฟังก์ชัน `render_page` ใน make_plans.py — PyMuPDF) → `plans/<แผ่น>.png`,
   เขียน `plans.json` {sheets: {id: {file,title,view}}, floor_sheet: {ชั้น: id}} และ `zones.json` เริ่มต้นจาก grid line
   (มาตราส่วน 1:100 บน A2 แสดง 2000 px → 1 ม. ≈ 33.7 px) · ตรวจด้วย `ingest/overlay.py` · แผ่นที่วางเหลื่อมให้วัดด้วย phase correlation
   · ทุก location ที่มีมูลค่าต้องมี slot ใน zones ของแผ่นของชั้นนั้น (ยกเว้น `EXT` ที่ใช้เส้นรอบอาคาร `*`)
6. รัน build แล้วตรวจด้วย `core.Project(...).validation()` ต้องไม่มี error: BOQ ผูกครบ, น้ำหนักรวม 100%, ทุก cell มีแท่ง Gantt, งวดรวม 100%
7. ปรับระยะเวลาให้แผนจบก่อนวันสัญญาเล็กน้อย → ล็อก Baseline แรก (`save_baseline('แผนตั้งต้นตามสัญญา')`)
8. เขียนสมมติฐานทุกข้อลง `assumptions` และปัญหาในไฟล์ต้นฉบับลง `source_issues` — แสดงในหน้าภาพรวมให้ผู้ใช้ยืนยัน

## เมื่อมี VO / แบบเปลี่ยน
แก้ parser/build ของโครงการแล้วรันใหม่ — `project.json` จะเก็บ `active_baseline` ไว้, `progress.csv` ไม่ถูกแตะ
ถ้าเปลี่ยน `loc_id` หรือ `task_id` ต้อง map ความคืบหน้าเดิมให้ด้วย
