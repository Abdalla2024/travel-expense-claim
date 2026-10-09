"""Batch-by-batch claim, permit, cancellation and Finance reconciliation.

The engine is a deterministic simulation over arrival batches. Inside batch b
it consumes, in order: claim revisions, cancellation deliveries, review
replies, a readiness pass (which proposes requests), Finance activity, and a
final evaluation. Nothing from batch > b is visible while batch b is processed.

Rules are cited by policy paragraph (POL ¶n, counted in page order) or by the
interview session (INT1/INT2 with the export timestamp).
"""
import calendar
import datetime as dt
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from . import routing

ROLES = ["administration", "budget_owner", "supervisor", "director"]
DIRECTORY_COL = {"administration": "Administration reviewer", "budget_owner": "Budget owner",
                 "supervisor": "Supervisor", "director": "Director"}
UNCAPPED = {"transport", "conference"}
CAPPED = {"lodging": "night", "meals": "day"}
# Reviews that depend on the calculated amount (POL ¶6: administration checks rates/caps and the calculated amount;
# budget review is of the money; the director considers high spend). The supervisor's review does not.
AMOUNT_ROLES = {"administration", "budget_owner", "director"}
DIRECTOR_THRESHOLD_CENTS = 100000  # strictly above EUR 1,000.00 (POL ¶4, INT1 06:19)
LOCAL = ZoneInfo("Europe/Amsterdam")


