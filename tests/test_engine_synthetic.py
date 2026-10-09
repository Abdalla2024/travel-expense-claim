"""Engine branch tests on a SYNTHETIC in-memory dataset (SYN-* identifiers).

These isolated inputs exercise validation branches the supplied scenario does not
contain (wrong reviewer, stale revision, conflicting replay, orphan confirmation,
refund over the unrecovered amount). They are not scenario history and never
replace the primary run, which tests/test_primary_run.py checks.
"""
import copy
import datetime as dt
import os
import sys
import unittest
from collections import defaultdict
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))

from tec.engine import Engine  # noqa: E402

UTC = dt.timezone.utc
D = dt.date(2026, 9, 1)


def t(day, hour=12):
    return dt.datetime(2026, 9, day, hour, tzinfo=UTC)


def base():
    people = {"SYN-E1": {"Employee ID": "SYN-E1", "Payee ID": "SYN-E1", "Administration reviewer": "SYN-ADM",
                         "Budget owner": "SYN-BO", "Supervisor": "SYN-SUP", "Director": "SYN-DIR", "Finance officer": "SYN-FIN"}}
    trips = {"SYN-T1": {"trip_id": "SYN-T1", "employee": "SYN-E1", "destination": "NL", "international": False,
                        "start": dt.date(2026, 9, 2), "end": dt.date(2026, 9, 5), "commitment": D, "estimate": Decimal("100"),
                        "permit_id": None, "trip_revision": 1, "permit_revision": None, "ref": "syn#trip"}}
    claim = {"source_id": "synthetic", "locator": "c1", "claim_id": "SYN-C1", "revision": 1, "arrival_batch": 1,
             "employee": "SYN-E1", "trip_id": "SYN-T1", "trip_revision": 1, "submitted": D, "binder_status": "submitted",
             "claim_reason": "synthetic", "related": [], "exception": None,
             "lines": [{"line": 1, "cost_id": "SYN-COST-1", "receipt_ref": "SYN-R1", "first_submitted": D,
                        "amount": Decimal("100.00"), "amount_text": "100.00", "currency": "EUR"}]}
    receipts = defaultdict(list, {"SYN-COST-1": [{"source_id": "synthetic", "locator": "r1", "receipt_ref": "SYN-R1",
                                                  "cost_id": "SYN-COST-1", "employee": "SYN-E1", "trip_id": "SYN-T1",
                                                  "category": "transport", "currency": "EUR", "gross": Decimal("100.00"),
                                                  "units": "1", "description": "x", "issued": "2026-09-01"}]})
    merchant = defaultdict(list, {"SYN-COST-1": [{"txn": "SYN-M1", "cost_id": "SYN-COST-1", "employee": "SYN-E1",
                                                  "trip_id": "SYN-T1", "currency": "EUR", "gross": Decimal("100.00"), "paid": D,
                                                  "status": "settled", "receipt_ref": "SYN-R1", "ref": "syn#m1"}]})
    return {"policy": {"policy_revision": "POL-2026.2", "case_clock_date": "2026-11-15"}, "people": people, "trips": trips,
            "merchant": merchant, "fx": [], "caps": [], "budget": [], "reviews": [], "finance": [], "cancellations": [],
            "claims": [claim], "receipts": receipts, "receipts_available": True, "limits": []}


def review(did, role, batch=1, rev=1, reviewer=None, outcome="approve", cost_ids=("SYN-COST-1",), tcs=()):
    who = reviewer or {"administration": "SYN-ADM", "budget_owner": "SYN-BO", "supervisor": "SYN-SUP", "director": "SYN-DIR"}[role]
    return {"decision_id": did, "batch": batch, "subject_type": "claim", "subject_id": "SYN-C1", "revision": rev,
            "roles": [role], "reviewer": who, "outcome": outcome, "reason": "r", "repair": None, "source_revisions": [],
            "time": t(3), "ref": "syn#" + did,
            "packet": {"employee": "SYN-E1", "trip_id": "SYN-T1", "permit_id": None, "cost_ids": list(cost_ids),
                       "policy_revision": "POL-2026.2", "estimate": None, "trip_revision": 1, "permit_revision": None,
                       "cancellation_ids": list(tcs), "ref": "syn#p"}}


