"""Independent checks over a retained run. Each check returns (name, ok, detail)."""
import csv
import hashlib
import json


def _jload(path):
    """json.load on a path, closing the file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
import os
from collections import defaultdict

from . import capture, dataset
from .engine import cents
from .run import claims_csv

FIVE_URLS = {s["url"] for s in capture.SOURCES}


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify(run_dir, schema_path, compare_dir=None):
    res = []

    def check(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    sources = _jload(os.path.join(run_dir, "sources.json"))
    meta = _jload(os.path.join(run_dir, "run.json"))
    files = sources["files"]
    check("sources.json covers the five native URLs", {f["url"] for f in files} == FIVE_URLS,
          sorted(FIVE_URLS - {f["url"] for f in files}))
    check("source_ids unique", len({f["source_id"] for f in files}) == len(files))
    bad = [f["source_id"] for f in files if f["status"] == "read" and (not f["path"] or _sha(os.path.join(run_dir, f["path"])) != f["sha256"])]
    check("read pieces bound to retained bytes (sha256)", not bad, bad)
    bad = [f["source_id"] for f in files if f["status"] == "unavailable" and (f["path"] or f["sha256"] or f["version"] or not f["error"])]
    check("unavailable pieces carry error and null path/hash/version", not bad, bad)
    check("every piece has url, locator and UTC observed_at",
          all(f["url"] and f["locator"] and f["observed_at"].endswith("Z") for f in files))
    if sources["mode"] == "offline-replay":
        check("replay labelled and linked to its source run", sources["replay_of"] and all(f.get("replayed_from_run") for f in files))

    if meta["outcome"] == "failure":
        check("failed run produced no snapshots", not os.listdir(os.path.join(run_dir, "batches")))
        return res

    ds = dataset.load(run_dir, files)
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(_jload(schema_path), format_checker=FormatChecker())
    src_sha = _sha(os.path.join(run_dir, "sources.json"))
    fin = {}
    for e in sorted(ds["finance"], key=lambda e: e["batch"]):
        fin.setdefault(e["event_id"], e)  # first delivery decides availability; redeliveries are no-ops
    canc_ids = {e["event_id"] for e in ds["cancellations"]}
    reviews = {r["decision_id"]: r for r in ds["reviews"]}
    claim_batch = {(c["claim_id"], c["revision"]): c["arrival_batch"] for c in ds["claims"]}

    prev, snaps = None, []
    for b in meta["batches"]:
        path = os.path.join(run_dir, b["path"])
        snap = _jload(path)
        bn = int(b["batch_id"].split("-")[1])
        errs = sorted(validator.iter_errors(snap), key=lambda e: list(e.path))
        check("%s conforms to %s" % (b["batch_id"], snap.get("schema_version")), not errs, [e.message for e in errs[:3]])
        check("%s sha256 matches run.json" % b["batch_id"], _sha(path) == b["sha256"])
        check("%s predecessor binding" % b["batch_id"], snap["predecessor"] == prev,
              "expected %s got %s" % (prev, snap["predecessor"]))
        check("%s source binding" % b["batch_id"], snap["source_binding"] == {"path": "sources.json", "sha256": src_sha})
        ids = snap["admitted_event_ids"]
        check("%s admitted_event_ids are unique Finance activity IDs" % b["batch_id"],
              len(ids) == len(set(ids)) and all(i in fin and i not in canc_ids for i in ids))
        check("%s no Finance event from a later batch" % b["batch_id"], all(fin[i]["batch"] <= bn for i in ids),
              [i for i in ids if fin[i]["batch"] > bn])
        cev = [i for t in snap["travel_cancellations"] for i in t["admitted_cancellation_event_ids"]]
        check("%s cancellation event IDs only from Travel cancellations, arrived by this batch" % b["batch_id"],
              all(i in canc_ids and i not in fin for i in cev) and all(
                  next(e for e in ds["cancellations"] if e["event_id"] == i)["batch"] <= bn for i in cev))
        iss = {i["record_id"] for i in snap["issues"]}
        check("%s issue_record_ids resolve to issues[]" % b["batch_id"],
              all(set(t["issue_record_ids"]) <= iss for t in snap["travel_cancellations"]))
        check("%s claim revisions available by this batch" % b["batch_id"],
              all(claim_batch.get((c["claim_id"], c["revision"]), 99) <= bn for c in snap["claims"]))
        dec_bad = []
        for c in snap["claims"]:
            for d in c["decision_ids"]:
                r = reviews.get(d)
                if not r or r["subject_id"] != c["claim_id"] or r["revision"] != c["revision"] or r["batch"] > bn:
                    dec_bad.append((c["claim_id"], d))
        check("%s decision_ids match exact claim subject/revision and batch availability" % b["batch_id"], not dec_bad, dec_bad[:5])

        paid = defaultdict(int)
        req_claim = {r["request_id"]: r["claim_id"] for r in snap["requests"]}
        for i in ids:
            e = fin[i]
            if e["type"] == "settled":
                paid[req_claim[e["request_id"]]] += cents(e["amount"])
            elif e["type"] == "refund":
                paid[req_claim[e["request_id"]]] -= cents(e["amount"])
        money_bad = [c["claim_id"] for c in snap["claims"] if c["paid_cents"] != paid.get(c["claim_id"], 0)]
        check("%s paid_cents recomputed from admitted settled minus refunds" % b["batch_id"], not money_bad, money_bad)
        bal_bad = [c["claim_id"] for c in snap["claims"] if c["balance_cents"] != (
            None if c["allowed_cents"] is None else c["allowed_cents"] - c["paid_cents"])]
        check("%s balance_cents = allowed_cents - paid_cents (null when unknown)" % b["batch_id"], not bal_bad, bal_bad)
        sum_bad = [c["claim_id"] for c in snap["claims"] if c["allowed_cents"] is not None and c["status"] not in ("withdrawn", "rejected")
                   and c["allowed_cents"] != sum(l["allowed_cents"] for l in c["lines"])]
        check("%s claim allowed_cents = sum of line allowed_cents" % b["batch_id"], not sum_bad, sum_bad)
        closed_bad = [c["claim_id"] for c in snap["claims"] if c["status"] == "closed-reimbursed" and (
            c["balance_cents"] != 0 or c["paid_cents"] <= 0 or any(i.startswith("ISS-%s-r%d-" % (c["claim_id"], c["revision"])) for i in iss))]
        check("%s closed-reimbursed implies zero balance, payment and no open issue" % b["batch_id"], not closed_bad, closed_bad)
        held_bad = [c["claim_id"] for c in snap["claims"] if c["status"] == "held"
                    and not any(i.startswith("ISS-%s-" % c["claim_id"]) for i in iss)]
        check("%s every held claim has an owned issue" % b["batch_id"], not held_bad, held_bad)
        snaps.append(snap)
        prev = {"path": b["path"], "sha256": b["sha256"]}

    with open(os.path.join(run_dir, "claims.csv"), encoding="utf-8") as f:
        check("claims.csv equals the final snapshot", f.read() == claims_csv(snaps[-1]))
    with open(os.path.join(run_dir, "claims.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    check("claims.csv one row per claim", len(rows) == len({r["claim_id"] for r in rows}) == len(snaps[-1]["claims"]))

    with open(os.path.join(run_dir, "queue", "events.jsonl"), encoding="utf-8") as f:
        events = [json.loads(l) for l in f]
    check("queue events append-only sequence", [e["seq"] for e in events] == list(range(1, len(events) + 1)))
    check("queue events carry run and batch references",
          all(e["run_id"] == meta["run_id"] and e["batch_id"].startswith("batch-") for e in events))
    items = {i["item_id"]: i for i in _jload(os.path.join(run_dir, "queue", "items.json"))}
    open_items = {i["issue_record_id"] for i in items.values() if i["status"] == "open"}
    final_issues = {i["record_id"] for i in snaps[-1]["issues"]}
    check("open queue items == open issues in the final snapshot", open_items == final_issues,
          sorted(open_items ^ final_issues)[:5])
    req_fields = ("subject_type", "subject_id", "revision", "trip_id", "trip_revision", "source_ids", "missing_fact",
                  "owner", "next_action", "status", "opened", "last_changed")
    check("queue items carry subject, revision, source, fact, owner, action, run/batch refs",
          all(all(k in i for k in req_fields) and i["owner"] and i["source_ids"] for i in items.values()))
    link_bad = [k for k, i in items.items() if i.get("supersedes") and items[i["supersedes"]]["superseded_by"] != k]
    check("superseded/replacement links are symmetric", not link_bad, link_bad)

    with open(os.path.join(run_dir, "report.md"), encoding="utf-8") as f:
        report = f.read()
    missing = [c["claim_id"] for c in snaps[-1]["claims"] if c["status"] in ("held", "pending", "ready") and "| %s |" % c["claim_id"] not in report]
    check("report lists every open claim", not missing, missing)
    check("report lists every cancellation process", all(t["cancellation_id"] in report for t in snaps[-1]["travel_cancellations"]))

    if compare_dir:
        other = _jload(os.path.join(compare_dir, "run.json"))
        same = len(other["batches"]) == len(meta["batches"])
        diffs = []
        for a, b in zip(meta["batches"], other["batches"]):
            x = _strip(_jload(os.path.join(run_dir, a["path"])))
            y = _strip(_jload(os.path.join(compare_dir, b["path"])))
            if x != y:
                diffs.append(a["batch_id"])
        check("replay equivalence with %s (claims, requests, money, event and obligation identity)" % other["run_id"],
              same and not diffs, diffs)
    return res


def _strip(snap):
    s = dict(snap)
    for k in ("run_id", "source_binding", "predecessor"):
        s.pop(k)
    return s
