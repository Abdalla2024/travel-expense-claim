"""Undefined expense categories (interview 3, 10:48-10:52) on a SYNTHETIC dataset.

Every identifier here is SYN-*. The undefined category is "gifts", chosen so the
tests do not presuppose anything about "entertainment" (C117), for which no
Finance decision exists. Finance instructions below are synthetic test inputs,
not scenario history; C117 itself is checked in tests/test_primary_run.py.
"""
import copy
import os
import sys
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from tec.repair_queue import RepairQueue  # noqa: E402
from test_engine_synthetic import D, approvals, base, fin, run  # noqa: E402


def with_gifts():
    """SYN-C1 r1: line 1 'gifts' (undefined) 25.00 EUR, line 2 meals 40.00 EUR (defined, capped 40/day)."""
    ds = base()
    c = ds["claims"][0]
    c["lines"][0].update(amount=Decimal("25.00"), amount_text="25.00")
    c["lines"].append({"line": 2, "cost_id": "SYN-COST-2", "receipt_ref": "SYN-R2", "first_submitted": D,
                       "amount": Decimal("40.00"), "amount_text": "40.00", "currency": "EUR"})
    r1 = ds["receipts"]["SYN-COST-1"][0]
    r1.update(category="gifts", gross=Decimal("25.00"))
    ds["merchant"]["SYN-COST-1"][0]["gross"] = Decimal("25.00")
    ds["receipts"]["SYN-COST-2"] = [dict(r1, receipt_ref="SYN-R2", cost_id="SYN-COST-2", category="meals", gross=Decimal("40.00"))]
    ds["merchant"]["SYN-COST-2"] = [dict(ds["merchant"]["SYN-COST-1"][0], txn="SYN-M2", cost_id="SYN-COST-2",
                                         gross=Decimal("40.00"), receipt_ref="SYN-R2", ref="syn#m2")]
    ds["caps"] = [{"destination": "NL", "category": "meals", "currency": "EUR", "from": D.replace(month=1, day=1),
                   "to": D.replace(month=12, day=31), "amount": Decimal("40"), "ref": "syn#cap-meals"}]
    return ds


def exception(rev=1, allowed="10.00", actor="SYN-FIN", category=None, cost="SYN-COST-1"):
    return {"actor": actor, "claim_id": "SYN-C1", "revision": rev, "cost_id": cost,
            "allowed_original": None if allowed is None else Decimal(allowed), "covered_issues": [],
            "travel_cancellation_id": None, "reason": "synthetic Finance instruction", "locator": "exc", "category": category}


def revision2(ds, exc, batch=2):
    c2 = copy.deepcopy(ds["claims"][0])
    c2.update(revision=2, arrival_batch=batch, locator="c2", exception=exc)
    ds["claims"].append(c2)
    return c2


def line(st, cost):
    return next(l for l in st["lines"] if l["cost_id"] == cost)


