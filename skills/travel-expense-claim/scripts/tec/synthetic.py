"""Labelled synthetic scenarios: run the real engine and queue on SYN-* fixtures.

Output goes under artifacts/synthetic/<name>/, never artifacts/runs/, and every
file says SYNTHETIC. Nothing here is read from or presented as a native source.
"""
import datetime as dt
import json
import os
from collections import Counter, defaultdict
from decimal import Decimal

from . import routing
from .engine import Engine, _eur
from .repair_queue import RepairQueue

BANNER = ("SYNTHETIC SCENARIO — every identifier is SYN-*. These records are invented test inputs, not Alderbridge "
          "source data, approvals, replies or Finance decisions.")


def _d(s):
    return None if s is None else dt.date.fromisoformat(s)


def _t(s):
    return None if s is None else dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)


def _m(s):
    return None if s is None else Decimal(s)


def load(path):
    with open(path, encoding="utf-8") as f:
        fx = json.load(f)
    if "SYNTHETIC" not in fx.get("_label", ""):
        raise ValueError("fixture is not labelled SYNTHETIC")
    ids = json.dumps({k: v for k, v in fx.items() if k not in ("_label", "policy_revision", "case_clock_date")})
    for c in fx["claims"] + fx["trips"] + fx["people"]:
        for v in (c.get("claim_id"), c.get("trip_id"), c.get("Employee ID")):
            if v and not v.startswith("SYN-"):
                raise ValueError("non-SYN identifier %s in synthetic fixture" % v)
    ds = {"policy": {"policy_revision": fx["policy_revision"], "case_clock_date": fx["case_clock_date"]},
          "people": {p["Employee ID"]: dict(p, ref="synthetic#people:" + p["Employee ID"]) for p in fx["people"]},
          "trips": {}, "merchant": defaultdict(list), "receipts": defaultdict(list), "fx": [], "caps": [], "budget": [],
          "reviews": [], "finance": [], "cancellations": [], "claims": [], "receipts_available": True, "limits": [],
          "_fixture_sha_hint": len(ids)}
    for t in fx["trips"]:
        ds["trips"][t["trip_id"]] = dict(t, start=_d(t["start"]), end=_d(t["end"]), commitment=_d(t["commitment"]),
                                         estimate=_m(t["estimate"]), ref="synthetic#trip:" + t["trip_id"])
    for c in fx["claims"]:
        lines = [dict(l, first_submitted=_d(l["first_submitted"]), amount=_m(l["amount"]), amount_text=l["amount"])
                 for l in c["lines"]]
        ds["claims"].append(dict(c, submitted=_d(c["submitted"]), lines=lines, related=[], source_id="synthetic",
                                 locator="claim %s r%d" % (c["claim_id"], c["revision"])))
    for r in fx["receipts"]:
        ds["receipts"][r["cost_id"]].append(dict(r, gross=_m(r["gross"]), source_id="synthetic",
                                                 locator="receipt", description="synthetic"))
    for m in fx["merchant"]:
        ds["merchant"][m["cost_id"]].append(dict(m, gross=_m(m["gross"]), paid=_d(m["paid"]), ref="synthetic#merchant:" + m["txn"]))
    for f in fx["fx"]:
        ds["fx"].append(dict(f, date=_d(f["date"]), rate=_m(f["rate"]), ref="synthetic#fx:" + f["ref"]))
    for r in fx["reviews"]:
        claim = next(c for c in fx["claims"] if c["claim_id"] == r["subject_id"])
        ds["reviews"].append(dict(r, subject_type="claim", time=_t(r["time"]), source_revisions=[],
                                  affected_fields=["trip", "amount", "evidence"], ref="synthetic#review:" + r["decision_id"],
                                  packet={"employee": claim["employee"], "trip_id": claim["trip_id"], "permit_id": None,
                                          "cost_ids": [l["cost_id"] for l in claim["lines"]],
                                          "policy_revision": fx["policy_revision"], "estimate": None, "trip_revision": 1,
                                          "permit_revision": None, "cancellation_ids": [], "ref": "synthetic#packet"}))
    for e in fx["finance"]:
        ds["finance"].append(dict(e, amount=_m(e["amount"]), obligation=_m(e["obligation"]), time=_t(e["time"]),
                                  ref="synthetic#finance:%s@batch-%d" % (e["event_id"], e["batch"])))
    return ds


