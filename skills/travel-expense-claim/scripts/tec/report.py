"""Operations handoff report (report.md)."""
from collections import Counter, defaultdict

from .engine import _eur, _natural

CLOSED = ("closed-reimbursed", "closed-no-payment", "rejected", "withdrawn")


def _m(c):
    return "—" if c is None else _eur(c)


def _src_table(sources):
    rows = ["| source_id | status | completeness | locator | observed_at (UTC) | version | sha256 | path |",
            "|---|---|---|---|---|---|---|---|"]
    for f in sources["files"]:
        rows.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            f["source_id"], f["status"] + (" (" + f["error"] + ")" if f["error"] else ""), f.get("completeness"),
            f["locator"], f["observed_at"], f["version"] or "null", (f["sha256"] or "null")[:16] + ("…" if f["sha256"] else ""),
            f["path"] or "null"))
    return "\n".join(rows)


def failure_report(meta, sources):
    return "\n".join([
        "# Travel expense claim run `%s` — FAILED" % meta["run_id"], "",
        "No batch was processed: %s." % meta["failure"], "",
        "Nothing was inferred, substituted from earlier downloads, or paraphrased. Retry with `run` once the native "
        "locations are reachable, or use `replay --from <run>` to reprocess an earlier run's retained inputs (labelled offline replay).", "",
        "## Source access", "", _src_table(sources), "",
        "## Limitations", ""] + ["- " + x for x in sources["limitations"]]) + "\n"