def fin(eid, typ, batch, amount=None, obligation=None, orig=None, day=11, actor="SYN-FIN"):
    return {"event_id": eid, "batch": batch, "type": typ, "request_id": "REQ-SYN-C1", "claim_id": "SYN-C1", "actor": actor,
            "payee": "SYN-E1", "currency": "EUR", "amount": None if amount is None else Decimal(amount),
            "original_event_id": orig, "obligation": None if obligation is None else Decimal(obligation),
            "reason": "x", "time": t(day), "ref": "syn#" + eid}


def approvals(batch=1, rev=1, **kw):
    return [review("SYN-A%d" % rev, "administration", batch, rev, **kw), review("SYN-B%d" % rev, "budget_owner", batch, rev, **kw),
            review("SYN-S%d" % rev, "supervisor", batch, rev, **kw)]


def run(ds):
    out = {}
    eng = Engine(ds)
    eng.run(lambda b, st: out.__setitem__(b, copy.deepcopy(st)))
    return eng, out


class EngineBranches(unittest.TestCase):
    def test_ordinary_path(self):
        ds = base()
        ds["reviews"] = approvals()
        ds["finance"] = [fin("SYN-F1", "accepted", 1, obligation="100.00"), fin("SYN-F2", "settled", 2, amount="100.00", day=12)]
        eng, st = run(ds)
        self.assertEqual(st[1]["claims"]["SYN-C1"]["status"], "pending")
        self.assertEqual(st[2]["claims"]["SYN-C1"]["status"], "closed-reimbursed")
        self.assertEqual(st[2]["claims"]["SYN-C1"]["paid_cents"], 10000)

    def test_wrong_reviewer_and_stale_revision_rejected(self):
        ds = base()
        ds["reviews"] = approvals()[:2] + [review("SYN-S1", "supervisor", reviewer="SYN-BO")]
        eng, st = run(ds)
        self.assertEqual(st[1]["claims"]["SYN-C1"]["status"], "pending")
        self.assertIn("SYN-S1", [x["decision"]["decision_id"] for x in eng.rejected_imports])

        ds = base()
        c2 = copy.deepcopy(ds["claims"][0])
        c2.update(revision=2, arrival_batch=2, locator="c2")
        ds["claims"].append(c2)
        ds["reviews"] = [review("SYN-OLD", "administration", batch=2, rev=1)]
        eng, st = run(ds)
        self.assertIn("stale revision", eng.rejected_imports[0]["reason"])

    def test_director_threshold_strictly_above_1000(self):
        for amount, needs in (("1000.00", False), ("1000.01", True)):
            ds = base()
            ds["claims"][0]["lines"][0]["amount"] = Decimal(amount)
            ds["receipts"]["SYN-COST-1"][0]["gross"] = Decimal(amount)
            ds["merchant"]["SYN-COST-1"][0]["gross"] = Decimal(amount)
            ds["reviews"] = approvals()
            eng, st = run(ds)
            c = st[1]["claims"]["SYN-C1"]
            self.assertEqual(c["status"] == "pending" and c["next_owner"] == "SYN-DIR", needs, amount)

    def test_conflicting_replay_holds_without_erasing_money(self):
        ds = base()
        ds["reviews"] = approvals()
        ds["finance"] = [fin("SYN-F1", "accepted", 1, obligation="100.00"), fin("SYN-F2", "settled", 2, amount="60.00", day=12),
                         fin("SYN-F2", "settled", 3, amount="99.00", day=12)]
        eng, st = run(ds)
        c = st[3]["claims"]["SYN-C1"]
        self.assertEqual(c["paid_cents"], 6000)
        self.assertEqual(c["status"], "held")
        self.assertTrue(any(i["fact_code"].startswith("finance_event_rejected") for i in c["issues"]))

    def test_exact_replay_no_effect(self):
        ds = base()
        ds["reviews"] = approvals()
        ev = fin("SYN-F2", "settled", 2, amount="100.00", day=12)
        again = dict(ev, batch=4)
        ds["finance"] = [fin("SYN-F1", "accepted", 1, obligation="100.00"), ev, again]
        eng, st = run(ds)
        self.assertEqual(st[4]["claims"]["SYN-C1"]["paid_cents"], 10000)
        self.assertIn(("finance", "SYN-F2", 4), eng.replays)

    def test_refund_over_unrecovered_rejected_and_overpayment_needs_resolution(self):
        ds = base()
        ds["reviews"] = approvals()
        ds["finance"] = [fin("SYN-F1", "accepted", 1, obligation="100.00"), fin("SYN-F2", "settled", 2, amount="120.00", day=12),
                         fin("SYN-F3", "refund", 3, amount="130.00", orig="SYN-F2", day=13),
                         fin("SYN-F4", "refund", 3, amount="20.00", orig="SYN-F2", day=14),
                         fin("SYN-F5", "resolution", 4, obligation="100.00", day=15)]
        eng, st = run(ds)
        self.assertEqual(st[2]["claims"]["SYN-C1"]["status"], "held")
        self.assertEqual(st[2]["claims"]["SYN-C1"]["balance_cents"], -2000)
        self.assertIn("SYN-F3", [x["event"]["event_id"] for x in eng.fin_rejected])
        self.assertEqual(st[3]["claims"]["SYN-C1"]["status"], "held")  # paid matches, resolution still missing
        # Money and resolution now agree, but the rejected refund SYN-F3 stays visible for Finance (POL ¶9),
        # so the claim must not be forced closed.
        c4 = st[4]["claims"]["SYN-C1"]
        self.assertEqual((c4["paid_cents"], c4["balance_cents"], c4["status"]), (10000, 0, "held"))
        self.assertEqual([i["fact_code"] for i in c4["issues"]], ["finance_event_rejected:SYN-F3"])

    def test_orphan_confirmation_waits_and_wrong_confirmer_rejected(self):
        ds = base()
        ds["trips"]["SYN-T1"]["commitment"] = None
        ds["claims"] = []
        req = {"event_id": "SYN-TC-req", "cancellation_id": "SYN-TC", "action": "requested", "target_type": "trip",
               "trip_id": "SYN-T1", "trip_revision": 1, "permit_id": None, "permit_revision": None, "initiation_ref": None,
               "actor": "SYN-E1", "time": t(10, 9), "effective": None, "batch": 2, "reason": "x", "ref": "syn#req"}
        conf = dict(req, event_id="SYN-TC-conf", action="confirmed", initiation_ref="SYN-TC-req", actor="SYN-SUP",
                    time=t(10, 10), effective=t(10, 10), batch=1, ref="syn#conf")
        bad = dict(conf, event_id="SYN-TC-bad", actor="SYN-BO", batch=2, ref="syn#bad")
        ds["cancellations"] = [conf, req, bad]
        ds["reviews"] = [review("SYN-X", "administration", batch=2)]  # makes batch 2 exist without a claim
        ds["reviews"][0]["subject_id"] = "SYN-NONE"
        eng, st = run(ds)
        self.assertEqual(st[1]["cancellations"], {})          # confirmation alone establishes nothing
        tc = st[2]["cancellations"]["SYN-TC"]
        self.assertEqual(tc["status"], "confirmed")
        self.assertEqual(tc["financial_status"], "no-financial-effect")
        self.assertTrue(any("not the directory supervisor" in x["reason"] or "already" in x["reason"] for x in eng.canc_rejected))

    def test_pre_cancellation_approvals_do_not_authorize(self):
        ds = base()
        ds["reviews"] = approvals()
        ds["cancellations"] = [
            {"event_id": "SYN-TC-r", "cancellation_id": "SYN-TC", "action": "requested", "target_type": "trip", "trip_id": "SYN-T1",
             "trip_revision": 1, "permit_id": None, "permit_revision": None, "initiation_ref": None, "actor": "SYN-E1",
             "time": t(2, 8), "effective": None, "batch": 1, "reason": "x", "ref": "syn#r"},
            {"event_id": "SYN-TC-c", "cancellation_id": "SYN-TC", "action": "confirmed", "target_type": "trip", "trip_id": "SYN-T1",
             "trip_revision": 1, "permit_id": None, "permit_revision": None, "initiation_ref": "SYN-TC-r", "actor": "SYN-SUP",
             "time": t(2, 9), "effective": t(2, 9), "batch": 1, "reason": "x", "ref": "syn#c"}]
        eng, st = run(ds)
        c = st[1]["claims"]["SYN-C1"]
        self.assertEqual(c["status"], "held")
        self.assertTrue(any(i["fact_code"] == "travel_cancellation:SYN-TC" for i in c["issues"]))
        self.assertFalse(eng.requests)  # nothing proposed to Finance


if __name__ == "__main__":
    unittest.main()
