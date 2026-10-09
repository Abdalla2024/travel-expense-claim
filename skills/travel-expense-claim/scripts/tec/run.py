"""Run orchestration: capture -> engine -> sealed snapshots, queue, claims.csv, report.md."""
import csv
import datetime as dt
import hashlib
import io
import json


def _jload(path):
    """json.load on a path, closing the file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
import os
import subprocess

from . import capture, dataset, engine, report
from .repair_queue import RepairQueue

SCHEMA_VERSION = "travel-claim-snapshot/2"


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_sealed(path, obj):
    if os.path.exists(path):
        raise FileExistsError("refusing to overwrite sealed file " + path)
    data = canonical(obj)
    with open(path, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def git_revision(repo):
    try:
        rev = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", repo, "status", "--porcelain", "--", "skills"], capture_output=True, text=True).stdout.strip()
        return rev + ("+uncommitted-skill-changes" if dirty else "")
    except Exception:
        return None


def new_run_id(prefix):
    return "%s-%s" % (prefix, dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))


def execute(runs_dir, run_id, mode, replay_of=None, repo=None):
    run_dir = os.path.join(runs_dir, run_id)
    if os.path.exists(run_dir):
        raise FileExistsError("run %s already exists; runs are never overwritten" % run_id)
    os.makedirs(os.path.join(run_dir, "batches"))
    started = capture.utcnow()

    if mode == "fresh":
        files = capture.flatten(capture.capture_fresh(run_dir))
    else:
        prior_dir = os.path.join(runs_dir, replay_of)
        prior = _jload(os.path.join(prior_dir, "sources.json"))
        files = capture.capture_replay(run_dir, prior_dir, prior)

    meta = {"run_id": run_id, "mode": mode, "replay_of": replay_of, "started_at": started,
            "code_revision": git_revision(repo or "."), "outcome": None}
    try:
        ds = dataset.load(run_dir, files)
        clock = "%s %s" % (ds["policy"]["case_clock_date"], ds["policy"]["case_clock_tz"])
    except dataset.SourceUnavailable as e:
        ds, clock = None, None
        meta["outcome"] = "failure"
        meta["failure"] = str(e)

    sources = {"run_id": run_id, "mode": "fresh-read" if mode == "fresh" else "offline-replay",
               "replay_of": replay_of, "source_version": _source_version(files), "case_clock": clock,
               "files": files, "limitations": _limitations(files, ds)}
    src_sha = write_sealed(os.path.join(run_dir, "sources.json"), sources)

    if ds is None:
        meta["finished_at"] = capture.utcnow()
        write_sealed(os.path.join(run_dir, "run.json"), meta)
        with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
            f.write(report.failure_report(meta, sources))
        return run_dir, meta

    eng = engine.Engine(ds)
    rq = RepairQueue(run_id)
    snaps, prev, history = [], None, []

    def on_batch(b, state):
        nonlocal prev
        snap, issues = build_snapshot(run_id, b, prev, src_sha, eng, state)
        rel = "batches/batch-%d.json" % b
        sha = write_sealed(os.path.join(run_dir, rel), snap)
        prev = {"path": rel, "sha256": sha}
        cur_revs = {("claim", cid): c["revision"] for cid, c in eng.current.items()}
        inputs = {}
        for x in eng.batch_log[b]:
            inputs.setdefault(x["subject"], []).extend(x["refs"])
            if x["subject"] in eng.canc:  # cancellation evidence also answers items on the affected claims
                r = eng.canc[x["subject"]]["request"]
                for cid, revs in eng.revs.items():
                    if any(c["trip_id"] == r["trip_id"] for c in revs):
                        inputs.setdefault(cid, []).extend(x["refs"])
        q_events = rq.update(b, issues, cur_revs, inputs)
        snaps.append({"batch": b, "path": rel, "sha256": sha, "snapshot": snap, "queue_events": q_events,
                      "log": list(eng.batch_log[b])})
        history.append(state)

    eng.run(on_batch)

    qdir = os.path.join(run_dir, "queue")
    os.makedirs(os.path.join(qdir, "drafts"))
    with open(os.path.join(qdir, "events.jsonl"), "w", encoding="utf-8") as f:
        for ev in rq.events:
            f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")
    with open(os.path.join(qdir, "items.json"), "wb") as f:
        f.write(canonical(sorted(rq.items.values(), key=lambda v: v["item_id"])))
    for owner, md in rq.drafts().items():
        with open(os.path.join(qdir, "drafts", "%s.md" % owner), "w", encoding="utf-8") as f:
            f.write(md)

    final = snaps[-1]["snapshot"]
    with open(os.path.join(run_dir, "claims.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(claims_csv(final))

    partial = [x for x in files if x["status"] != "read" or x.get("completeness") != "complete"]
    meta["outcome"] = "partial" if (partial or ds["limits"]) else "success"
    meta["batches"] = [{"batch_id": "batch-%d" % s["batch"], "path": s["path"], "sha256": s["sha256"]} for s in snaps]
    meta["finished_at"] = capture.utcnow()
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report.build(meta, sources, snaps, eng, rq, ds))
    write_sealed(os.path.join(run_dir, "run.json"), meta)
    return run_dir, meta


def build_snapshot(run_id, b, prev, src_sha, eng, state):
    claims, issues = [], {}
    for cid, st in state["claims"].items():
        claims.append({k: st[k] for k in ("claim_id", "revision", "trip_id", "trip_revision", "status", "lines",
                                          "allowed_cents", "paid_cents", "balance_cents", "decision_ids",
                                          "next_owner", "reason")})
        for i in st["issues"]:
            issues.setdefault(i["record_id"], i)
    cancs = []
    for k, cs in state["cancellations"].items():
        for i in cs["issues"]:
            issues.setdefault(i["record_id"], i)
        row = {x: cs[x] for x in cs if x != "issues"}
        row["issue_record_ids"] = sorted({i["record_id"] for i in cs["issues"]})
        cancs.append(row)
    reqs = [{k: r[k] for k in ("request_id", "claim_id", "revision", "amount_cents", "payee", "currency",
                               "status", "decision_ids")} for r in sorted(eng.requests.values(), key=lambda r: engine._natural(r["request_id"]))]
    snap = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "batch_id": "batch-%d" % b, "predecessor": prev,
            "source_binding": {"path": "sources.json", "sha256": src_sha}, "claims": claims, "requests": reqs,
            "travel_cancellations": cancs,
            "admitted_event_ids": [e["event_id"] for e in eng.fin_admitted],
            "issues": [{"record_id": i["record_id"], "reason": i["reason"], "owner": i["owner"] or "UNASSIGNED",
                        "resolution_needed": i["resolution_needed"]} for i in sorted(issues.values(), key=lambda i: i["record_id"])]}
    return snap, list(issues.values())


def claims_csv(snap):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["claim_id", "revision", "trip_id", "status", "allowed_cents", "paid_cents", "balance_cents", "next_owner", "reason"])
    for c in snap["claims"]:
        w.writerow([c["claim_id"], c["revision"], c["trip_id"], c["status"],
                    "" if c["allowed_cents"] is None else c["allowed_cents"], c["paid_cents"],
                    "" if c["balance_cents"] is None else c["balance_cents"], c["next_owner"] or "", c["reason"]])
    return buf.getvalue()


def _source_version(files):
    h = hashlib.sha256()
    for f in sorted(files, key=lambda f: f["source_id"]):
        h.update(("%s=%s;" % (f["source_id"], f["sha256"])).encode())
    return "content-set-sha256:" + h.hexdigest()


def _limitations(files, ds):
    out = [
        "Policy paragraph 1 says 'Read the fixed source manifest before each run' and cites LOG-0014. The operations lead "
        "confirmed in interview 2 (10:03, 10:11) that no such document exists and instructed us to proceed with the five "
        "native sources (10:12). The reference stays recorded here as unresolved.",
        "The workbook and the PDFs expose no native revision identifier (interview 2, 10:09). Their `version` is the HTTP "
        "validator the server returned, or null; identity is the retained bytes' sha256 plus retrieval time and locator.",
        "Google Sheets regenerates the xlsx on every export, so the workbook's byte sha256 differs between fresh runs "
        "even when no cell changed. Each workbook tab therefore also records `content_sha256`, a hash over its "
        "canonical cell text (notes, header, rows), to compare content across runs.",
        "DW-D-2 (cited by every review) is the business workflow contract whose rules are contained in the policy "
        "(interview 2, 10:08); it is not a separate fetchable source.",
    ]
    for f in files:
        if f["status"] != "read" or f.get("completeness") != "complete":
            out.append("%s: %s (%s)" % (f["source_id"], f.get("missing_scope") or f["status"], f.get("error")))
    if ds:
        out += ds["limits"]
    return out
