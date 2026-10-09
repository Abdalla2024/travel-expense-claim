"""Partial-reply resumption (interview 4, 01:20) on the labelled SYNTHETIC scenario.

Fixture: tests/fixtures/synthetic_partial_resumption.json (all SYN-*). The retained
output under artifacts/synthetic/partial-resumption/ must equal a fresh rerun of
the same fixture, and must never appear under artifacts/runs/.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from tec import synthetic  # noqa: E402
from tec.repair_queue import RepairQueue  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "synthetic_partial_resumption.json")
# The current retained copy (interview 6: hold impact, wrong-role reply). Earlier copies are kept unmodified:
# partial-resumption/ (557b1a2) and partial-resumption-2/ (c1411c5).
RETAINED = os.path.join(ROOT, "artifacts", "synthetic", "partial-resumption-3")


class PartialResumption(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.out = os.path.join(cls.tmp, "artifacts", "synthetic", "partial-resumption")
        cls.batches, cls.rq, cls.eng = synthetic.run_demo(FIXTURE, cls.out)
        cls.b = {pb["batch"]: pb for pb in cls.batches}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def claim(self, b, cid):
        return self.b[b]["claims"][cid]

    def line(self, b, cid, cost):
        return next(l for l in self.claim(b, cid)["lines"] if l["cost_id"] == cost)

    def test_partial_reply_resumes_only_supported_tasks(self):
        self.assertEqual(self.claim(1, "SYN-C1")["status"], "held")
        # Batch 2: proof for SYN-COST-1 and the GBP rate arrive; SYN-COST-3 proof does not.
        self.assertEqual((self.line(2, "SYN-C1", "SYN-COST-1")["status"], self.line(2, "SYN-C1", "SYN-COST-1")["allowed_cents"]), ("supported", 6000))
        self.assertEqual((self.line(2, "SYN-C1", "SYN-COST-2")["status"], self.line(2, "SYN-C1", "SYN-COST-2")["allowed_cents"]), ("supported", 5850))
        self.assertEqual(self.line(2, "SYN-C1", "SYN-COST-3")["status"], "unresolved")
        c2 = self.claim(2, "SYN-C1")
        self.assertEqual((c2["status"], c2["allowed_cents"]), ("held", None))   # whole claim held (INT3 10:49)
        partial = [e for e in self.b[2]["queue_events"] if e["event"] == "partial-response"]
        self.assertEqual(len(partial), 1)
        self.assertEqual((partial[0]["owner"], partial[0]["satisfied"], partial[0]["still_open"]),
                         ("SYN-E1", ["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-1"],
                          ["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3"]))
        self.assertEqual(self.rq.items["RQ-SYN-C1-r1-missing_rate-SYN-COST-2"]["last_changed"]["batch_id"], "batch-2")
        self.assertEqual(self.rq.items["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3"]["status"], "satisfied")
        self.assertEqual(self.rq.items["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3"]["last_changed"]["batch_id"], "batch-3")
        # INT5 01:51: the item itself records the source that closed it.
        self.assertEqual(self.rq.items["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-1"]["resolved_by"], ["synthetic#merchant:SYN-M1"])

    def test_unrelated_claim_resumes_independently(self):
        self.assertEqual((self.claim(1, "SYN-C2")["status"], self.claim(1, "SYN-C2")["next_owner"]), ("held", "SYN-BO"))
        self.assertEqual(self.claim(2, "SYN-C2")["status"], "pending")         # funding reply arrived; at Finance
        self.assertEqual(self.claim(3, "SYN-C2")["status"], "closed-reimbursed")
        self.assertEqual(self.claim(2, "SYN-C1")["status"], "held")            # unaffected by SYN-C2 resuming

    def test_late_evidence_makes_earlier_reply_stale_then_review_resumes(self):
        self.assertEqual(self.claim(1, "SYN-C1")["decision_ids"], ["SYN-D-C1-ADM-1"])
        self.assertEqual(self.claim(2, "SYN-C1")["decision_ids"], [])
        c3 = self.claim(3, "SYN-C1")
        self.assertEqual(c3["decision_ids"], ["SYN-D-C1-ADM-3", "SYN-D-C1-BO-3", "SYN-D-C1-SUP-3"])
        self.assertEqual((c3["status"], c3["allowed_cents"]), ("ready", 15850))
        c4 = self.claim(4, "SYN-C1")
        self.assertEqual((c4["status"], c4["paid_cents"], c4["balance_cents"]), ("closed-reimbursed", 15850, 0))

    def test_no_duplicate_requests_or_payments(self):
        opened = [e["item_id"] for e in self.rq.events if e["event"] == "opened"]
        self.assertEqual(len(opened), len(set(opened)))                       # each fact requested once
        self.assertIn(("finance", "SYN-F-C2-1", 4), self.eng.replays)
        self.assertEqual(self.claim(4, "SYN-C2")["paid_cents"], 12000)        # redelivery adds nothing
        self.assertEqual([r["request_id"] for r in self.eng.requests.values()], ["REQ-SYN-C2", "REQ-SYN-C1"])

    def test_funding_return_routed_to_budget_owner_with_evidence(self):
        ev = next(e for e in self.b[2]["queue_events"] if e["item_id"] == "RQ-SYN-C2-r1-funding_decision:budget_owner")
        self.assertEqual((ev["event"], ev["owner"]), ("satisfied", "SYN-BO"))
        self.assertIn("synthetic#review:SYN-D-C2-BO-2", ev["evidence"])

    def test_second_request_for_same_fact_updates_the_original_item(self):
        # INT5 01:51: keep the original finding and owner; update the item's source and next action, no new request.
        base = {"subject_type": "claim", "subject_id": "SYN-C9", "revision": 1, "trip_id": "SYN-T9", "trip_revision": 1,
                "permit_id": None, "permit_revision": None, "cost_id": None, "owner": "SYN-BO",
                "reason": "returned for funding", "resolution_needed": "decide funding", "source_ids": ["synthetic"]}
        q = RepairQueue("synthetic-test")
        evs = q.update(1, [dict(base, record_id="ISS-SYN-C9-r1-funding_decision:budget_owner", fact_code="funding_decision:budget_owner"),
                           dict(base, record_id="ISS-SYN-C9-r1-funding_decision:supervisor", fact_code="funding_decision:supervisor")],
                       {("claim", "SYN-C9"): 1}, {})
        self.assertEqual([e["event"] for e in evs], ["opened", "merged-into-existing"])
        self.assertEqual(len(q.open_items()), 1)
        item = q.open_items()[0]
        self.assertEqual((item["item_id"], item["owner"]), ("RQ-SYN-C9-r1-funding_decision:budget_owner", "SYN-BO"))
        self.assertEqual(item["also_covers"], ["ISS-SYN-C9-r1-funding_decision:supervisor"])
        self.assertEqual(q.drafts()["SYN-BO"].count("Funding decision needed"), 1)

    def test_output_is_labelled_and_retained_copy_matches(self):
        with open(os.path.join(self.out, "report.md"), encoding="utf-8") as f:
            self.assertIn("SYNTHETIC", f.read().splitlines()[0])
        for name in os.listdir(os.path.join(self.out, "queue", "drafts")):
            with open(os.path.join(self.out, "queue", "drafts", name), encoding="utf-8") as f:
                self.assertTrue(f.read().startswith("> SYNTHETIC"))
        if not os.path.isdir(RETAINED):
            self.skipTest("retained synthetic scenario not generated yet")
        for rel in ("report.md", "states.json", "queue/items.json", "queue/events.jsonl"):
            with open(os.path.join(self.out, rel), encoding="utf-8") as a, open(os.path.join(RETAINED, rel), encoding="utf-8") as b:
                self.assertEqual(a.read().replace("synthetic-partial-resumption", ""),
                                 b.read().replace("synthetic-partial-resumption", ""), rel)

    def test_wrong_role_reply_kept_as_history_without_advancing(self):
        # INT6 02:09: not current authorization; it waits or is rejected and stays as history.
        rej = [x for x in self.eng.rejected_imports if x["decision"]["decision_id"] == "SYN-D-C2-SUP-X"]
        self.assertEqual(len(rej), 1)
        self.assertIn("SYN-BO is not the directory supervisor", rej[0]["reason"])
        for b in (1, 2, 3, 4):
            self.assertNotIn("SYN-D-C2-SUP-X", self.claim(b, "SYN-C2")["decision_ids"])
        with open(os.path.join(self.out, "report.md"), encoding="utf-8") as f:
            self.assertIn("`SYN-D-C2-SUP-X` (batch-1): SYN-BO claimed supervisor", f.read())

    def test_hold_impact_states_what_is_withheld(self):
        # INT6 02:08-02:09: holding is permitted when its business cost is explained.
        item = self.rq.items["RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3"]
        self.assertIn("Withheld: SYN-COST-1 EUR 60.00, SYN-COST-2 EUR 58.50, total EUR 118.50; already paid EUR 0.00",
                      item["hold_impact"])
        self.assertIn("SYN-COST-3 (claimed 40.00 EUR) is unresolved", item["hold_impact"])

    def test_synthetic_never_in_source_runs(self):
        runs = os.path.join(ROOT, "artifacts", "runs")
        for r in os.listdir(runs) if os.path.isdir(runs) else []:
            p = os.path.join(runs, r, "claims.csv")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    self.assertNotIn("SYN-", f.read(), r)


if __name__ == "__main__":
    unittest.main()
