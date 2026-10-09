"""Interview 6 rules on SYNTHETIC inputs (SYN-*): re-review after a late Finance rate or cap (02:09),
hold-impact explanations (02:08-02:09) and wrong-role replies (02:09)."""
import copy
import os
import sys
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_engine_synthetic import D, approvals, base, review, run  # noqa: E402


def gbp_claim():
    """SYN-C1 r1: one transport line of 50.00 GBP; the Finance GBP rate arrives in batch 2 (synthetic)."""
    ds = base()
    ds["claims"][0]["lines"][0].update(amount=Decimal("50.00"), amount_text="50.00", currency="GBP")
    ds["receipts"]["SYN-COST-1"][0].update(currency="GBP", gross=Decimal("50.00"))
    ds["merchant"]["SYN-COST-1"][0].update(currency="GBP", gross=Decimal("50.00"))
    ds["fx"] = [{"currency": "GBP", "date": D, "rate": Decimal("1.17"), "ref": "syn#fx-gbp", "batch": 2}]
    return ds


class LateRateReReview(unittest.TestCase):
    def test_only_amount_dependent_reviews_repeat(self):
        ds = gbp_claim()
        ds["reviews"] = approvals()                                            # all three approve in batch 1
        ds["reviews"] += [review("SYN-A3", "administration", batch=3), review("SYN-B3", "budget_owner", batch=3)]
        eng, st = run(ds)
        self.assertEqual(st[1]["claims"]["SYN-C1"]["status"], "held")          # rate missing
        c2 = st[2]["claims"]["SYN-C1"]
        self.assertEqual((c2["status"], c2["allowed_cents"]), ("pending", 5850))
        self.assertEqual(c2["decision_ids"], ["SYN-S1"])                        # supervisor's review stands
        self.assertEqual(c2["next_owner"], "SYN-ADM")
        self.assertIn("SYN-A1, SYN-B1 from batch 1 predate", c2["reason"])
        self.assertIn("administration/budget_owner review of r1 repeats", c2["reason"])
        c3 = st[3]["claims"]["SYN-C1"]
        self.assertEqual((c3["status"], c3["decision_ids"]), ("ready", ["SYN-A3", "SYN-B3", "SYN-S1"]))

    def test_late_payment_proof_still_invalidates_every_reply(self):
        ds = base()
        ds["merchant"]["SYN-COST-1"][0]["batch"] = 2
        ds["reviews"] = approvals()
        eng, st = run(ds)
        c2 = st[2]["claims"]["SYN-C1"]
        self.assertEqual((c2["status"], c2["decision_ids"]), ("pending", []))

    def test_new_revision_still_needs_its_own_approvals(self):
        ds = gbp_claim()
        ds["fx"][0]["batch"] = 1
        ds["reviews"] = approvals()
        c2 = copy.deepcopy(ds["claims"][0])
        c2.update(revision=2, arrival_batch=2, locator="c2")
        ds["claims"].append(c2)
        eng, st = run(ds)
        self.assertEqual(st[1]["claims"]["SYN-C1"]["status"], "ready")
        self.assertEqual((st[2]["claims"]["SYN-C1"]["revision"], st[2]["claims"]["SYN-C1"]["decision_ids"]), (2, []))


class HoldImpact(unittest.TestCase):
    def test_line_hold_states_withheld_amounts_and_risk(self):
        ds = base()
        c = ds["claims"][0]
        c["lines"].append({"line": 2, "cost_id": "SYN-COST-2", "receipt_ref": "SYN-R2", "first_submitted": D,
                           "amount": Decimal("15.00"), "amount_text": "15.00", "currency": "EUR"})
        ds["receipts"]["SYN-COST-2"] = [dict(ds["receipts"]["SYN-COST-1"][0], receipt_ref="SYN-R2", cost_id="SYN-COST-2",
                                             gross=Decimal("15.00"))]                     # no merchant proof
        eng, st = run(ds)
        c1 = st[1]["claims"]["SYN-C1"]
        i = next(i for i in c1["issues"] if i["fact_code"] == "missing_payment_proof")
        self.assertIn("Withheld: SYN-COST-1 EUR 100.00, total EUR 100.00; already paid EUR 0.00", i["hold_impact"])
        self.assertIn("SYN-COST-2 (claimed 15.00 EUR) is unresolved", i["hold_impact"])
        self.assertIn("Proceeding on the independent lines instead", i["hold_impact"])
        self.assertEqual(c1["allowed_cents"], None)                                 # contract unchanged: unknown

    def test_single_line_hold_withholds_nothing(self):
        ds = base()
        ds["merchant"]["SYN-COST-1"] = []
        eng, st = run(ds)
        self.assertIn("holding withholds nothing that could proceed", st[1]["claims"]["SYN-C1"]["hold_impact"])

    def test_claim_level_hold_is_not_a_line_choice(self):
        ds = base()
        ret = review("SYN-RET", "budget_owner", outcome="return")
        ret.update(repair="Obtain funding decision.", reason="Funding review")
        ds["reviews"] = [ret]
        eng, st = run(ds)
        self.assertIn("Held for a claim-level reason (funding_decision)", st[1]["claims"]["SYN-C1"]["hold_impact"])


class WrongRoleReply(unittest.TestCase):
    def test_reply_from_wrong_person_is_history_only(self):
        ds = base()
        ds["reviews"] = approvals()[:2] + [review("SYN-S-WRONG", "supervisor", reviewer="SYN-DIR")]
        eng, st = run(ds)
        c = st[1]["claims"]["SYN-C1"]
        self.assertEqual((c["status"], c["next_owner"]), ("pending", "SYN-SUP"))   # case not advanced
        self.assertNotIn("SYN-S-WRONG", c["decision_ids"])
        self.assertEqual([x["decision"]["decision_id"] for x in eng.rejected_imports], ["SYN-S-WRONG"])  # history kept


if __name__ == "__main__":
    unittest.main()
