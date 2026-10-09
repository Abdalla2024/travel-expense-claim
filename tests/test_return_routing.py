"""Returned-work routing by what the reviewer asked for (interview 3 10:48, interview 4 01:20).

SYNTHETIC inputs (SYN-*) for the branches; the real C21/C09 returns are checked in
tests/test_primary_run.py. Repair texts below reuse the wording of the supplied
review ledger where a real example exists.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from tec import routing  # noqa: E402
from tec.repair_queue import RepairQueue  # noqa: E402
from test_engine_synthetic import approvals, base, review, run  # noqa: E402


def returned(repair, reason="r", batch=1, later=None):
    ds = base()
    ret = review("SYN-RET", "budget_owner", batch=batch, outcome="return")
    ret.update(repair=repair, reason=reason, affected_fields=["trip", "amount", "evidence"])
    ds["reviews"] = [review("SYN-A1", "administration"), ret, review("SYN-S1", "supervisor")]
    if later:
        ds["reviews"].append(later)
    return ds


class Classification(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(routing.classify("Obtain funding decision.", "Budget owner requests a funding review")[0], "funding_decision")
        self.assertEqual(routing.classify("Provide revised trip evidence.", None)[0], "employee_correction")
        self.assertEqual(routing.classify("Call me", "See note")[0], "return_unclassified")
        kind, _, _, basis = routing.classify("Provide budget evidence", None)    # matches two routes: not guessed
        self.assertEqual(kind, "return_unclassified")
        self.assertIn("more than one route", basis)


class ReturnRouting(unittest.TestCase):
    def test_funding_return_goes_to_budget_owner(self):
        eng, st = run(returned("Obtain funding decision.", "Budget owner requests a funding review before committing."))
        c = st[1]["claims"]["SYN-C1"]
        i = next(i for i in c["issues"] if i["fact_code"].startswith("funding_decision"))
        self.assertEqual((c["status"], c["next_owner"], i["owner"], i["follow_up"]), ("held", "SYN-BO", "SYN-BO", "SYN-ADM"))
        self.assertIn("funding decision for claim SYN-C1 revision 1", i["resolution_needed"])
        self.assertNotIn("SYN-E1", i["owner"])

    def test_evidence_return_goes_to_employee_with_affected_fields(self):
        eng, st = run(returned("Provide revised trip evidence.", "Please supply the revised trip evidence."))
        i = next(i for i in st[1]["claims"]["SYN-C1"]["issues"] if i["fact_code"].startswith("employee_correction"))
        self.assertEqual(i["owner"], "SYN-E1")
        self.assertIn("Affected fields: trip, amount, evidence", i["reason"])
        self.assertIn("Provide revised trip evidence", i["resolution_needed"])

    def test_unclassified_return_goes_to_lead_not_guessed(self):
        eng, st = run(returned("Call me about this.", "See note."))
        i = next(i for i in st[1]["claims"]["SYN-C1"]["issues"] if i["fact_code"].startswith("return_unclassified"))
        self.assertEqual(i["owner"], "SYN-ADM")
        self.assertIn("No interview settles", i["route_basis"])

    def test_later_reply_from_same_role_resumes_review(self):
        later = review("SYN-B2", "budget_owner", batch=2)
        eng, st = run(returned("Obtain funding decision.", later=later))
        self.assertEqual(st[1]["claims"]["SYN-C1"]["status"], "held")
        c2 = st[2]["claims"]["SYN-C1"]
        self.assertEqual(c2["status"], "ready")                                   # resumed; request proposed
        self.assertEqual(c2["decision_ids"], ["SYN-A1", "SYN-B2", "SYN-RET", "SYN-S1"])
        self.assertFalse([i for i in c2["issues"] if i["fact_code"].startswith("funding_decision")])

    def test_rejection_is_not_undone_by_a_later_reply(self):
        ds = base()
        ds["reviews"] = approvals() + [review("SYN-REJ", "supervisor", outcome="reject"),
                                       review("SYN-S9", "supervisor", batch=2)]
        eng, st = run(ds)
        self.assertEqual(st[2]["claims"]["SYN-C1"]["status"], "rejected")

    def test_draft_is_plain_language(self):
        eng, st = run(returned("Obtain funding decision.", "Budget owner requests a funding review before committing."))
        q = RepairQueue("synthetic-test")
        q.update(1, st[1]["claims"]["SYN-C1"]["issues"], {("claim", "SYN-C1"): 1}, {})
        text = q.drafts()["SYN-BO"]
        self.assertIn("**Funding decision needed**", text)
        self.assertNotIn("returned:", text)
        self.assertNotIn("SYN-RET", text.split("Evidence:")[0])                  # decision ID only in evidence refs
        self.assertNotIn("..", text)


if __name__ == "__main__":
    unittest.main()
