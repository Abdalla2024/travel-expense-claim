"""Checks on the primary scenario run's sealed outputs.

Run selection: $TEC_RUN, else the newest fresh run under artifacts/runs. A replay
(if any) of that run is compared for equivalence. Expected values below were
derived by hand from the native sources (see references/requirements.md §3) and
are checked against the actual retained snapshots, batch by batch.
"""
import csv
import json


def _jload(path):
    """json.load on a path, closing the file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))
RUNS = os.environ.get("TEC_RUNS_DIR") or os.path.join(ROOT, "artifacts", "runs")

from tec import verify as vermod  # noqa: E402


def _runs(mode):
    out = []
    for r in sorted(os.listdir(RUNS)) if os.path.isdir(RUNS) else []:
        p = os.path.join(RUNS, r, "run.json")
        if os.path.exists(p):
            m = _jload(p)
            if m["mode"] == mode and m["outcome"] != "failure":
                out.append(m)
    return out


PRIMARY = os.environ.get("TEC_RUN") or (_runs("fresh")[-1]["run_id"] if _runs("fresh") else None)


@unittest.skipUnless(PRIMARY, "no primary run under artifacts/runs (run tec_cli.py run first)")
class PrimaryRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = os.path.join(RUNS, PRIMARY)
        cls.meta = _jload(os.path.join(cls.dir, "run.json"))
        cls.snap = {}
        for b in cls.meta["batches"]:
            with open(os.path.join(cls.dir, b["path"]), encoding="utf-8") as f:
                cls.snap[int(b["batch_id"].split("-")[1])] = json.load(f)

    def c(self, b, cid):
        return next(x for x in self.snap[b]["claims"] if x["claim_id"] == cid)

    def t(self, b, tc):
        return next(x for x in self.snap[b]["travel_cancellations"] if x["cancellation_id"] == tc)

    def expect(self, b, cid, status, allowed, paid, rev=None, owner="any"):
        c = self.c(b, cid)
        got = (c["status"], c["allowed_cents"], c["paid_cents"])
        self.assertEqual(got, (status, allowed, paid), "%s batch-%d" % (cid, b))
        if rev is not None:
            self.assertEqual(c["revision"], rev, "%s batch-%d revision" % (cid, b))
        if owner != "any":
            self.assertEqual(c["next_owner"], owner, "%s batch-%d owner" % (cid, b))

    def test_verifier_passes(self):
        res = vermod.verify(self.dir, os.path.join(ROOT, "snapshot.schema.json"))
        failed = [(n, d) for n, ok, d in res if not ok]
        self.assertFalse(failed, failed)

    def test_batches_and_chain(self):
        self.assertEqual(sorted(self.snap), [1, 2, 3, 4])
        self.assertIsNone(self.snap[1]["predecessor"])
        self.assertEqual({len(self.snap[b]["claims"]) for b in (1, 2)}, {120})
        self.assertEqual(len(self.snap[3]["claims"]), 121)  # C24 first arrives in batch 3

    def test_ordinary_path_and_arithmetic(self):
        self.expect(1, "C01", "pending", 10000, 0, owner="FIN-01")
        self.expect(2, "C01", "closed-reimbursed", 10000, 10000)
        self.expect(4, "C02", "closed-reimbursed", 54000, 54000)      # 600 USD x 0.9
        self.expect(4, "C07", "closed-reimbursed", 30000, 30000)      # lodging 360 capped at 150 x 2 nights
        for cid, cents in (("C102", 14999), ("C103", 15000), ("C104", 15000), ("C105", 3999), ("C106", 4000), ("C107", 4000)):
            self.expect(4, cid, "closed-reimbursed", cents, cents)
        for cid in ("C108", "C109"):                                   # half-up per line, then sum
            self.expect(4, cid, "closed-reimbursed", 208, 208)
        self.expect(4, "C115", "closed-reimbursed", 1500, 1500)       # personal line excluded, meal kept
        line = next(l for l in self.c(4, "C115")["lines"] if l["cost_id"] == "COST-115-1")
        self.assertEqual((line["status"], line["allowed_cents"]), ("excluded", 0))

    def test_director_threshold(self):
        self.assertEqual(len(self.c(4, "C05")["decision_ids"]), 3)    # exactly EUR 1,000.00: no director
        self.assertTrue(any("director" in d for d in self.c(4, "C06")["decision_ids"]))
        self.expect(4, "C119", "pending", 100001, 0, owner="DIR-01")  # EUR 1,000.01 without director reply

    def test_incomplete_claims_hold_only_themselves(self):
        held = {"C08": "EMP-01", "C114": "EMP-03", "C22": "FIN-01", "C23": "FIN-01", "C116": "FIN-01", "C117": "FIN-01"}
        for cid, owner in held.items():
            for b in (1, 4):
                self.expect(b, cid, "held", None, 0, owner=owner)
        c116 = {i["record_id"] for i in self.snap[4]["issues"] if i["record_id"].startswith("ISS-C116-")}
        self.assertEqual(c116, {"ISS-C116-r1-missing_cap-COST-116-1", "ISS-C116-r1-missing_rate-COST-116-2"})
        # Independent work in the same batch still completes.
        self.expect(2, "C27", "closed-reimbursed", 3500, 3500)

    def test_c117_undefined_category_stays_unresolved(self):
        # Interview 3 (10:48-10:52): undefined category is unresolved until Finance defines it or instructs on
        # eligibility; whole claim held; Finance is the authority; the Travel Administration Lead follows up.
        for b in (1, 2, 3, 4):
            c = self.c(b, "C117")
            self.assertEqual((c["status"], c["allowed_cents"], c["balance_cents"], c["next_owner"]), ("held", None, None, "FIN-01"))
            ent = next(l for l in c["lines"] if l["cost_id"] == "COST-117-1")
            self.assertEqual((ent["status"], ent["allowed_cents"]), ("unresolved", None))   # not silently zero
            meals = next(l for l in c["lines"] if l["cost_id"] == "COST-117-2")
            self.assertEqual((meals["status"], meals["allowed_cents"]), ("supported", 4000))
        self.assertFalse([r for r in self.snap[4]["requests"] if r["claim_id"] == "C117"])
        iss = next(i for i in self.snap[4]["issues"] if i["record_id"] == "ISS-C117-r1-unknown_category-COST-117-1")
        self.assertEqual(iss["owner"], "FIN-01")
        self.assertIn("'entertainment'", iss["reason"])
        self.assertIn("Travel Administration Lead (ADMIN-01) follows up", iss["resolution_needed"])
        with open(os.path.join(self.dir, "queue", "items.json"), encoding="utf-8") as f:
            item = next(i for i in json.load(f) if i["item_id"] == "RQ-C117-r1-unknown_category-COST-117-1")
        self.assertEqual((item["owner"], item["decision_authority"], item["follow_up"], item["status"]),
                         ("FIN-01", "FIN-01", "ADMIN-01", "open"))
        self.assertNotIn(item["owner"], ("EMP-03", "LEAD-01"))   # not the employee, not the budget owner

    def test_late_filing_and_permits(self):
        self.expect(1, "C11", "pending", 6000, 0)                      # submitted on the deadline day
        self.expect(1, "C112", "held", None, 0, owner="FIN-01")        # one day late, no exception
        self.expect(1, "C12", "held", None, 0, rev=1, owner="FIN-01")
        self.expect(3, "C12", "pending", 7000, 0, rev=2)               # Finance late-filing exception for r2
        self.expect(4, "C12", "closed-reimbursed", 7000, 7000, rev=2)
        self.expect(4, "C10", "held", None, 0, owner="FIN-01")         # P10 approved after commitment
        self.assertIn("late_permit", self.c(4, "C10")["reason"])
        self.expect(4, "C25", "held", None, 0, owner="FIN-01")         # P25 never approved
        self.assertIn("permit_unapproved", self.c(4, "C25")["reason"])
        self.expect(4, "C02", "closed-reimbursed", 54000, 54000)       # P02 approved incl. director before commitment

    def test_review_outcomes_and_zero_entitlement(self):
        self.expect(4, "C13", "withdrawn", 0, 0)
        self.expect(4, "C14", "rejected", 0, 0)
        # Changed for interview 4 routing: the budget owner returned C21 for a funding decision, which the budget
        # owner makes (INT3 10:48), so the request goes to LEAD-01, not the employee as in earlier runs.
        self.expect(4, "C21", "held", 8000, 0, owner="LEAD-01")
        for cid in ("C15", "C118"):                                    # INT2 10:07: full review still required
            for b in (1, 2, 3, 4):
                self.expect(b, cid, "pending", 0, 0, owner="ADMIN-01")
        self.expect(4, "C113", "pending", 2500, 0, owner="ADMIN-01")   # paid after submission; proof now present
        self.expect(4, "C26", "pending", 10000, 0, owner="ADMIN-01")

    def test_returned_work_routed_by_request(self):
        # New for interview 4 (01:20) with interview 3 (10:48): each return names the exact need and its owner.
        with open(os.path.join(self.dir, "queue", "items.json"), encoding="utf-8") as f:
            items = {i["item_id"]: i for i in json.load(f)}
        c21 = items["RQ-C21-r1-funding_decision:budget_owner"]
        self.assertEqual((c21["owner"], c21["follow_up"], c21["status"]), ("LEAD-01", "ADMIN-01", "open"))
        self.assertIn("funding decision for claim C21 revision 1", c21["next_action"])
        c09 = items["RQ-C09-r1-employee_correction:budget_owner"]
        self.assertEqual((c09["owner"], c09["status"]), ("EMP-01", "superseded"))
        self.assertIn("Provide revised trip evidence", c09["next_action"])
        with open(os.path.join(self.dir, "queue", "drafts", "LEAD-01.md"), encoding="utf-8") as f:
            draft = f.read()
        self.assertIn("**Funding decision needed**", draft)
        with open(os.path.join(self.dir, "queue", "drafts", "EMP-01.md"), encoding="utf-8") as f:
            self.assertNotIn("C21", f.read())                       # no longer misplaced with the employee
        for name in os.listdir(os.path.join(self.dir, "queue", "drafts")):
            with open(os.path.join(self.dir, "queue", "drafts", name), encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("returned:", text)
            self.assertNotIn("..", text)

    def test_correction_after_return(self):
        self.expect(1, "C09", "held", 8000, 0, rev=1, owner="EMP-01")
        self.expect(3, "C09", "pending", 8000, 0, rev=2)
        self.assertEqual(self.c(3, "C09")["trip_id"], "T09B")
        self.expect(4, "C09", "closed-reimbursed", 8000, 8000, rev=2)

    def test_partial_payments_and_failed_retry(self):
        for cid, b2, total in (("C16", 4000, 10000), ("C120", 3000, 7500)):
            self.expect(2, cid, "pending", total, b2, owner="FIN-01")
            self.expect(3, cid, "closed-reimbursed", total, total)
        self.expect(2, "C17", "pending", 10000, 0)
        self.assertIn("ISS-C17-r1-payment_failed", {i["record_id"] for i in self.snap[2]["issues"]})
        self.expect(3, "C17", "pending", 10000, 0)
        self.expect(4, "C17", "closed-reimbursed", 10000, 10000)

    def test_overpayment_refund_resolution(self):
        self.expect(2, "C20", "held", 10000, 11000, owner="FIN-01")
        self.assertEqual(self.c(2, "C20")["balance_cents"], -1000)
        self.expect(3, "C20", "held", 10000, 10000, owner="FIN-01")   # refunded, resolution still owed
        self.expect(4, "C20", "closed-reimbursed", 10000, 10000)

    def test_c19_correction_and_cancellation_after_payment(self):
        self.expect(2, "C19", "closed-reimbursed", 10000, 10000, rev=1)
        self.expect(3, "C19", "held", None, 10000, rev=2, owner="FIN-01")
        self.assertEqual(self.t(3, "TC019")["financial_status"], "unresolved")
        self.expect(4, "C19", "closed-reimbursed", 8000, 8000, rev=3)
        self.assertEqual(self.t(4, "TC019")["financial_status"], "resolved")
        self.assertTrue(all(d.startswith("D-C19-3-") for d in self.c(4, "C19")["decision_ids"]))

    def test_c18_reassignment_and_late_transfer_stays_unresolved(self):
        self.expect(2, "C18", "held", None, 0, rev=1, owner="FIN-01")
        self.expect(3, "C18", "pending", 10000, 0, rev=2, owner="ADMIN-01")
        self.assertEqual(self.t(3, "TC018")["financial_status"], "resolved")
        self.expect(4, "C18", "held", 10000, 10000, rev=2, owner="FIN-01")
        self.assertEqual(self.t(4, "TC018")["financial_status"], "unresolved")
        self.assertIn("ISS-C18-r2-transfer_after_cancellation", self.t(4, "TC018")["issue_record_ids"])
        req = next(r for r in self.snap[4]["requests"] if r["request_id"] == "REQ-C18")
        self.assertEqual(req["status"], "cancelled")

    def test_permit_cancellation_and_cancellation_without_claim(self):
        self.expect(1, "C121", "held", 3000, 0, owner="SUP-01")
        self.assertEqual(self.t(1, "TC121")["status"], "requested")
        self.expect(2, "C121", "held", None, 0, owner="FIN-01")
        self.expect(4, "C121", "closed-reimbursed", 2000, 2000, rev=2)
        for b in (1, 2, 3, 4):
            t = self.t(b, "TC122")
            self.assertEqual((t["affected_claim_ids"], t["financial_status"]), ([], "no-financial-effect"))
            self.assertFalse([c for c in self.snap[b]["claims"] if c["trip_id"] == "T122"])
        self.assertEqual(self.t(4, "TC122")["admitted_cancellation_event_ids"], ["TC122-requested", "TC122-confirmed"])

    def test_prepaid_link_and_replay_no_effect(self):
        self.expect(4, "C24", "closed-reimbursed", 5000, 5000)
        l = next(l for l in self.c(4, "C24")["lines"] if l["cost_id"] == "COST-03")
        self.assertEqual((l["status"], l["allowed_cents"]), ("excluded", 0))
        self.assertEqual(self.snap[4]["admitted_event_ids"].count("F-C01-1"), 1)
        self.expect(4, "C01", "closed-reimbursed", 10000, 10000)
        with open(os.path.join(self.dir, "report.md"), encoding="utf-8") as f:
            report = f.read()
        self.assertIn("finance `F-C01-1` in batch-4: no effect", report)
        self.assertIn("cancellation `TC122-confirmed` in batch-4: no effect", report)

    def test_earlier_batches_preserved(self):
        # Batch 4 knowledge never leaks into batch 1-3 snapshots.
        self.assertNotIn("F-C18-3", self.snap[3]["admitted_event_ids"])
        self.assertEqual(self.c(1, "C19")["revision"], 1)
        self.assertNotIn("TC019", [t["cancellation_id"] for t in self.snap[2]["travel_cancellations"]])

    def test_claims_csv_blank_unknown_money(self):
        with open(os.path.join(self.dir, "claims.csv"), encoding="utf-8") as f:
            rows = {r["claim_id"]: r for r in csv.DictReader(f)}
        self.assertEqual((rows["C22"]["allowed_cents"], rows["C22"]["paid_cents"], rows["C22"]["balance_cents"]), ("", "0", ""))
        self.assertEqual(rows["C15"]["allowed_cents"], "0")

    def test_queue_history(self):
        with open(os.path.join(self.dir, "queue", "events.jsonl"), encoding="utf-8") as f:
            events = [json.loads(l) for l in f]
        partial = [e for e in events if e["event"] == "partial-response"]
        self.assertTrue(any(e["subject"] == "C20" and e["batch_id"] == "batch-3" for e in partial))
        # Changed for interview 4: return items are named by what is needed, not by the reviewer's decision ID.
        sup = [e for e in events if e["event"] == "superseded" and e["item_id"] == "RQ-C09-r1-employee_correction:budget_owner"]
        self.assertEqual(sup[0]["batch_id"], "batch-3")


@unittest.skipUnless(PRIMARY and [m for m in _runs("replay") if m["replay_of"] == PRIMARY], "no replay of the primary run")
class Replay(unittest.TestCase):
    def test_replay_equivalent(self):
        rep = [m for m in _runs("replay") if m["replay_of"] == PRIMARY][-1]
        res = vermod.verify(os.path.join(RUNS, rep["run_id"]), os.path.join(ROOT, "snapshot.schema.json"),
                            os.path.join(RUNS, PRIMARY))
        failed = [(n, d) for n, ok, d in res if not ok]
        self.assertFalse(failed, failed)


if __name__ == "__main__":
    unittest.main()