def run_demo(fixture, out_dir, name="partial-resumption"):
    if os.path.exists(out_dir):
        raise FileExistsError("refusing to overwrite retained synthetic output " + out_dir)
    ds = load(fixture)
    eng = Engine(ds)
    rq = RepairQueue("synthetic-" + name)
    per_batch = []

    def on_batch(b, state):
        issues = [i for st in state["claims"].values() for i in st["issues"]]
        inputs = defaultdict(list)
        for x in eng.batch_log[b]:
            inputs[x["subject"]].extend(x["refs"])
        for cid, c in eng.current.items():  # evidence rows that arrived this batch, attributed per cost
            for l in c["lines"]:
                key = (cid, l["cost_id"])
                for r in ds["merchant"].get(l["cost_id"], []) + ds["receipts"].get(l["cost_id"], []):
                    if r.get("batch") == b:
                        inputs[key].append(r.get("ref") or "synthetic#receipt:" + r["receipt_ref"])
                for r in ds["fx"]:
                    if r.get("batch") == b and r["currency"] == l["currency"]:
                        inputs[key].append(r["ref"])
        evs = rq.update(b, issues, {("claim", k): v["revision"] for k, v in eng.current.items()}, inputs)
        per_batch.append({"batch": b, "claims": {k: {x: v[x] for x in ("revision", "status", "allowed_cents", "paid_cents",
                                                                            "balance_cents", "next_owner", "reason", "lines", "decision_ids")}
                                                 for k, v in state["claims"].items()},
                          "queue_events": evs, "log": list(eng.batch_log[b])})

    eng.run(on_batch)
    os.makedirs(os.path.join(out_dir, "queue", "drafts"))
    with open(os.path.join(out_dir, "states.json"), "w", encoding="utf-8") as f:
        json.dump({"_label": BANNER, "fixture": "tests/fixtures/" + os.path.basename(fixture),
                   "batches": per_batch, "replays": eng.replays}, f, indent=2, sort_keys=True, default=str)
    with open(os.path.join(out_dir, "queue", "events.jsonl"), "w", encoding="utf-8") as f:
        for ev in rq.events:
            f.write(json.dumps(ev, sort_keys=True) + "\n")
    with open(os.path.join(out_dir, "queue", "items.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(rq.items.values(), key=lambda v: v["item_id"]), f, indent=2, sort_keys=True)
    for owner, md in rq.drafts().items():
        with open(os.path.join(out_dir, "queue", "drafts", owner + ".md"), "w", encoding="utf-8") as f:
            f.write("> " + BANNER + "\n\n" + md)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(_report(name, fixture, per_batch, rq, eng))
    return per_batch, rq, eng


def _report(name, fixture, per_batch, rq, eng):
    w = []
    w.append("# SYNTHETIC scenario: %s" % name)
    w.append("")
    w.append("> **" + BANNER + "**")
    w.append("")
    w.append("Fixture: `tests/fixtures/%s`. Produced with `tec_cli.py synthetic-demo`, which runs the same engine and "
             "repair queue as a source run. It is kept under `artifacts/synthetic/`, outside `artifacts/runs/`, so it is "
             "never mistaken for a source run." % os.path.basename(fixture))
    w.append("")
    w.append("What it shows (interview 4, 01:20):")
    w.append("")
    w.append("- **Partial reply:** a reply that answers part of a request resumes only the tasks it supports. The other tasks stay open.")
    w.append("- **Independent work:** an unrelated claim resumes on its own, as soon as its missing decision arrives.")
    w.append("- **No duplicates:** nothing is requested twice, and a redelivered Finance record has no effect.")
    w.append("- **Returned work:** a funding return goes to the budget owner, not the employee (interview 3, 10:48).")
    w.append("- **Stale approvals:** an approval given before late evidence arrived stops counting, and that review resumes (interview 3, 10:50).")
    w.append("")
    w.append("## Claim state by batch")
    w.append("")
    w.append("| Batch | Claim | Status | Allowed | Paid | Next owner | Lines (status, allowed) | Reason |")
    w.append("|---|---|---|---|---|---|---|---|")
    for pb in per_batch:
        for cid, c in sorted(pb["claims"].items()):
            lines = "; ".join("%s %s %s" % (l["cost_id"], l["status"], "—" if l["allowed_cents"] is None else _eur(l["allowed_cents"]))
                              for l in c["lines"])
            w.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
                pb["batch"], cid, c["status"], "—" if c["allowed_cents"] is None else _eur(c["allowed_cents"]),
                _eur(c["paid_cents"]), c["next_owner"] or "—", lines, c["reason"].replace("|", "/")))
    w.append("")
    w.append("## Replies counted for the current revision")
    w.append("")
    w.append("A reply admitted before evidence that arrived later stops counting (interview 3, 10:50), and the review resumes.")
    w.append("")
    for pb in per_batch:
        for cid, c in sorted(pb["claims"].items()):
            w.append("- batch-%d %s: %s" % (pb["batch"], cid, ", ".join(c["decision_ids"]) or "none"))
    w.append("")
    w.append("## Repair queue by batch")
    w.append("")
    for pb in per_batch:
        cnt = Counter(e["event"] for e in pb["queue_events"])
        w.append("**batch-%d** — %s" % (pb["batch"], ", ".join("%s %d" % kv for kv in sorted(cnt.items())) or "no change"))
        w.append("")
        for e in pb["queue_events"]:
            if e["event"] == "partial-response":
                w.append("- `partial-response` from %s on %s r%s: answered %s; still open %s" % (
                    e["owner"], e["subject"], e["revision"], ", ".join(e["satisfied"]), ", ".join(e["still_open"])))
            else:
                it = rq.items[e["item_id"]]
                w.append("- `%s` %s — %s (%s, owner %s)%s" % (
                    e["event"], e["item_id"], routing.label(it["fact_code"]), it["cost_id"] or it["subject_id"], it["owner"],
                    ("; evidence: " + ", ".join(sorted(set(e["evidence"])))) if e.get("evidence") else ""))
        w.append("")
    w.append("## Redeliveries")
    w.append("")
    for kind, ident, b in eng.replays:
        w.append("- Exact redelivery of %s `%s` in batch-%d: no effect." % (kind, ident, b))
    w.append("")
    return "\n".join(w) + "\n"