class UndefinedCategory(unittest.TestCase):
    def test_undefined_category_holds_claim_even_with_full_approvals(self):
        ds = with_gifts()
        ds["reviews"] = approvals(cost_ids=("SYN-COST-1", "SYN-COST-2"))
        eng, st = run(ds)
        c = st[1]["claims"]["SYN-C1"]
        self.assertEqual((c["status"], c["allowed_cents"], c["balance_cents"]), ("held", None, None))
        self.assertEqual(line(c, "SYN-COST-2")["allowed_cents"], 4000)          # defined line still calculated
        self.assertEqual(line(c, "SYN-COST-2")["status"], "supported")
        self.assertFalse(eng.requests)                                          # nothing proposed to Finance

    def test_unresolved_is_not_silently_zero(self):
        ds = with_gifts()
        eng, st = run(ds)
        g = line(st[1]["claims"]["SYN-C1"], "SYN-COST-1")
        self.assertEqual((g["status"], g["allowed_cents"]), ("unresolved", None))
        self.assertNotIn("zero entitlement", g["reason"])
        self.assertIn("'gifts' is not defined", g["reason"])

    def test_authority_and_follow_up_are_distinct(self):
        ds = with_gifts()
        eng, st = run(ds)
        c = st[1]["claims"]["SYN-C1"]
        i = next(i for i in c["issues"] if i["fact_code"] == "unknown_category")
        self.assertEqual((i["owner"], i["decision_authority"], i["follow_up"]), ("SYN-FIN", "SYN-FIN", "SYN-ADM"))
        self.assertEqual(c["next_owner"], "SYN-FIN")
        self.assertNotEqual(i["owner"], "SYN-E1")                               # employee is not the policy authority
        self.assertIn("may only be asked to clarify", i["resolution_needed"])
        q = RepairQueue("synthetic-test")
        q.update(1, c["issues"], {("claim", "SYN-C1"): 1}, {})
        item = q.items["RQ-SYN-C1-r1-unknown_category-SYN-COST-1"]
        self.assertEqual((item["owner"], item["follow_up"], item["cost_id"]), ("SYN-FIN", "SYN-ADM", "SYN-COST-1"))
        draft = q.drafts()["SYN-FIN"]
        self.assertIn("Follow-up on missing replies: SYN-ADM (Travel Administration Lead)", draft)

    def test_finance_instruction_resolves_only_when_valid(self):
        for exc, ok in ((exception(actor="SYN-BO"), False),                      # budget owner decides funding, not policy
                        (exception(rev=1), False),                                # bound to r1, claim is now r2
                        (exception(rev=2), True)):
            ds = with_gifts()
            revision2(ds, exc)
            eng, st = run(ds)
            g = line(st[2]["claims"]["SYN-C1"], "SYN-COST-1")
            self.assertEqual(g["status"] == "supported", ok, exc)
            if ok:
                self.assertEqual(g["allowed_cents"], 1000)
                self.assertTrue(any(s.endswith("#exc") for s in g["source_ids"]))
            else:
                self.assertEqual(g["allowed_cents"], None)

    def test_instruction_does_not_cover_missing_evidence(self):
        ds = with_gifts()
        ds["merchant"]["SYN-COST-1"] = []
        revision2(ds, exception(rev=2))
        eng, st = run(ds)
        c = st[2]["claims"]["SYN-C1"]
        self.assertEqual(line(c, "SYN-COST-1")["status"], "unresolved")
        self.assertEqual([i["fact_code"] for i in c["issues"]], ["missing_payment_proof"])

    def test_ineligible_records_zero_and_keeps_claimed_amount_and_evidence(self):
        ds = with_gifts()
        revision2(ds, exception(rev=2, allowed="0"))
        eng, st = run(ds)
        c = st[2]["claims"]["SYN-C1"]
        g = line(c, "SYN-COST-1")
        self.assertEqual((g["status"], g["allowed_cents"]), ("excluded", 0))
        self.assertIn("claimed 25.00 EUR retained with evidence", g["reason"])
        self.assertTrue({"receipts#r1:SYN-R1", "syn#m1"} <= set(g["source_ids"]))
        self.assertEqual(c["allowed_cents"], 4000)                               # meals line still owed
        self.assertEqual(c["status"], "pending")                                 # resolution alone does not close

    def test_reclassification_new_revision_revalidates_and_preserves_history(self):
        ds = with_gifts()
        ds["reviews"] = approvals(cost_ids=("SYN-COST-1", "SYN-COST-2"))           # r1 approvals, batch 1
        revision2(ds, exception(rev=2, allowed=None, category="meals"))
        eng, st = run(ds)
        self.assertEqual([r["revision"] for r in eng.revs["SYN-C1"]], [1, 2])    # r1 kept as history
        self.assertEqual(st[1]["claims"]["SYN-C1"]["revision"], 1)
        c = st[2]["claims"]["SYN-C1"]
        g = line(c, "SYN-COST-1")
        self.assertEqual((g["status"], g["allowed_cents"]), ("supported", 2500))
        self.assertIn("reclassified by Finance exception from receipt category 'gifts' to 'meals'", g["reason"])
        self.assertEqual(eng.ds["receipts"]["SYN-COST-1"][0]["category"], "gifts")  # source evidence unchanged
        self.assertEqual(c["decision_ids"], [])                                  # r1 approvals do not carry over
        self.assertEqual((c["status"], c["next_owner"]), ("pending", "SYN-ADM"))
        self.assertFalse(eng.requests)

    def test_resolution_then_approvals_then_finance_before_closure(self):
        ds = with_gifts()
        revision2(ds, exception(rev=2), batch=2)
        ds["reviews"] = approvals(batch=3, rev=2, cost_ids=("SYN-COST-1", "SYN-COST-2"))
        ds["finance"] = [fin("SYN-F1", "accepted", 4, obligation="50.00"), fin("SYN-F2", "settled", 5, amount="50.00", day=12)]
        eng, st = run(ds)
        self.assertEqual(st[1]["claims"]["SYN-C1"]["status"], "held")            # undefined category
        self.assertEqual(st[2]["claims"]["SYN-C1"]["status"], "pending")         # resolved, awaiting r2 reviews
        self.assertEqual(st[3]["claims"]["SYN-C1"]["status"], "ready")           # approved, request proposed
        self.assertEqual(st[4]["claims"]["SYN-C1"]["status"], "pending")         # accepted, not yet paid
        c5 = st[5]["claims"]["SYN-C1"]
        self.assertEqual((c5["status"], c5["allowed_cents"], c5["paid_cents"]), ("closed-reimbursed", 5000, 5000))


if __name__ == "__main__":
    unittest.main()
