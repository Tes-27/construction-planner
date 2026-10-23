"""ชุดทดสอบ Construction Planner — รัน:  python -m unittest discover -s tests -v
(Windows: .venv\\Scripts\\python.exe -m unittest discover -s tests -v)

ทดสอบที่แก้ไฟล์จะทำบนสำเนาในโฟลเดอร์ชั่วคราว — ไม่แตะ projects/ จริง
ค่าที่คาดหวังหลายค่ายืนยันกับเอกสารต้นฉบับแล้ว (เช่น ตารางงวด Copy of payment) — ถ้า test พัง ให้หาสาเหตุ อย่าแก้ค่าคาดหวังทิ้ง
"""
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import billing  # noqa: E402
import core  # noqa: E402

PROJ = os.path.join(ROOT, "projects")
D = dt.date


def copy_project(name):
    tmp = tempfile.mkdtemp(prefix="cp-test-")
    dst = os.path.join(tmp, name)
    shutil.copytree(os.path.join(PROJ, name), dst, ignore=shutil.ignore_patterns("source", "tmp", "photos"))
    return tmp, dst


class TestData(unittest.TestCase):
    """ข้อมูลกลางของทั้งสองโครงการต้องผ่านการตรวจ และตัวเลขต้องตรงกับ BOQ/สัญญา"""

    @classmethod
    def setUpClass(cls):
        cls.p = core.Project(os.path.join(PROJ, "machi"))
        cls.demo = core.Project(os.path.join(PROJ, "machi-demo"))

    def test_validation_has_no_errors(self):
        for p in (self.p, self.demo):
            bad = [v for v in p.validation() if v[0] == "error"]
            self.assertEqual(bad, [], p.folder)

    def test_boq_total_and_contract_factor(self):
        self.assertAlmostEqual(self.p.in_scope, 40215020.00, places=2)
        self.assertAlmostEqual(self.p.total_value, 40215020.00, places=2)
        self.assertAlmostEqual(self.p.total_value * self.p.k_contract, 42056074.77, places=2)

    def test_locations_and_rooms(self):
        rooms = [l for l in self.p.locations if l["kind"] == "room"]
        self.assertEqual(len(rooms), 70)
        self.assertEqual(sorted(l["name"] for l in rooms if l["floor"] == "2")[:3], ["221", "222", "223"])
        self.assertNotIn("229", {l["name"] for l in rooms})  # ไม่มีเลข X29 / X31 ตามแบบ
        self.assertEqual(sum(1 for l in rooms if l["rtype"] == "B"), 5)

    def test_milestone_money_matches_payment_sheet(self):
        """ยืนยันกับชีต Copy of payment ทุกบรรทัด — งวด = % × 45,000,000 ÷ 1.07 ไม่ปัดระหว่างทาง"""
        expected = {  # งวด: (มูลค่า, (7) สุทธิ)
            "1.1": (2102803.74, 2081775.70), "1.2": (2943925.23, 2914485.98), "2": (1682242.99, 1665420.56),
            "3": (3364485.98, 3330841.12), "4": (3364485.98, 3330841.12), "5": (2523364.49, 2498130.84),
            "6": (2523364.49, 2498130.84), "7": (2102803.74, 2081775.70), "8": (2102803.74, 2081775.70),
            "9": (2102803.74, 2081775.70), "10": (3364485.98, 3330841.12), "11": (4205607.48, 4163551.40),
            "12": (2523364.49, 2498130.84), "13": (2102803.74, 2081775.70), "14": (2943925.23, 2914485.98),
            "15": (2102803.74, 2081775.70),
        }
        got = {m["no"]: m for m in self.p.milestones}
        self.assertEqual(set(got), set(expected))
        for no, (amount, net) in expected.items():
            mm = self.p.money(float(got[no]["amount"]), float(got[no]["pct"]))
            self.assertAlmostEqual(mm["amount"], amount, places=2, msg=no)
            self.assertAlmostEqual(mm["net"], net, places=2, msg=no)

    def test_every_valued_location_has_a_zone(self):
        for p in (self.p, self.demo):
            for l in p.locations:
                if not p.loc_value.get(l["loc_id"]) or p.slot(l) == "EXT":
                    continue
                sheet = p.plans["floor_sheet"].get(l["floor"])
                self.assertIn(p.slot(l), p.zones.get(sheet, {}), f"{l['loc_id']} บน {sheet}")


