"""Unit tests for money, date and repair-queue rules (synthetic inputs only)."""
import datetime as dt
import json
import os
import sys
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))

from tec import parse  # noqa: E402
from tec.engine import add_months_clamped, cents  # noqa: E402
from tec.repair_queue import RepairQueue  # noqa: E402


class MoneyAndDates(unittest.TestCase):
    def test_half_up_per_line(self):
        # C108/C109 shape: 1.15 USD and 1.16 USD at 0.9 round per line before summing (POL ¶3)
        self.assertEqual(cents(Decimal("1.15") * Decimal("0.9")), 104)   # 1.035 -> 1.04
        self.assertEqual(cents(Decimal("1.16") * Decimal("0.9")), 104)   # 1.044 -> 1.04
        self.assertEqual(cents(Decimal("0.005")), 1)
        self.assertEqual(cents(Decimal("600") * Decimal("0.9")), 54000)

    def test_deadline_two_months_inclusive_clamped(self):
        self.assertEqual(add_months_clamped(dt.date(2026, 8, 31), 2), dt.date(2026, 10, 31))  # policy example
        self.assertEqual(add_months_clamped(dt.date(2026, 7, 1), 2), dt.date(2026, 9, 1))     # T11/T111 boundary
        self.assertEqual(add_months_clamped(dt.date(2026, 12, 31), 2), dt.date(2027, 2, 28))
        self.assertEqual(add_months_clamped(dt.date(2027, 12, 31), 2), dt.date(2028, 2, 29))

    def test_excel_serials(self):
        self.assertEqual(parse.serial_date("46266"), dt.date(2026, 9, 1))
        self.assertEqual(parse.serial_utc("46275.375").isoformat(), "2026-09-10T09:00:00+00:00")
        self.assertEqual(parse.dec("1000.01"), Decimal("1000.01"))


class PartialResponseQueue(unittest.TestCase):
    """Uses tests/fixtures/synthetic_partial_response.json — a SYNTHETIC fixture, not scenario history."""

    def setUp(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "synthetic_partial_response.json"), encoding="utf-8") as f:
            self.fx = json.load(f)
        self.assertIn("SYNTHETIC", self.fx["_label"])

    def _issues(self, b):
        s = self.fx["subject"]
        out = []
        for f in b["open_facts"]:
            out.append(dict(s, record_id="ISS-%s-r%d-%s-%s" % (s["subject_id"], b["revision"], f["fact_code"], f["cost_id"]),
                            revision=b["revision"], fact_code=f["fact_code"], cost_id=f["cost_id"], reason=f["reason"],
                            owner=self.fx["owner"], resolution_needed=f["action"], source_ids=["synthetic-fixture"]))
        return out

    def test_partial_response_keeps_unsatisfied_facts_open(self):
        q = RepairQueue("synthetic-test")
        b1, b2, b3 = self.fx["batches"]
        q.update(1, self._issues(b1), {("claim", "SYN-C1"): 1}, {})
        self.assertEqual(len(q.open_items()), 3)

        ev2 = q.update(2, self._issues(b2), {("claim", "SYN-C1"): 1}, {"SYN-C1": b2["inputs"]})
        kinds = [e["event"] for e in ev2]
        self.assertEqual(kinds.count("satisfied"), 1)
        partial = [e for e in ev2 if e["event"] == "partial-response"]
        self.assertEqual(len(partial), 1)
        self.assertEqual(partial[0]["satisfied"], ["RQ-SYN-C1-r1-missing_receipt-SYN-COST-1"])
        self.assertEqual(len(partial[0]["still_open"]), 2)
        self.assertEqual(partial[0]["batch_id"], "batch-2")
        # Unsatisfied items are unchanged: no event touches them.
        self.assertFalse([e for e in ev2 if e["item_id"] and "SYN-COST-2" in e["item_id"]])

        ev3 = q.update(3, self._issues(b3), {("claim", "SYN-C1"): 2}, {"SYN-C1": b3["inputs"]})
        sup = {e["item_id"]: e for e in ev3 if e["event"] == "superseded"}
        self.assertEqual(set(sup), {"RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-2", "RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3"})
        new = q.items["RQ-SYN-C1-r2-missing_payment_proof-SYN-COST-3"]
        self.assertEqual(new["supersedes"], "RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3")
        self.assertEqual(q.items[new["supersedes"]]["superseded_by"], new["item_id"])
        self.assertIsNone(q.items["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-2"]["superseded_by"])
        # History is append-only and fully referenced.
        self.assertEqual([e["seq"] for e in q.events], list(range(1, len(q.events) + 1)))
        self.assertTrue(all(e["run_id"] == "synthetic-test" for e in q.events))
        drafts = q.drafts()
        self.assertIn("DRAFT request to SYN-EMP — not sent", drafts["SYN-EMP"])


if __name__ == "__main__":
    unittest.main()