def build(meta, sources, snaps, eng, rq, ds):
    final = snaps[-1]["snapshot"]
    claims = final["claims"]
    by_status = Counter(c["status"] for c in claims)
    out = []
    w = out.append
    w("# Travel expense claim — operations handoff (`%s`)" % meta["run_id"])
    w("")
    w("- **Mode:** %s%s" % (sources["mode"], " of `%s` (no fresh access claimed)" % meta["replay_of"] if meta["replay_of"] else ""))
    w("- **Outcome:** %s · **Case clock:** %s (frozen; arrival batch decides availability)" % (meta["outcome"], sources["case_clock"]))
    w("- **Code revision:** `%s` · **Policy:** %s (Notion block version %s)" % (
        meta["code_revision"], ds["policy"]["policy_revision"], ds["policy"]["version"]))
    w("- **Sealed snapshots:** " + ", ".join("[%s](%s) `%s…`" % (s["path"].split("/")[-1], s["path"], s["sha256"][:12]) for s in snaps))
    w("- **Outputs:** [claims.csv](claims.csv) · [sources.json](sources.json) · [queue/items.json](queue/items.json) · "
      "[queue/events.jsonl](queue/events.jsonl) · [queue/drafts/](queue/drafts/)")
    w("")
    w("People keep every approval, exception and payment decision. This run only prepared local work from supplied scenario "
      "facts: it sent nothing, booked nothing and moved no money.")
    w("")

    # ---------------------------------------------------------------- summary
    paid = sum(c["paid_cents"] for c in claims)
    reimbursed = [c for c in claims if c["status"] == "closed-reimbursed"]
    open_claims = [c for c in claims if c["status"] not in CLOSED]
    w("## 1. Position after %s" % final["batch_id"])
    w("")
    w("| Status | Claims |")
    w("|---|---|")
    for s in ("closed-reimbursed", "closed-no-payment", "rejected", "withdrawn", "ready", "pending", "held"):
        w("| %s | %d |" % (s, by_status.get(s, 0)))
    w("| **total** | **%d** |" % len(claims))
    w("")
    w("- Net confirmed payments across all claims: **%s** (%d admitted Finance events)." % (_eur(paid), len(final["admitted_event_ids"])))
    w("- Reimbursed and closed: %d claims, %s." % (len(reimbursed), _eur(sum(c["paid_cents"] for c in reimbursed))))
    known_open = [c for c in open_claims if c["balance_cents"] is not None]
    w("- Open claims: %d. Known outstanding balance on them: %s; %d open claims have an unknown entitlement (blank money)." % (
        len(open_claims), _eur(sum(c["balance_cents"] for c in known_open)), len(open_claims) - len(known_open)))
    neg = [c for c in claims if c["balance_cents"] is not None and c["balance_cents"] < 0]
    if neg:
        w("- Overpayments still owed back or unresolved: " + ", ".join("%s %s" % (c["claim_id"], _eur(c["balance_cents"])) for c in neg) + ".")
    w("")

    # ---------------------------------------------------------------- unresolved work
    w("## 2. Unresolved work (owner, reason, evidence or action needed)")
    w("")
    issues = {i["record_id"]: i for i in final["issues"]}
    w("| Claim | Rev | Trip | Status | Allowed | Paid | Balance | Next owner | Reason | Next action |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for c in sorted(open_claims, key=lambda c: (c["status"], _natural(c["claim_id"]))):
        acts = sorted({i["resolution_needed"] for k, i in issues.items() if k.startswith("ISS-%s-r%d-" % (c["claim_id"], c["revision"]))})
        if not acts and c["status"] == "pending":
            acts = ["%s responds (review or Finance outcome)" % c["next_owner"]]
        w("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            c["claim_id"], c["revision"], c["trip_id"], c["status"], _m(c["allowed_cents"]), _eur(c["paid_cents"]),
            _m(c["balance_cents"]), c["next_owner"] or "—", c["reason"].replace("|", "/"), "; ".join(acts).replace("|", "/")))
    w("")

    # ---------------------------------------------------------------- cancellations
    w("## 3. Trip and permit cancellation processes")
    w("")
    w("Cancellation processes are tracked separately from claims. A process with no claim is reported here and never turned into a claim row.")
    w("")
    w("| Cancellation | Target | Trip / permit | Status | Requested | Effective | Affected claims | Original requests | Financial status | Next owner | Events |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in final["travel_cancellations"]:
        w("| %s | %s | %s r%s / %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            t["cancellation_id"], t["target_type"], t["trip_id"], t["trip_revision"],
            "%s r%s" % (t["permit_id"], t["permit_revision"]) if t["permit_id"] else "no permit", t["status"],
            t["requested_at"], t["effective_at"] or "—", ", ".join(t["affected_claim_ids"]) or "none (no claim)",
            ", ".join(t["original_request_ids"]) or "—", t["financial_status"], t["next_owner"] or "—",
            ", ".join(t["admitted_cancellation_event_ids"])))
    w("")

    # ---------------------------------------------------------------- queue
    w("## 4. Repair queue")
    w("")
    w("Grouping: by responsible person, then subject. There is one item per missing fact or return reason. Each item keeps its "
      "subject, revision, trip/permit revision, source locators, owner, next action, and the run/batch where it was opened and last changed. "
      "The history is append-only ([events.jsonl](queue/events.jsonl)). An item is marked satisfied only when the inputs that "
      "close that fact arrive. If a response from an owner covers only part of what was asked, the event is logged as "
      "`partial-response` and the unanswered items stay open. Drafts in [queue/drafts/](queue/drafts/) are local and unsent.")
    w("")
    by_owner = defaultdict(list)
    for it in rq.open_items():
        by_owner[it["owner"]].append(it)
    w("### Open items after %s" % final["batch_id"])
    w("")
    w("| Owner | Item | Subject | Rev | Trip/permit rev | Missing fact or return reason | Next action | Opened | Last changed |")
    w("|---|---|---|---|---|---|---|---|---|")
    for owner in sorted(by_owner):
        for it in by_owner[owner]:
            w("| %s | `%s` | %s %s%s | %s | %s r%s%s | %s | %s | %s | %s |" % (
                owner, it["item_id"], it["subject_type"], it["subject_id"], (" " + it["cost_id"]) if it["cost_id"] else "",
                it["revision"] if it["revision"] is not None else "—", it["trip_id"], it["trip_revision"],
                (" / %s r%s" % (it["permit_id"], it["permit_revision"])) if it["permit_id"] else "",
                it["missing_fact"].replace("|", "/"), it["next_action"].replace("|", "/"),
                it["opened"]["batch_id"], it["last_changed"]["batch_id"]))
    w("")
    w("### Queue updates by batch")
    w("")
    for s in snaps:
        evs = s["queue_events"]
        cnt = Counter(e["event"] for e in evs)
        w("**%s / %s** — %s" % (meta["run_id"], "batch-%d" % s["batch"], ", ".join("%s %d" % kv for kv in sorted(cnt.items())) or "no change"))
        w("")
        for e in evs:
            if e["event"] == "opened" and s["batch"] == snaps[0]["batch"]:
                continue  # the initial backlog is listed in the open-items table / events.jsonl
            if e["event"] == "partial-response":
                w("- `partial-response` %s %s r%s: satisfied %s; still open %s" % (
                    e["owner"], e["subject"], e["revision"], ", ".join(e["satisfied"]), ", ".join(e["still_open"])))
            else:
                extra = ""
                if e.get("superseded_by"):
                    extra = " → replaced by `%s`" % e["superseded_by"]
                if e.get("supersedes"):
                    extra = " (replaces `%s`)" % e["supersedes"]
                ev = e.get("evidence")
                w("- `%s` `%s` (%s)%s%s" % (e["event"], e["item_id"], e.get("owner"), extra,
                                          ("; evidence: " + ", ".join(sorted(set(ev))[:4])) if ev else ""))
        if s["batch"] == snaps[0]["batch"]:
            w("- %d items opened (initial backlog; see table above and events.jsonl)" % cnt.get("opened", 0))
        w("")

    # ---------------------------------------------------------------- batch history
    w("## 5. Significant changes by batch")
    w("")
    prev = {}
    for s in snaps:
        snap = s["snapshot"]
        w("### batch-%d — `%s` (sha256 `%s…`, predecessor %s)" % (
            s["batch"], s["path"], s["sha256"][:16], ("`%s`" % snap["predecessor"]["path"]) if snap["predecessor"] else "none"))
        w("")
        cnt = Counter(c["status"] for c in snap["claims"])
        w("Claims known: %d (%s). Admitted Finance events: %d. Open issues: %d." % (
            len(snap["claims"]), ", ".join("%s %d" % kv for kv in sorted(cnt.items())), len(snap["admitted_event_ids"]), len(snap["issues"])))
        w("")
        trans = []
        for c in snap["claims"]:
            p = prev.get(c["claim_id"])
            if p is None and s is not snaps[0]:
                trans.append("%s new r%d → %s" % (c["claim_id"], c["revision"], c["status"]))
            elif p and (p["status"], p["revision"], p["paid_cents"], p["allowed_cents"]) != (c["status"], c["revision"], c["paid_cents"], c["allowed_cents"]):
                trans.append("%s r%d %s %s/%s → r%d %s %s/%s" % (
                    c["claim_id"], p["revision"], p["status"], _m(p["paid_cents"]), _m(p["allowed_cents"]),
                    c["revision"], c["status"], _m(c["paid_cents"]), _m(c["allowed_cents"])))
        if trans:
            w("State transitions (paid/allowed):")
            w("")
            for t in trans:
                w("- " + t)
            w("")
        notable = [x for x in s["log"] if x["kind"] not in ("claim",) and not (x["kind"] == "finance" and s is snaps[0])
                   and not (x["kind"] == "request" and s is snaps[0])]
        if notable:
            w("Events consumed:")
            w("")
            for x in notable:
                w("- [%s] %s: %s%s" % (x["kind"], x["subject"], x["text"], (" — " + ", ".join(x["refs"])) if x["refs"] else ""))
            w("")
        prev = {c["claim_id"]: c for c in snap["claims"]}

    # ---------------------------------------------------------------- integrity
    w("## 6. Replays, rejected imports and unmatched events")
    w("")
    if eng.replays:
        for kind, ident, b in eng.replays:
            w("- Exact redelivery of %s `%s` in batch-%d: no effect. Event identity and money were preserved." % (kind, ident, b))
    else:
        w("- No redeliveries observed.")
    for x in eng.rejected_imports:
        w("- Review reply `%s` (batch-%d) not admitted: %s" % (x["decision"]["decision_id"], x["batch"], x["reason"]))
    for x in eng.fin_rejected:
        w("- Finance event `%s` (batch-%d) not admitted: %s" % (x["event"]["event_id"], x["batch"], x["reason"]))
    for x in eng.fin_waiting:
        w("- Finance event `%s` remains unmatched (no proposed request `%s`)." % (x["event_id"], x["request_id"]))
    for x in eng.canc_rejected:
        w("- Cancellation delivery `%s` (batch-%d) not admitted: %s" % (x["event"]["event_id"], x["batch"], x["reason"]))
    for x in eng.canc_waiting:
        w("- Cancellation confirmation `%s` waits for its request `%s`." % (x["event_id"], x["initiation_ref"]))
    if not (eng.rejected_imports or eng.fin_rejected or eng.fin_waiting or eng.canc_rejected or eng.canc_waiting):
        w("- No review, Finance or cancellation delivery was rejected or left unmatched.")
    w("")

    # ---------------------------------------------------------------- budget
    w("## 7. Budget ledger context (for reviewers; not an approval)")
    w("")
    alloc = sum(b["amount"] for b in ds["budget"] if b["type"] == "allocation")
    settled_prior = sum(b["settled"] - b["refunded"] for b in ds["budget"] if b["type"] == "obligation")
    remaining_prior = sum(b["amount"] - b["settled"] for b in ds["budget"] if b["type"] == "obligation")
    accepted = sum(r["amount_cents"] for r in final["requests"] if r["status"] in ("accepted", "dispatched", "settled", "cancel-pending"))
    w("Allocation %s − prior net settled %s − prior remaining commitments %s − this workflow's accepted requests %s = **%s** "
      "available (Consulting / Client-A / 2026; each commitment's settled portion is subtracted once)." % (
          _eur(int(alloc * 100)), _eur(int(settled_prior * 100)), _eur(int(remaining_prior * 100)), _eur(accepted),
          _eur(int((alloc - settled_prior - remaining_prior) * 100) - accepted)))
    w("")

    # ---------------------------------------------------------------- sources
    w("## 8. Sources and limitations")
    w("")
    w("`sources.json` source_version `%s`." % sources["source_version"])
    w("")
    w(_src_table(sources))
    w("")
    for x in sources["limitations"]:
        w("- " + x)
    w("")
    w("Verify this run with `.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py verify %s`." % meta["run_id"])
    w("")
    return "\n".join(out)