class TestSchedule(unittest.TestCase):
    def setUp(self):
        self.p = core.Project(os.path.join(PROJ, "machi"))

    def test_plan_finishes_before_contract(self):
        _, end = self.p.schedule()
        self.assertEqual(self.p.cal.date(end), D(2026, 9, 24))
        self.assertLess(self.p.cal.date(end), D(2026, 10, 5))

    def test_status_at_start_equals_plan(self):
        _, e0 = self.p.schedule()
        _, e1 = self.p.schedule(status=D(2025, 10, 6))
        self.assertEqual(e0, e1)

    def test_demo_forecast_reflects_delay(self):
        demo = core.Project(os.path.join(PROJ, "machi-demo"))
        _, end = demo.schedule(status=D(2026, 10, 22))
        self.assertGreater(demo.cal.date(end), D(2026, 10, 5))
        # 86.0% — ค่าดำเนินการตามเวลา (PRE_TIME) คิดเทียบวันเสร็จที่คาดการณ์ ไม่ใช่วันตามแผนเดิม
        self.assertAlmostEqual(100 * demo.earned(D(2026, 10, 17)) / demo.total_value, 86.0, delta=0.5)

    def test_cycle_is_rejected_and_not_saved(self):
        tmp, path = copy_project("machi")
        try:
            p = core.Project(path)
            with self.assertRaises(ValueError):
                p.update_activity("WALL3", {"preds": "PLI3FS"})
            self.assertEqual(core.Project(path).act["WALL3"]["preds"], "SLAB4FS+3;WALL2FS-5")
        finally:
            shutil.rmtree(tmp)


class TestBilling(unittest.TestCase):
    def test_bahttext(self):
        self.assertEqual(billing.bahttext(2081775.70), "สองล้านแปดหมื่นหนึ่งพันเจ็ดร้อยเจ็ดสิบห้าบาทเจ็ดสิบสตางค์")
        self.assertEqual(billing.bahttext(21.01), "ยี่สิบเอ็ดบาทหนึ่งสตางค์")
        self.assertEqual(billing.bahttext(1000011), "หนึ่งล้านสิบเอ็ดบาทถ้วน")
        self.assertEqual(billing.bahttext(45000000), "สี่สิบห้าล้านบาทถ้วน")

    def test_report_and_excel(self):
        demo = core.Project(os.path.join(PROJ, "machi-demo"))
        r = billing.report(demo, "10", D(2026, 9, 28))
        self.assertFalse(r["draft"])
        self.assertAlmostEqual(r["money"]["net"], 3330841.12, places=2)
        self.assertAlmostEqual(r["cum"]["amount"], 28177570.10, places=1)
        wb_bytes = billing.to_xlsx(r).read()
        self.assertGreater(len(wb_bytes), 5000)

    def test_billing_state_roundtrip(self):
        tmp, path = copy_project("machi")
        try:
            p = core.Project(path)
            p.save_billing("1.1", {"submitted": "2025-10-25", "invoice_no": "T-1"})
            p = core.Project(path)
            sched, _ = p.schedule(status=D(2025, 10, 25))
            m = next(x for x in p.milestone_status(D(2025, 10, 25), sched) if x["no"] == "1.1")
            self.assertEqual((m["status"], m["invoice_no"]), ("submitted", "T-1"))
        finally:
            shutil.rmtree(tmp)