def cents(eur):
    """Decimal EUR -> integer cents, half-up (POL ¶3)."""
    return int((eur * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def add_months_clamped(d, months):
    """Two calendar months after trip end, nonexistent day clamped to month end (POL ¶5)."""
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def local_date(ts):
    return ts.astimezone(LOCAL).date()


def iso(ts):
    return None if ts is None else ts.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


class Engine:
    def __init__(self, ds):
        self.ds = ds
        pol = ds["policy"]
        self.policy_revision = pol["policy_revision"]
        clock_day = dt.date.fromisoformat(pol["case_clock_date"])
        # Business timestamps may not exceed the end of the case-clock date (INT2 10:05).
        self.clock_end = dt.datetime.combine(clock_day + dt.timedelta(days=1), dt.time(), LOCAL)
        # Evidence rows with an arrival batch also open that batch, so a fact arriving on its own is processed
        # (INT4 01:20). Supplied register rows carry no batch and add nothing here.
        evidence_batches = {r["batch"] for rows in list(ds["merchant"].values()) + list(ds["receipts"].values())
                            for r in rows if r.get("batch")} | {r["batch"] for r in ds["fx"] + ds["caps"] if r.get("batch")}
        self.batches = sorted({c["arrival_batch"] for c in ds["claims"]} | {r["batch"] for r in ds["reviews"]}
                              | {f["batch"] for f in ds["finance"]} | {c["batch"] for c in ds["cancellations"]}
                              | evidence_batches)
        self.revs = defaultdict(list)          # claim_id -> revisions in arrival order
        self.current = {}                      # claim_id -> current revision record
        self.claim_arrival = {}                # (claim_id, revision) -> batch
        self.decisions = []                    # admitted, valid review replies
        self.rejected_imports = []             # invalid replies, kept visible (POL ¶7)
        self.requests = {}                     # request_id -> request
        self.fin_seen = {}                     # event_id -> payload key
        self.fin_admitted = []                 # admitted Finance events in admission order
        self.fin_waiting = []                  # events not yet matchable to a request
        self.fin_rejected = []                 # invalid or conflicting events
        self.canc_seen = {}
        self.canc = {}                         # cancellation_id -> process
        self.canc_waiting = []                 # confirmations whose request has not arrived
        self.canc_rejected = []
        self.replays = []                      # exact redeliveries (no effect)
        self.triggers = defaultdict(list)      # claim_id -> events that require Finance resolution
        self.batch = None
        self.batch_log = defaultdict(list)     # batch -> significant changes

    # ------------------------------------------------------------ helpers
    def log(self, kind, subject, text, refs=()):
        self.batch_log[self.batch].append({"kind": kind, "subject": subject, "text": text, "refs": list(refs)})

    def avail(self, rows):
        """Reference evidence available in the current batch. Supplied register tabs carry no arrival batch, so
        their rows count from batch 1; a row with a `batch` arrives in that batch (INT4 01:20: work resumes as
        soon as the missing evidence arrives)."""
        return [r for r in rows if (r.get("batch") or 1) <= self.batch]

    def directory(self, emp):
        return self.ds["people"].get(emp)

    def finance_officer(self, emp):
        p = self.directory(emp)
        return p and p["Finance officer"]

    # ------------------------------------------------------------ batch driver
    def run(self, on_batch):
        for b in self.batches:
            self.batch = b
            self._claims(b)
            self._cancellations(b)
            self._reviews(b)
            self._evaluate_all(propose=True)
            self._finance(b)
            state = self._evaluate_all(propose=False)
            on_batch(b, state)

    # ------------------------------------------------------------ 1. claim revisions
    def _claims(self, b):
        for c in [c for c in self.ds["claims"] if c["arrival_batch"] == b]:
            cid, prev = c["claim_id"], self.current.get(c["claim_id"])
            if prev and c["revision"] <= prev["revision"]:
                same = [r for r in self.revs[cid] if r["revision"] == c["revision"]]
                if same and _claim_key(same[0]) == _claim_key(c):
                    self.replays.append(("claim", "%s r%d" % (cid, c["revision"]), b))
                    continue
                self.log("claim-conflict", cid, "stale or conflicting revision r%d ignored" % c["revision"],
                         [c["source_id"] + "#" + c["locator"]])
                continue
            self.revs[cid].append(c)
            self.current[cid] = c
            self.claim_arrival[(cid, c["revision"])] = b
            if prev:
                live = [r for r in self._claim_requests(cid) if r["status"] in
                        ("accepted", "dispatched", "settled", "cancel-pending")]
                # Material correction after acceptance/dispatch needs explicit Finance resolution (POL ¶8, ¶11).
                if live:
                    self.triggers[cid].append({"kind": "correction-after-acceptance", "batch": b, "time": None,
                                               "ref": "%s r%d" % (cid, c["revision"])})
                self.log("revision", cid, "r%d -> r%d (%s)" % (prev["revision"], c["revision"], c["claim_reason"]),
                         [c["source_id"] + "#" + c["locator"]])
            else:
                self.log("claim", cid, "r%d received" % c["revision"], [c["source_id"] + "#" + c["locator"]])

    # ------------------------------------------------------------ 2. cancellations
    def _cancellations(self, b):
        todo = sorted([e for e in self.ds["cancellations"] if e["batch"] == b], key=lambda e: (e["time"], e["event_id"]))
        for e in todo:
            key = _payload_key(e)
            if e["event_id"] in self.canc_seen:
                if self.canc_seen[e["event_id"]] == key:
                    self.replays.append(("cancellation", e["event_id"], b))
                    self.log("replay", e["cancellation_id"], "exact redelivery of %s: no effect" % e["event_id"], [e["ref"]])
                else:
                    self._canc_reject(e, "conflicting payload for an admitted event ID", conflict=True)
                continue
            self.canc_seen[e["event_id"]] = key
            if e["action"] == "requested":
                self._canc_request(e)
            elif e["action"] == "confirmed":
                self.canc_waiting.append(e)
            else:
                self._canc_reject(e, "unknown action %r" % e["action"])
        still = []
        for e in self.canc_waiting:  # recheck unresolved references each batch (POL ¶14)
            p = self.canc.get(e["cancellation_id"])
            if not p or p["request"]["event_id"] != e["initiation_ref"]:
                still.append(e)
                continue
            self._canc_confirm(e, p)
        self.canc_waiting = still

    def _canc_target_errors(self, e):
        t = self.ds["trips"].get(e["trip_id"])
        if not t:
            return ["trip %s not in Trips" % e["trip_id"]]
        errs = []
        if e["trip_revision"] != t["trip_revision"]:
            errs.append("stale trip revision %s (current %s)" % (e["trip_revision"], t["trip_revision"]))
        if (e["permit_id"] or None) != (t["permit_id"] or None) or e["permit_revision"] != t["permit_revision"]:
            errs.append("permit %s r%s does not match trip permit %s r%s" % (
                e["permit_id"], e["permit_revision"], t["permit_id"], t["permit_revision"]))
        if e["target_type"] == "permit" and not t["permit_id"]:
            errs.append("permit cancellation for a trip without permit")
        if e["target_type"] not in ("trip", "permit"):
            errs.append("unknown target %r" % e["target_type"])
        if e["time"] is None or e["time"] >= self.clock_end:
            errs.append("activity time missing or beyond case clock")
        return errs

    def _canc_request(self, e):
        t = self.ds["trips"].get(e["trip_id"])
        errs = self._canc_target_errors(e)
        if t and e["actor"] != t["employee"]:
            errs.append("requester %s is not the trip employee %s" % (e["actor"], t["employee"]))
        if e["initiation_ref"] or e["effective"]:
            errs.append("a request carries no initiating reference or effective time")
        if e["cancellation_id"] in self.canc:
            errs.append("process already has an initiation")
        if errs:
            return self._canc_reject(e, "; ".join(errs), conflict=e["cancellation_id"] in self.canc)
        self.canc[e["cancellation_id"]] = {"request": e, "confirm": None, "batch_requested": self.batch,
                                           "batch_confirmed": None, "conflicts": []}
        self.log("cancellation", e["cancellation_id"], "%s cancellation requested for %s by %s" % (
            e["target_type"], e["trip_id"] if e["target_type"] == "trip" else e["permit_id"], e["actor"]), [e["ref"]])

    def _canc_confirm(self, e, p):
        t = self.ds["trips"].get(e["trip_id"])
        req = p["request"]
        errs = self._canc_target_errors(e)
        sup = t and self.directory(t["employee"]) and self.directory(t["employee"])["Supervisor"]
        if e["actor"] != sup:
            errs.append("confirmer %s is not the directory supervisor %s" % (e["actor"], sup))
        for k in ("target_type", "trip_id", "trip_revision", "permit_id", "permit_revision"):
            if e[k] != req[k]:
                errs.append("%s differs from the request" % k)
        if not (e["time"] and e["time"] > req["time"]):
            errs.append("confirmation is not strictly later than the request")
        if e["effective"] != e["time"]:
            errs.append("effective time must equal the confirmation occurrence time")
        if p["confirm"]:
            errs.append("process already confirmed")
        if errs:
            return self._canc_reject(e, "; ".join(errs), conflict=bool(p["confirm"]))
        p["confirm"], p["batch_confirmed"] = e, self.batch
        # A cancellation after acceptance/dispatch needs explicit Finance resolution before closure (POL ¶11, ¶16).
        for cid, revs in self.revs.items():
            if any(c["trip_id"] == e["trip_id"] and c["trip_revision"] == e["trip_revision"] for c in revs):
                if any(r["status"] in ("accepted", "dispatched", "settled", "cancel-pending") for r in self._claim_requests(cid)):
                    self.triggers[cid].append({"kind": "cancellation-after-acceptance", "batch": self.batch,
                                               "time": e["effective"], "ref": e["cancellation_id"]})
        self.log("cancellation", e["cancellation_id"], "confirmed by %s, effective %s" % (e["actor"], iso(e["effective"])), [e["ref"]])

    def _canc_reject(self, e, why, conflict=False):
        self.canc_rejected.append({"event": e, "reason": why, "batch": self.batch, "conflict": conflict})
        if conflict and e["cancellation_id"] in self.canc:
            self.canc[e["cancellation_id"]]["conflicts"].append(e["event_id"])
        self.log("cancellation-rejected", e["cancellation_id"], why, [e["ref"]])

    # ------------------------------------------------------------ 3. review replies
    def _reviews(self, b):
        for r in sorted([r for r in self.ds["reviews"] if r["batch"] == b], key=lambda r: (r["time"], r["decision_id"])):
            errs = self._review_errors(r)
            if errs:
                self.rejected_imports.append({"decision": r, "reason": "; ".join(errs), "batch": b})
                self.log("review-rejected", r["subject_id"], "%s rejected: %s" % (r["decision_id"], "; ".join(errs)), [r["ref"]])
            else:
                prior = [x for x in self.decisions if (x["subject_type"], x["subject_id"], x["revision"]) ==
                         (r["subject_type"], r["subject_id"], r["revision"]) and set(x["roles"]) & set(r["roles"])
                         and x["outcome"] == "return"]
                self.decisions.append(dict(r, admitted_batch=b))
                if prior and r["outcome"] == "approve":
                    self.log("review-resumed", r["subject_id"], "%s %s r%d after return %s" % (
                        "+".join(r["roles"]), r["outcome"], r["revision"], prior[-1]["decision_id"]), [r["ref"]])
                if r["outcome"] != "approve":
                    self.log("review", r["subject_id"], "%s %s r%d: %s" % (
                        "+".join(r["roles"]), r["outcome"], r["revision"], r["reason"]), [r["ref"]])

    def _review_errors(self, r):
        errs, p = [], r["packet"]
        if r["subject_type"] == "claim":
            c = self.current.get(r["subject_id"])
            if not c:
                return ["claim %s has not arrived" % r["subject_id"]]
            if r["revision"] != c["revision"]:
                errs.append("stale revision r%s (current r%d)" % (r["revision"], c["revision"]))
            emp, trip = c["employee"], self.ds["trips"].get(c["trip_id"])
            if p and (p["trip_id"] != c["trip_id"] or sorted(p["cost_ids"]) != sorted(l["cost_id"] for l in c["lines"])):
                errs.append("review packet does not describe this claim revision")
            if p and trip and p["trip_revision"] not in (None, c["trip_revision"]):
                errs.append("packet trip revision differs")
        elif r["subject_type"] == "permit":
            trip = next((t for t in self.ds["trips"].values() if t["permit_id"] == r["subject_id"]), None)
            if not trip:
                return ["permit %s not in Trips" % r["subject_id"]]
            emp = trip["employee"]
            if r["revision"] != trip["permit_revision"]:
                errs.append("stale permit revision r%s" % r["revision"])
            if p and (p["trip_id"] != trip["trip_id"] or p["permit_id"] != r["subject_id"]):
                errs.append("review packet does not describe this permit")
        else:
            return ["unknown subject type %r" % r["subject_type"]]
        if not p:
            errs.append("no review packet")
        elif p["employee"] != emp:
            errs.append("packet employee differs")
        elif p["policy_revision"] != self.policy_revision:
            errs.append("packet policy %s is not current %s" % (p["policy_revision"], self.policy_revision))
        d = self.directory(emp)
        if not d:
            errs.append("employee %s not in directory" % emp)
        else:
            for role in r["roles"]:
                if role not in ROLES:
                    errs.append("unknown role %s" % role)
                elif d[DIRECTORY_COL[role]] != r["reviewer"]:
                    errs.append("%s is not the directory %s (%s)" % (r["reviewer"], role, d[DIRECTORY_COL[role]]))
            if len(r["roles"]) > 1 and (set(r["roles"]) != {"budget_owner", "supervisor"}):
                errs.append("only budget owner and supervisor may share one response")  # POL ¶4
        if r["outcome"] not in ("approve", "return", "reject"):
            errs.append("unknown outcome %r" % r["outcome"])
        if r["time"] is None or r["time"] >= self.clock_end:
            errs.append("decision time missing or beyond case clock")
        return errs

    # ------------------------------------------------------------ permits
    def permit_state(self, trip):
        """Return (status, completion_time, decision_ids) for the trip's permit as currently known."""
        pid = trip["permit_id"]
        ds = [d for d in self.decisions if d["subject_type"] == "permit" and d["subject_id"] == pid
              and d["revision"] == trip["permit_revision"]]
        if any(d["outcome"] != "approve" for d in ds):
            return "not-approved", None, [d["decision_id"] for d in ds]
        need = ["administration", "budget_owner", "supervisor"]
        if trip["estimate"] is not None and cents(trip["estimate"]) > DIRECTOR_THRESHOLD_CENTS:
            need.append("director")
        have = {role for d in ds for role in d["roles"]}
        if not set(need) <= have:
            return "incomplete", None, [d["decision_id"] for d in ds]
        return "approved", max(d["time"] for d in ds), [d["decision_id"] for d in ds]

    # ------------------------------------------------------------ cancellations affecting a trip
    def trip_cancellations(self, trip_id, trip_revision):
        out = []
        for cid, p in sorted(self.canc.items()):
            r = p["request"]
            if r["trip_id"] == trip_id and r["trip_revision"] == trip_revision:
                out.append((cid, p))
        return out

    # ------------------------------------------------------------ requests
    def _claim_requests(self, cid):
        return [r for r in self.requests.values() if r["claim_id"] == cid]

    def request_ledger(self, req):
        evs = [e for e in self.fin_admitted if e["request_id"] == req["request_id"]]
        settled = sum((cents(e["amount"]) for e in evs if e["type"] == "settled"), 0)
        refunded = sum((cents(e["amount"]) for e in evs if e["type"] == "refund"), 0)
        return evs, settled, refunded

    def net_paid(self, cid):
        total = 0
        for req in self._claim_requests(cid):
            _, s, r = self.request_ledger(req)
            total += s - r
        return total

    # ------------------------------------------------------------ 4/6. evaluation
    def _evaluate_all(self, propose):
        claims = {cid: self.evaluate_claim(cid, propose) for cid in sorted(self.current, key=_natural)}
        cancs = {cid: self.evaluate_cancellation(cid, claims) for cid in sorted(self.canc)}
        return {"claims": claims, "cancellations": cancs}

    def evaluate_claim(self, cid, propose=False):
        c = self.current[cid]
        rev = c["revision"]
        trip = self.ds["trips"].get(c["trip_id"])
        emp = c["employee"]
        d = self.directory(emp)
        fin = d and d["Finance officer"]
        issues = []
        claim_ref = "%s#%s" % (c["source_id"], c["locator"])

        lead = d and d["Administration reviewer"]

        def issue(code, owner, reason, action, cost=None, refs=(), blocking=True, extra=None):
            # owner = the party who must supply the missing fact or decision (its authority);
            # follow_up = the Travel Administration Lead, who chases missing replies (INT3 10:51).
            rid = "ISS-%s-r%d-%s%s" % (cid, rev, code, ("-" + cost) if cost else "")
            issues.append(dict(record_id=rid, subject_type="claim", subject_id=cid, revision=rev,
                               trip_id=c["trip_id"], trip_revision=c["trip_revision"],
                               permit_id=trip and trip["permit_id"], permit_revision=trip and trip["permit_revision"],
                               fact_code=code, cost_id=cost, reason=reason, owner=owner, resolution_needed=action,
                               decision_authority=owner, follow_up=lead,
                               source_ids=[claim_ref] + list(refs), blocking=blocking, **(extra or {})))

        if not trip:
            issue("trip_missing", d and d["Administration reviewer"] or "ADMIN-01",
                  "trip %s is not in the Trips register" % c["trip_id"], "Obtain the trip record")
        elif trip["employee"] != emp:
            issue("trip_employee_mismatch", emp, "trip belongs to %s" % trip["employee"],
                  "Confirm which trip this claim belongs to")
        elif trip["trip_revision"] != c["trip_revision"]:
            issue("trip_revision_mismatch", emp, "claim cites trip r%d, register has r%d" % (
                c["trip_revision"], trip["trip_revision"]), "Resubmit against the current trip revision")

        cancels = self.trip_cancellations(c["trip_id"], c["trip_revision"]) if trip else []
        confirmed = [(k, p) for k, p in cancels if p["confirm"]]
        for k, p in cancels:
            if not p["confirm"]:
                # A valid request pauses payment readiness while the supervisor decides (POL ¶15).
                sup = d and d["Supervisor"]
                issue("cancellation_pending:" + k, sup, "%s cancellation %s requested %s; payment readiness paused" % (
                    p["request"]["target_type"], k, iso(p["request"]["time"])),
                    "Supervisor confirms or declines cancellation %s" % k, refs=[p["request"]["ref"]])

        permit_status = None
        if trip and trip["international"]:
            permit_status, permit_done, permit_dids = self.permit_state(trip)

        lines, allowed_total, unresolved = [], 0, False
        # Latest arrival batch of the evidence this revision relies on, split by what it changes:
        # receipts and payment proof (all replies depend on them, INT3 10:50, INT5 01:52) versus Finance rates and caps,
        # which change the amount, so only the amount-dependent reviews repeat (INT6 02:09; POL ¶6 role scopes).
        evidence_batch = 1
        amount_batch = 1
        exc = c.get("exception")
        for ln in c["lines"]:
            cost = ln["cost_id"]
            refs, findings = [claim_ref], []   # findings: (code, owner, reason, action, coverable)
            status, allowed_orig, reason_bits, excluded = None, None, [], None

            rcs = self.avail(self.ds["receipts"].get(cost, []))
            rc = None
            if not self.ds["receipts_available"]:
                findings.append(("receipt_source_unavailable", d and d["Administration reviewer"],
                                 "receipt binder could not be read in this run", "Re-run with a complete receipt binder read", False))
            elif len(rcs) != 1:
                findings.append(("missing_receipt" if not rcs else "duplicate_receipt", emp,
                                 "%d receipts for %s" % (len(rcs), cost), "Employee supplies the single matching receipt", False))
            else:
                rc = rcs[0]
                evidence_batch = max(evidence_batch, rc.get("batch") or 1)
                refs.append("receipts#%s:%s" % (rc["locator"], rc["receipt_ref"]))
                bad = [k for k, a, b2 in (("receipt reference", rc["receipt_ref"], ln["receipt_ref"]),
                                          ("employee", rc["employee"], emp), ("trip", rc["trip_id"], c["trip_id"]),
                                          ("currency", rc["currency"], ln["currency"]), ("gross", rc["gross"], ln["amount"])) if a != b2]
                if bad:
                    findings.append(("receipt_mismatch", emp, "receipt differs on " + ", ".join(bad),
                                     "Employee supplies a receipt matching the claimed cost", False))
            txs = self.avail(self.ds["merchant"].get(cost, []))
            tx = next((t for t in txs if t["status"] == "settled" and t["employee"] == emp and t["trip_id"] == c["trip_id"]
                       and t["currency"] == ln["currency"] and t["gross"] == ln["amount"]
                       and t["receipt_ref"] == ln["receipt_ref"]), None)
            if tx:
                refs.append(tx["ref"])
                evidence_batch = max(evidence_batch, tx.get("batch") or 1)
            elif txs:
                findings.append(("payment_proof_mismatch", emp, "merchant transaction(s) %s not settled or not matching" % ", ".join(
                    t["txn"] for t in txs), "Employee supplies the settled merchant transaction for %s" % cost, False))
            else:
                findings.append(("missing_payment_proof", emp, "no settled merchant transaction for %s" % cost,
                                 "Employee supplies the settled merchant transaction for %s" % cost, False))
            paid_date = tx and tx["paid"]
            category = rc and rc["category"]

            # Version-bound Finance exception (POL ¶3, ¶15): only the directory Finance officer, for this
            # claim, revision and cost. Bound before category rules so a Finance reclassification applies.
            line_exc = None
            if exc and exc["cost_id"] == cost:
                ok = exc["claim_id"] == cid and exc["revision"] == rev and exc["actor"] == fin
                if ok:
                    line_exc = exc
                    refs.append("%s#%s" % (c["source_id"], exc["locator"]))
                else:
                    reason_bits.append("exception not bound to %s r%d by %s; ignored" % (cid, rev, fin))
            if line_exc and line_exc.get("category") and line_exc["category"] != category:
                # Reclassification is recorded on this revision; the receipt keeps the original category (INT3 10:51).
                reason_bits.append("reclassified by Finance exception from receipt category '%s' to '%s' (%s)" % (
                    category, line_exc["category"], line_exc["reason"]))
                category = line_exc["category"]

            # Prepaid cost already carried by another claim's accepted obligation (POL ¶9).
            prior = [r for r in self.requests.values() if r["claim_id"] != cid and cost in r["cost_ids"]
                     and r["status"] in ("accepted", "dispatched", "settled", "cancel-pending")]
            if prior:
                excluded = "already carried by %s (%s %s); linked, not paid twice" % (
                    prior[0]["claim_id"], prior[0]["request_id"], prior[0]["status"])
                refs.append("request:" + prior[0]["request_id"])
            elif category == "personal":
                excluded = "personal purchase: zero entitlement (claimed %s %s retained with evidence)" % (ln["amount"], ln["currency"])
            elif category is not None and category not in UNCAPPED and category not in CAPPED:
                # Undefined categories stay unresolved for every claim until Finance supplies a definition or a
                # specific eligibility instruction; never assumed eligible or ineligible (INT3 10:48, 10:50, 10:52).
                findings.append(("unknown_category", fin,
                                 "receipt category '%s' is not defined by policy %s; eligibility unknown" % (category, self.policy_revision),
                                 "Finance (%s) supplies an authoritative definition of '%s' or a specific eligibility instruction "
                                 "for %s %s r%d (claimed %s %s); the employee (%s) may only be asked to clarify the purchase; "
                                 "the Travel Administration Lead (%s) follows up" % (
                                     fin, category, cost, cid, rev, ln["amount"], ln["currency"], emp, lead), "instruction"))

            rate = None
            if ln["currency"] == "EUR":
                rate = Decimal(1)
            elif paid_date:
                fx = next((f for f in self.avail(self.ds["fx"]) if f["currency"] == ln["currency"] and f["date"] == paid_date), None)
                if fx:
                    rate = fx["rate"]
                    refs.append(fx["ref"])
                    amount_batch = max(amount_batch, fx.get("batch") or 1)
                else:
                    findings.append(("missing_rate", fin, "no Finance %s rate for payment date %s" % (ln["currency"], paid_date),
                                     "Finance supplies or confirms the %s rate for %s" % (ln["currency"], paid_date), False))

            cap_total = None
            if category in CAPPED and paid_date and trip and not excluded:
                cap = next((k for k in self.avail(self.ds["caps"]) if k["destination"] == trip["destination"] and k["category"] == category
                            and k["currency"] == ln["currency"] and k["from"] <= paid_date <= k["to"]), None)
                units = rc["units"] if rc else None
                if not (units and units.isdigit() and int(units) > 0):
                    findings.append(("invalid_units", emp, "documented units %r" % units, "Employee documents positive units", False))
                elif cap:
                    refs.append(cap["ref"])
                    amount_batch = max(amount_batch, cap.get("batch") or 1)
                    cap_total = cap["amount"] * int(units)
                else:
                    findings.append(("missing_cap", fin, "no %s cap for %s in %s on %s" % (category, trip["destination"], ln["currency"], paid_date),
                                     "Finance supplies or confirms the %s %s cap in %s for %s" % (trip["destination"], category, ln["currency"], paid_date), False))

            # Filing deadline from the planned trip end; corrections keep first submission dates (POL ¶5).
            if trip:
                deadline = add_months_clamped(trip["end"], 2)
                if ln["first_submitted"] > deadline:
                    findings.append(("late_filing", fin, "first submitted %s after deadline %s" % (ln["first_submitted"], deadline),
                                     "Finance grants or refuses a late-filing exception for %s r%d %s" % (cid, rev, cost), True))
            if trip and trip["international"]:
                commit = min([x for x in (trip["commitment"], paid_date) if x] or [None])
                if permit_status != "approved":
                    if commit:
                        findings.append(("permit_unapproved", fin, "permit %s %s before commitment %s" % (trip["permit_id"], permit_status, commit),
                                         "Finance decides a permit_unapproved exception for %s" % cost, True))
                elif commit:
                    done = local_date(permit_done)
                    if done > commit:
                        findings.append(("late_permit", fin, "permit %s approved %s after first commitment %s" % (trip["permit_id"], done, commit),
                                         "Finance decides a late_permit exception for %s" % cost, True))
                    elif done == commit:
                        findings.append(("permit_timing_ambiguous", fin, "permit approval and commitment both on %s" % done,
                                         "Supervisor/Finance resolve the order of approval and commitment", False))
            for k, p in confirmed:
                findings.append(("travel_cancellation:" + k, fin, "%s cancellation %s confirmed %s" % (
                    p["request"]["target_type"], k, iso(p["confirm"]["effective"])),
                    "Finance supplies an explicit cost disposition for %s naming %s" % (cost, k), True))
                if paid_date and paid_date == local_date(p["confirm"]["effective"]):
                    findings.append(("cancellation_timing_ambiguous:" + k, fin, "payment date equals cancellation date",
                                     "Supervisor/Finance resolve whether payment preceded cancellation", False))

            open_findings = []
            for code, owner, why, action, coverable in findings:
                base = code.split(":")[0]
                if coverable == "instruction":
                    # A cost-specific Finance amount is an explicit eligibility instruction for that cost.
                    covered = bool(line_exc and line_exc["allowed_original"] is not None)
                else:
                    covered = bool(line_exc and coverable and base in line_exc["covered_issues"] and
                                   (base != "travel_cancellation" or line_exc["travel_cancellation_id"] == code.split(":")[1]))
                if covered:
                    reason_bits.append("%s covered by Finance exception (%s)" % (code, line_exc["reason"]))
                else:
                    open_findings.append((code, owner, why, action))

            if not excluded and line_exc and line_exc["allowed_original"] == 0 and not open_findings:
                excluded = "Finance instruction: zero entitlement (%s); claimed %s %s retained with evidence" % (
                    line_exc["reason"], ln["amount"], ln["currency"])
            if excluded:
                status, allowed_cents, reason_bits = "excluded", 0, [excluded] + reason_bits
            else:
                if line_exc and line_exc["allowed_original"] is not None:
                    allowed_orig = line_exc["allowed_original"]
                    reason_bits.append("allowed original %s set by Finance exception" % allowed_orig)
                elif category in UNCAPPED:
                    allowed_orig = ln["amount"]
                elif category in CAPPED and cap_total is not None:
                    allowed_orig = min(ln["amount"], cap_total)
                    if cap_total < ln["amount"]:
                        reason_bits.append("capped at %s" % cap_total)
                allowed_cents = cents(allowed_orig * rate) if (allowed_orig is not None and rate is not None) else None
                if open_findings or allowed_cents is None:
                    status = "unresolved"
                else:
                    status = "supported"
                    reason_bits.insert(0, "%s %s %s x %s" % (category, ln["amount"], ln["currency"], rate))
            for code, owner, why, action in open_findings:
                issue(code, owner, why, action, cost=cost, refs=refs[1:])
                reason_bits.append(code + ": " + why)
            if status == "unresolved" and not open_findings:
                reason_bits.append("allowed amount cannot be computed")
            lines.append({"cost_id": cost, "source_ids": sorted(set(refs)), "status": status,
                          "allowed_cents": allowed_cents if status != "unresolved" or allowed_cents is not None else None,
                          "reason": "; ".join(reason_bits) or status})
            if status == "unresolved":
                unresolved = True
            else:
                allowed_total += allowed_cents

        allowed = None if unresolved else allowed_total

        # Reviews for the exact current subject/revision (INT2 10:09); cancellation-aware when needed (POL ¶15).
        need_aware = sorted({k for k, _ in confirmed})
        mine = [x for x in self.decisions if x["subject_type"] == "claim" and x["subject_id"] == cid and x["revision"] == rev]
        counted, not_aware, stale = [], [], []
        for x in mine:
            if need_aware and not set(need_aware) <= set(x["packet"]["cancellation_ids"]):
                not_aware.append(x)
            elif x["admitted_batch"] < evidence_batch:
                # Evidence for this revision arrived after the reply; changed evidence invalidates it (INT3 10:50).
                stale.append(x)
            elif x["admitted_batch"] < amount_batch and set(x["roles"]) & AMOUNT_ROLES:
                # A Finance rate or cap arrived after this reply: only the review that depends on the amount repeats
                # (INT6 02:09). The supervisor's review does not depend on the amount (POL ¶6), so it stands.
                stale.append(x)
            else:
                counted.append(x)
        roles_needed = ["administration", "budget_owner", "supervisor"]
        if allowed is not None and allowed > DIRECTOR_THRESHOLD_CENTS:
            roles_needed.append("director")
        # The latest reply per role on this revision is that role's position: a later reply from the role that
        # returned the work resumes its review (INT4 01:20), without touching other roles' replies.
        latest = {}
        for x in sorted(counted, key=lambda x: (x["time"], x["admitted_batch"], x["decision_id"])):
            for role in x["roles"]:
                latest[role] = x
        current_replies = {x["decision_id"]: x for x in latest.values()}.values()
        approvals = {role for role, x in latest.items() if x["outcome"] == "approve"}
        rejects = [x for x in counted if x["outcome"] == "reject"]  # an explicit rejection closes; not undone
        returns = [x for x in current_replies if x["outcome"] == "return"]
        for x in returns:
            # Route by what the reviewer asked for, not by default to the employee (INT3 10:48, INT4 01:20).
            kind, src, _, basis = routing.classify(x["repair"], x["reason"])
            who = routing.owner_for(src, emp, d) if d else emp
            roles = " and ".join(r.replace("_", " ") for r in x["roles"])
            asked = routing.sentence(x["repair"]) or routing.sentence(x["reason"])
            fields = ", ".join(x.get("affected_fields") or []) or "not stated"
            # A return request states subject type, revision, the actor's role, the source version and the repair
            # naming the affected fields (INT5 01:53).
            why = ("The %s (%s) returned claim %s revision %d on %s: %s. Repair requested: %s. Affected fields: %s. "
                   "Source versions reviewed: %s") % (
                roles, x["reviewer"], cid, rev, local_date(x["time"]), routing.sentence(x["reason"]),
                routing.sentence(x["repair"]) or "none stated", fields, ", ".join(x.get("source_revisions") or []) or "not stated")
            if kind == "funding_decision":
                action = ("The budget owner (%s) makes the funding decision for claim %s revision %d and replies on that "
                          "revision; the process then continues from there" % (who, cid, rev))
            elif kind == "employee_correction":
                action = ("The employee (%s) supplies the correction asked for (%s) as an updated claim revision; the "
                          "%s (%s) then evaluates the repair and the process continues from there" % (who, asked, roles, x["reviewer"]))
            elif kind == "named_owner_repair":
                action = ("%s supplies the repair the %s named (%s); the %s (%s) then evaluates it on claim %s and the "
                          "process continues from there" % (who, roles, asked, roles, x["reviewer"], cid))
            else:
                action = ("The Travel Administration Lead (%s) identifies with the %s (%s) who owns the repair (%s) and "
                          "passes it to them" % (who, roles, x["reviewer"], asked))
            issue("%s:%s" % (kind, "+".join(x["roles"])), who, why, action, refs=[x["ref"]],
                  extra={"route_basis": basis})
        decision_ids = sorted(x["decision_id"] for x in counted)

        reqs = self._claim_requests(cid)
        paid = self.net_paid(cid)
        live = [r for r in reqs if r["status"] in ("accepted", "dispatched", "settled", "cancel-pending")]
        missing_roles = [r for r in roles_needed if r not in approvals]

        # Finance-side issues: unmatched, invalid or conflicting deliveries stay visible (POL ¶10)
        for w in self.fin_waiting:
            if w["claim_id"] == cid:
                issue("finance_event_unmatched:" + w["event_id"], fin, "%s %s names %s, which this workflow has not proposed" % (
                    w["event_id"], w["type"], w["request_id"]), "Finance clarifies %s" % w["event_id"], refs=[w["ref"]])
        for x in self.fin_rejected:
            if x["event"]["claim_id"] == cid:
                issue("finance_event_rejected:" + x["event"]["event_id"], fin, x["reason"],
                      "Finance corrects or confirms %s" % x["event"]["event_id"], refs=[x["event"]["ref"]])
        for r in reqs:
            evs, s, rf = self.request_ledger(r)
            types = [e["type"] for e in evs]
            if r["status"] == "cancelled" and s > 0:
                late = [e for e in evs if e["type"] == "settled" and e["time"] > max(
                    x["time"] for x in evs if x["type"] == "cancelled")]
                if late:
                    issue("transfer_after_cancellation", fin, "%s settled %s after Finance cancelled %s" % (
                        ",".join(e["event_id"] for e in late), _eur(sum(cents(e["amount"]) for e in late)), r["request_id"]),
                        "Finance resolves the late transfer on %s (apply to a current revision or recover it)" % r["request_id"],
                        refs=[e["ref"] for e in late])
            if types and types[-1] == "failed":
                issue("payment_failed", fin, "%s failed (%s); paid amount unchanged" % (r["request_id"], evs[-1]["event_id"]),
                      "Finance authorizes and executes a new attempt", refs=[evs[-1]["ref"]], blocking=False)

        state = {"claim_id": cid, "revision": rev, "trip_id": c["trip_id"], "trip_revision": c["trip_revision"],
                 "lines": lines, "allowed_cents": allowed, "paid_cents": paid,
                 "balance_cents": None if allowed is None else allowed - paid,
                 "decision_ids": decision_ids, "issues": issues}

        def done(status, owner, reason):
            state.update(status=status, next_owner=owner, reason=reason)
            if status in ("held",) and not state["issues"]:
                raise AssertionError("held without an issue: " + cid)
            if status == "held":
                # Holding the whole claim and proceeding with independent lines are both permitted if the business cost
                # is explained (INT6 02:08-02:09). We hold; say what that withholds and what proceeding would risk.
                state["hold_impact"] = self.hold_impact(c, lines, [i for i in state["issues"] if i["blocking"]], state["paid_cents"])
                for i in state["issues"]:
                    if i["blocking"]:
                        i["hold_impact"] = state["hold_impact"]
            return state

        blocking = [i for i in issues if i["blocking"]]
        if c["binder_status"] == "withdrawn":
            if paid:
                issue("payment_after_withdrawal", fin, "withdrawal cannot erase %s paid" % _eur(paid), "Finance resolves recovery")
                return done("held", fin, "withdrawn with payment outstanding")
            state["issues"] = []
            state.update(allowed_cents=0, balance_cents=0)
            return done("withdrawn", None, "employee withdrew r%d before review (%s)" % (rev, c["claim_reason"]))
        if rejects:
            if paid:
                issue("payment_after_rejection", fin, "rejected claim has %s paid" % _eur(paid), "Finance resolves recovery")
                return done("held", fin, "rejected with payment outstanding")
            state["issues"] = []
            state.update(allowed_cents=0, balance_cents=0)
            x = rejects[0]
            return done("rejected", None, "rejected by %s %s: %s" % ("+".join(x["roles"]), x["reviewer"], x["reason"]))

        if not blocking and not missing_roles and allowed is not None:
            if not reqs and allowed > 0 and propose and self.batch is not None:
                self._propose(cid, rev, allowed, emp, decision_ids, lines)
                reqs = self._claim_requests(cid)
            elif reqs and all(r["status"] == "proposed" for r in reqs) and propose:
                for r in reqs:  # rebuild readiness from current facts before dispatch (POL ¶8)
                    r.update(revision=rev, amount_cents=allowed, decision_ids=decision_ids,
                             cost_ids=[l["cost_id"] for l in lines if l["status"] == "supported"])
            elif reqs and all(r["status"] == "cancelled" for r in reqs) and paid == 0 and allowed > 0 and propose:
                self._propose(cid, rev, allowed, emp, decision_ids, lines, replacement=True)
                reqs = self._claim_requests(cid)
            live = [r for r in reqs if r["status"] in ("accepted", "dispatched", "settled", "cancel-pending")]

        # Live obligation from an earlier revision blocks a replacement until Finance resolves it (POL ¶8, ¶16).
        if live and any(r["revision"] != rev for r in live) and allowed is not None and allowed > paid:
            issue("replacement_held", fin, "r%d entitlement %s exceeds net paid %s on %s from r%d" % (
                rev, _eur(allowed), _eur(paid), live[0]["request_id"], live[0]["revision"]),
                "Finance confirms status/adjustment of %s before any replacement request" % live[0]["request_id"])

        # Overpayment and resolution requirements (POL ¶11).
        if allowed is not None and paid > allowed:
            issue("overpayment", fin, "net paid %s exceeds entitlement %s" % (_eur(paid), _eur(allowed)),
                  "Finance investigates and resolves the %s overpayment" % _eur(paid - allowed))
        need_res = self._resolution_needed(cid, allowed)
        if need_res and allowed is not None and paid == allowed and paid > 0:
            issue("finance_resolution_required", fin, "; ".join(need_res),
                  "Finance records an explicit resolution for %s at %s" % (cid, _eur(allowed)))

        blocking = [i for i in state["issues"] if i["blocking"]]
        if blocking:
            first = blocking[0]
            return done("held", first["owner"], "; ".join(sorted({i["fact_code"].split(":")[0] for i in blocking})) +
                        " — " + first["reason"])
        if missing_roles:
            if not_aware and not counted:
                why = "approvals predate cancellation %s; cancellation-aware review needed" % ",".join(need_aware)
            elif stale:
                why = "%s from batch %s predate evidence that arrived later (batch %d; Finance rate/cap batch %d); %s review of r%d repeats" % (
                    ", ".join(sorted({x["decision_id"] for x in stale})),
                    ",".join(sorted({str(x["admitted_batch"]) for x in stale})), evidence_batch, amount_batch,
                    "/".join(missing_roles), rev)
            else:
                why = "awaiting %s review of r%d" % ("/".join(missing_roles), rev)
            role = missing_roles[0]
            if role in ("budget_owner", "supervisor") and "administration" in missing_roles:
                role = "administration"
            return done("pending", d and d[DIRECTORY_COL[role]], why)
        if allowed is None:
            issue("entitlement_unknown", d and d["Administration reviewer"], "allowed amount cannot be computed",
                  "Administration identifies the missing calculation input")
            return done("held", d and d["Administration reviewer"], "entitlement unknown")
        if allowed == 0 and paid == 0:
            state["issues"] = [i for i in state["issues"] if i["blocking"]]
            return done("closed-no-payment", None, "zero entitlement after full review: " + "; ".join(
                l["reason"] for l in lines))
        if not reqs or all(r["status"] == "proposed" for r in reqs):
            return done("ready", fin, "approved r%d for %s; request %s proposed to Finance" % (
                rev, _eur(allowed), reqs[0]["request_id"] if reqs else "-"))
        if paid < allowed:
            fail = [i for i in state["issues"] if i["fact_code"] == "payment_failed"]
            return done("pending", fin, fail[0]["reason"] if fail else "awaiting Finance settlement: %s of %s paid" % (
                _eur(paid), _eur(allowed)))
        if state["issues"]:
            return done("pending", state["issues"][0]["owner"], state["issues"][0]["reason"])
        return done("closed-reimbursed", None, "r%d approved; net paid %s equals entitlement%s" % (
            rev, _eur(paid), "; " + "; ".join(self._resolutions(cid)) if self._resolutions(cid) else ""))

    def hold_impact(self, c, lines, blocking, paid):
        """Plain statement of what a whole-claim hold withholds, using only amounts from the sources."""
        claimed = {l["cost_id"]: "%s %s" % (l["amount"], l["currency"]) for l in c["lines"]}
        supported = [l for l in lines if l["status"] == "supported"]
        open_lines = [l for l in lines if l["status"] == "unresolved"]
        total = sum(l["allowed_cents"] for l in supported)
        sup_txt = ", ".join("%s %s" % (l["cost_id"], _eur(l["allowed_cents"])) for l in supported) or "none"
        claim_level = sorted({i["fact_code"].split(":")[0] for i in blocking if not i["cost_id"]})
        if claim_level:
            return ("Held for a claim-level reason (%s), so the whole revision waits whichever approach is used; "
                    "proceeding with independent lines does not apply. Supported lines: %s (total %s). Already paid: %s."
                    % (", ".join(claim_level), sup_txt, _eur(total), _eur(paid)))
        if not supported:
            return ("Held, but no line is supported yet (%s open), so holding withholds nothing that could proceed. "
                    "Already paid: %s." % (", ".join("%s claimed %s" % (l["cost_id"], claimed[l["cost_id"]]) for l in open_lines),
                                           _eur(paid)))
        open_txt = ", ".join("%s (claimed %s)" % (l["cost_id"], claimed[l["cost_id"]]) for l in open_lines)
        return ("Held in full. Withheld: %s, total %s; already paid %s. Why: %s is unresolved, and reviews cover the whole "
                "claim revision (interview 1, 06:33), so revision %d's entitlement is unknown. Proceeding on the "
                "independent lines instead (also permitted, interview 6, 02:08) would mean reviewing and paying %s on revision %d "
                "while %s stays open. When it resolves, the changed facts make the dependent review repeat (interview 6, "
                "02:09), the remainder needs a second payment on the same revision, and any change to what was already "
                "paid needs a Finance adjustment and resolution before closure (policy ¶11)."
                % (sup_txt, _eur(total), _eur(paid), open_txt, c["revision"], _eur(total), c["revision"], open_txt))

    def _resolutions(self, cid):
        return ["Finance resolution %s" % e["event_id"] for e in self.fin_admitted
                if e["claim_id"] == cid and e["type"] == "resolution"]

    def _resolution_needed(self, cid, allowed):
        """Triggers needing an explicit Finance resolution after them, matching the current entitlement."""
        trig = list(self.triggers[cid])
        for e in self.fin_admitted:
            if e["claim_id"] == cid and e["type"] in ("adjustment", "refund"):
                trig.append({"kind": e["type"], "batch": e["admitted_batch"], "time": e["time"], "ref": e["event_id"]})
        if not trig:
            return []
        res = [e for e in self.fin_admitted if e["claim_id"] == cid and e["type"] == "resolution"]

        def after(r, t):
            return (r["admitted_batch"], r["time"]) >= (t["batch"], t["time"] or r["time"])
        open_t = [t for t in trig if not any(after(r, t) and allowed is not None and cents(r["obligation"]) == allowed for r in res)]
        return ["%s %s awaits Finance resolution" % (t["kind"], t["ref"]) for t in open_t]

    def _propose(self, cid, rev, amount, emp, decision_ids, lines, replacement=False):
        rid = "REQ-%s" % cid if not replacement else "REQ-%s-r%d" % (cid, rev)
        if rid in self.requests:
            return
        payee = self.directory(emp)["Payee ID"]
        self.requests[rid] = {"request_id": rid, "claim_id": cid, "revision": rev, "amount_cents": amount,
                              "payee": payee, "currency": "EUR", "status": "proposed", "decision_ids": decision_ids,
                              "cost_ids": [l["cost_id"] for l in lines if l["status"] == "supported"],
                              "proposed_batch": self.batch, "obligation_cents": None}
        self.log("request", cid, "%s proposed for %s (r%d)" % (rid, _eur(amount), rev))

    # ------------------------------------------------------------ 5. Finance activity
    def _finance(self, b):
        retry, self.fin_waiting = self.fin_waiting, []
        for e in retry:  # unmatched events from earlier batches are rechecked first
            self._try_admit(e, b)
        for e in sorted([e for e in self.ds["finance"] if e["batch"] == b], key=lambda e: (e["time"], e["event_id"])):
            key = _payload_key(e)
            if e["event_id"] in self.fin_seen:
                if self.fin_seen[e["event_id"]] == key:
                    # Exact replay: same immutable payload, no extra effect (POL ¶10, INT2 10:06).
                    self.replays.append(("finance", e["event_id"], b))
                    self.log("replay", e["claim_id"], "exact redelivery of %s in batch %d: no effect" % (e["event_id"], b), [e["ref"]])
                else:
                    self.fin_rejected.append({"event": e, "reason": "conflicting payload for event ID %s" % e["event_id"],
                                              "batch": b, "conflict": True})
                    self.log("finance-conflict", e["claim_id"], "conflicting redelivery of %s held" % e["event_id"], [e["ref"]])
                continue
            self.fin_seen[e["event_id"]] = key
            self._try_admit(e, b)

    def _try_admit(self, e, b):
        req = self.requests.get(e["request_id"])
        if not req:
            self.fin_waiting.append(e)
            return
        errs = self._finance_errors(e, req)
        if errs:
            self.fin_rejected.append({"event": e, "reason": "; ".join(errs), "batch": b, "conflict": False})
            self.log("finance-rejected", e["claim_id"], "%s not admitted: %s" % (e["event_id"], "; ".join(errs)), [e["ref"]])
            return
        self._apply_finance(dict(e, admitted_batch=b), req)

    def _finance_errors(self, e, req):
        errs = []
        emp = self.current[req["claim_id"]]["employee"]
        if e["claim_id"] != req["claim_id"]:
            errs.append("claim %s does not own %s" % (e["claim_id"], req["request_id"]))
        if e["actor"] != self.finance_officer(emp):
            errs.append("actor %s is not the directory Finance officer" % e["actor"])
        if e["payee"] != req["payee"]:
            errs.append("payee %s differs from %s" % (e["payee"], req["payee"]))
        if e["currency"] != "EUR":
            errs.append("currency %s" % e["currency"])
        if e["time"] is None or e["time"] >= self.clock_end:
            errs.append("time missing or beyond case clock")
        t = e["type"]
        if t in ("settled", "refund"):
            if e["amount"] is None or cents(e["amount"]) <= 0 or e["amount"] * 100 != cents(e["amount"]):
                errs.append("amount must be positive whole cents")
        if t == "accepted":
            if e["obligation"] is None or cents(e["obligation"]) != req["amount_cents"]:
                errs.append("accepted obligation %s differs from proposed %s" % (e["obligation"], _eur(req["amount_cents"])))
            if req["status"] != "proposed":
                errs.append("request is %s, not proposed" % req["status"])
        if t == "settled":
            if req["status"] in ("proposed",):
                errs.append("settlement before acceptance")
            evs = [x for x in self.fin_admitted if x["request_id"] == req["request_id"]]
            if evs and evs[-1]["type"] == "failed":
                errs.append("new attempt after failure without Finance retry authorization")
        if t == "refund":
            orig = next((x for x in self.fin_admitted if x["event_id"] == e["original_event_id"] and x["type"] == "settled"), None)
            if not orig:
                errs.append("refund does not name a prior settled transfer")
            else:
                done = sum(cents(x["amount"]) for x in self.fin_admitted if x["type"] == "refund" and x["original_event_id"] == orig["event_id"])
                if cents(e["amount"]) > cents(orig["amount"]) - done:
                    errs.append("refund exceeds unrecovered amount of %s" % orig["event_id"])
        if t in ("adjustment", "resolution") and (e["obligation"] is None or e["obligation"] < 0):
            errs.append("%s needs a non-negative obligation" % t)
        if t not in ("accepted", "settled", "failed", "retry_authorized", "cancellation_requested", "cancelled",
                     "adjustment", "refund", "resolution"):
            errs.append("unknown activity type %s" % t)
        return errs

    def _apply_finance(self, e, req):
        self.fin_admitted.append(e)
        t = e["type"]
        before = req["status"]
        if t == "accepted":
            req["status"], req["obligation_cents"] = "accepted", cents(e["obligation"])
            req["accepted_batch"] = e["admitted_batch"]
        elif t in ("adjustment", "resolution"):
            req["obligation_cents"] = cents(e["obligation"])
        elif t == "cancellation_requested":
            req["status"] = "cancel-pending"
        elif t == "cancelled":
            req["status"] = "cancelled"
        elif t == "settled":
            _, s, r = self.request_ledger(req)
            if req["status"] != "cancelled" and s - r >= (req["obligation_cents"] or req["amount_cents"]):
                req["status"] = "settled"
            if req["status"] == "cancelled":
                self.triggers[req["claim_id"]].append({"kind": "transfer-after-cancellation", "batch": e["admitted_batch"],
                                                       "time": e["time"], "ref": e["event_id"]})
        amt = e["amount"] if e["amount"] is not None else e["obligation"]
        self.log("finance", req["claim_id"], "%s %s %s%s" % (e["event_id"], t, req["request_id"],
                                                             (" " + _eur(cents(amt))) if amt is not None else "") +
                 (" (%s -> %s)" % (before, req["status"]) if before != req["status"] else ""), [e["ref"]])

    # ------------------------------------------------------------ cancellation processes
    def evaluate_cancellation(self, k, claims):
        p = self.canc[k]
        r, cf = p["request"], p["confirm"]
        trip = self.ds["trips"][r["trip_id"]]
        affected = sorted({cid for cid, revs in self.revs.items() for c in revs
                           if c["trip_id"] == r["trip_id"] and c["trip_revision"] == r["trip_revision"]}, key=_natural)
        orig_reqs = sorted(q["request_id"] for q in self.requests.values() if q["claim_id"] in affected)
        issues = []
        fin = self.finance_officer(trip["employee"])
        sup = self.directory(trip["employee"])["Supervisor"]
        for ev in p["conflicts"]:
            issues.append(dict(record_id="ISS-%s-conflicting-delivery-%s" % (k, ev), subject_type="cancellation", subject_id=k,
                               revision=None, trip_id=r["trip_id"], trip_revision=r["trip_revision"],
                               permit_id=r["permit_id"], permit_revision=r["permit_revision"], fact_code="conflicting_delivery",
                               cost_id=None, reason="conflicting or repeated delivery %s" % ev, owner=sup,
                               resolution_needed="Administration confirms the authoritative cancellation record with the supervisor",
                               source_ids=[r["ref"]], blocking=True))
        if not cf:
            fs = "unresolved" if affected or trip["commitment"] else "no-financial-effect"
            status, owner, reason = "requested", sup, "awaiting supervisor decision; affected arrangements and payment readiness paused"
        else:
            status = "confirmed"
            unresolved = []
            for cid in affected:
                st = claims.get(cid)
                cur = self.current[cid]
                if cur["trip_id"] == r["trip_id"] and cur["trip_revision"] == r["trip_revision"] and st:
                    if any(i["fact_code"] == "travel_cancellation:" + k for i in st["issues"]):
                        unresolved.append("%s has no Finance cost disposition naming %s" % (cid, k))
                    elif st["status"] in ("pending", "held") and "cancellation-aware" in st["reason"]:
                        unresolved.append("%s awaits cancellation-aware review" % cid)
                for q in self._claim_requests(cid):
                    accepted_before = q.get("accepted_batch") is not None and q["accepted_batch"] <= p["batch_confirmed"]
                    evs, s, rf = self.request_ledger(q)
                    if not accepted_before:
                        continue
                    cancelled = any(e["type"] == "cancelled" for e in evs)
                    late = cancelled and any(e["type"] == "settled" and e["time"] > max(x["time"] for x in evs if x["type"] == "cancelled") for e in evs)
                    resolved = any(e["type"] == "resolution" and e["time"] >= cf["effective"] for e in evs)
                    if late and not resolved:
                        unresolved.append("%s received a transfer after Finance cancelled it" % q["request_id"])
                    elif not cancelled and not resolved:
                        unresolved.append("%s was accepted before cancellation; needs Finance cancellation or resolution" % q["request_id"])
            if not affected and not trip["commitment"]:
                fs, owner, reason = "no-financial-effect", None, "confirmed; no commitment, claim or Finance obligation exists"
            elif not affected:
                fs, owner, reason = "unresolved", fin, "confirmed; trip has commitments but no claim to dispose of them"
                unresolved.append("commitment without claim")
            elif unresolved:
                fs, owner, reason = "unresolved", fin, "confirmed; " + "; ".join(unresolved)
            else:
                fs, owner, reason = "resolved", None, "confirmed; affected claims and requests have explicit Finance disposition"
        for cid in affected:
            st = claims.get(cid)
            if st:
                for i in st["issues"]:
                    if i["fact_code"] in ("travel_cancellation:" + k, "cancellation_pending:" + k) or (
                            i["fact_code"] in ("transfer_after_cancellation",) and status == "confirmed"):
                        issues.append(i)
        if fs == "unresolved" and not affected:
            issues.append(dict(record_id="ISS-%s-commitment-without-claim" % k, subject_type="cancellation", subject_id=k,
                               revision=None, trip_id=r["trip_id"], trip_revision=r["trip_revision"], permit_id=r["permit_id"],
                               permit_revision=r["permit_revision"], fact_code="commitment_without_claim", cost_id=None,
                               reason="trip had commitments but no claim", owner=fin,
                               resolution_needed="Finance confirms whether any cost needs disposition", source_ids=[r["ref"]], blocking=True))
        if status == "requested":
            issues.append(dict(record_id="ISS-%s-decision-pending" % k, subject_type="cancellation", subject_id=k,
                               revision=None, trip_id=r["trip_id"], trip_revision=r["trip_revision"], permit_id=r["permit_id"],
                               permit_revision=r["permit_revision"], fact_code="cancellation_decision_pending", cost_id=None,
                               reason="cancellation requested %s by %s" % (iso(r["time"]), r["actor"]), owner=sup,
                               resolution_needed="Supervisor confirms or declines %s" % k, source_ids=[r["ref"]], blocking=True))
        lead = self.directory(trip["employee"])["Administration reviewer"]
        for i in issues:
            if i["subject_type"] == "cancellation":
                i.setdefault("decision_authority", i["owner"])
                i.setdefault("follow_up", lead)
        return {"cancellation_id": k, "target_type": r["target_type"], "trip_id": r["trip_id"],
                "trip_revision": r["trip_revision"], "permit_id": r["permit_id"] or None,
                "permit_revision": r["permit_revision"] if r["permit_id"] else None, "status": status,
                "admitted_cancellation_event_ids": [r["event_id"]] + ([cf["event_id"]] if cf else []),
                "requested_at": iso(r["time"]), "confirmed_at": iso(cf["time"]) if cf else None,
                "effective_at": iso(cf["effective"]) if cf else None, "affected_claim_ids": affected,
                "original_request_ids": orig_reqs, "financial_status": fs, "next_owner": owner if status == "confirmed" else sup,
                "reason": reason, "issues": issues}


def _eur(c):
    return "EUR %s%d.%02d" % ("-" if c < 0 else "", abs(c) // 100, abs(c) % 100)


def _natural(s):
    import re
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)]


def _payload_key(e):
    """Immutable payload: everything except arrival batch and our own locator (POL ¶10, ¶14)."""
    return tuple(sorted((k, str(v)) for k, v in e.items() if k not in ("batch", "ref")))


def _claim_key(c):
    return tuple(sorted((k, str(v)) for k, v in c.items() if k not in ("arrival_batch", "source_id", "locator")))