class TestChanges(unittest.TestCase):
    def test_vo_and_eot(self):
        tmp, path = copy_project("machi-demo")
        try:
            p = core.Project(path)
            p.save_vo({"no": "1", "title": "พัดลมดูดอากาศ", "date": "2026-06-01", "status": "approved", "kind": "new",
                       "amount": 150000, "trade": "EE", "floors": "2-6", "kinds": "room", "duration": 10,
                       "preds": "FIXE6FS"})
            p.save_vo({"no": "2", "title": "ตัดราวระเบียงชั้น 2", "status": "approved", "kind": "adjust",
                       "amount": -40000, "task_id": "RAIL", "floors": "2"})
            p.save_vo({"no": "3", "title": "รออนุมัติ", "status": "pending", "kind": "new", "amount": 99999})
            p.save_eot({"no": "1", "title": "ฝน", "requested_days": 30, "approved_days": 21, "status": "approved"})
            p = core.Project(path)
            self.assertAlmostEqual(p.contract_value, 42056074.77 + 110000, places=2)
            self.assertAlmostEqual(p.total_value * p.k_contract, p.contract_value, places=2)
            self.assertAlmostEqual(p.task_value["VO1"] * p.k_contract, 150000, places=2)
            rail2 = sum(v for c, v in p.cells.items() if c[0] == "RAIL" and p.loc[c[1]]["floor"] == "2")
            self.assertAlmostEqual(rail2 * p.k_contract, 75035.83, places=1)
            self.assertEqual(p.contract_finish()[0], D(2026, 10, 26))
            vo_ms = {m["no"] for m in p.milestones if m.get("kind") == "vo"}
            self.assertEqual(vo_ms, {"VO-1", "VO-2"})
            self.assertAlmostEqual(p.money(150000)["net"], 148500.0, places=2)
            dl = p.delay(D(2026, 10, 22))
            self.assertLessEqual(dl["ld_forecast"], dl["ld_cap"] + 1e-6)
        finally:
            shutil.rmtree(tmp)


class TestServer(unittest.TestCase):
    """เรียก API ผ่าน Flask test client บนสำเนาโครงการ"""

    @classmethod
    def setUpClass(cls):
        import server
        cls.tmp, path = copy_project("machi-demo")
        server.PROJECTS = cls.tmp
        server.open_project("machi-demo")
        cls.c = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_pages_and_apis(self):
        for url in ["/", "/billing/10", "/api/state", "/api/schedule?date=2026-10-22", "/api/scurve?date=2026-10-22",
                    "/api/grid?floor=6&date=2026-10-22", "/api/heat?floor=6&date=2026-10-22", "/api/plans",
                    "/api/billing_report/10", "/api/billing_summary?date=2026-10-22", "/api/changes?date=2026-10-22",
                    "/api/export/schedule.xlsx", "/api/export/billing/10.xlsx", "/plans/A-P03.png"]:
            with self.c.get(url) as r:
                self.assertEqual(r.status_code, 200, url)

    def test_progress_rules(self):
        r = self.c.post("/api/progress", json={"date": "2099-01-01", "entries": [
            {"task_id": "RAIL", "loc_id": "F6-626", "pct": 50}]})
        self.assertEqual(r.status_code, 400)  # วันที่ในอนาคต
        r = self.c.post("/api/progress", json={"date": "2026-10-20", "entries": [
            {"task_id": "RAIL", "loc_id": "F6-626", "pct": 80, "steps": "10"}]})
        self.assertEqual(r.status_code, 200)
        g = self.c.get("/api/grid?floor=6&date=2026-10-20").get_json()
        self.assertEqual(g["cells"]["RAIL|F6-626"]["pct"], 80)

    def test_photo_upload(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (2400, 1800), "orange").save(buf, "JPEG")
        buf.seek(0)
        r = self.c.post("/api/photos", data={"loc_id": "F6-628", "task_id": "PAINT_IN", "date": "2026-10-20",
                                             "files": (buf, "a.jpg")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        ph = r.get_json()["photos"][0]
        self.assertLessEqual(max(ph["w"], ph["h"]), 1600)  # ย่อรูปแล้ว
        self.assertEqual(self.c.delete("/api/photos/" + ph["id"]).get_json()["ok"], True)


if __name__ == "__main__":
    unittest.main()
