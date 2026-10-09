"""Typed view of the retained sources, keyed for the engine.

Every record carries `ref`, a stable "<source_id>#<locator>:<native id>" string
used in snapshot line source_ids and the repair queue.
"""
import os
from collections import defaultdict

from . import parse


CATEGORY_POLICY = "POL-2026.2"  # policy revision the defined expense categories were read from


class SourceUnavailable(Exception):
    pass


def _usable(files, source_id):
    for f in files:
        if f["source_id"] == source_id:
            return f if f["status"] == "read" and f.get("completeness") == "complete" else None
    return None


def load(run_dir, files):
    """Build the dataset. Raises SourceUnavailable for sources no case can proceed without."""
    ds = {"unavailable": [], "limits": []}

    def need(source_id):
        f = _usable(files, source_id)
        if not f:
            ds["unavailable"].append(source_id)
        return f

    pol = need("policy")
    reg = [need("registers:" + parse.slug(t)) for t in parse.REQUIRED_TABS]
    ini = need("initial-claims")
    if not pol or not ini or not all(reg):
        raise SourceUnavailable("required source(s) unusable: " + ", ".join(ds["unavailable"]))

    ds["policy"] = parse.parse_policy(os.path.join(run_dir, pol["path"]))
    if ds["policy"]["policy_revision"] != CATEGORY_POLICY:
        # Category definitions in engine.UNCAPPED/CAPPED were taken from this policy revision; a newer policy
        # may define further categories (INT3 10:48), so the run is reported partial until they are re-read.
        ds["limits"].append("policy revision %s differs from %s, from which the defined expense categories were taken; "
                            "review category definitions before relying on unknown_category findings"
                            % (ds["policy"]["policy_revision"], CATEGORY_POLICY))
    tabs = parse.read_xlsx(os.path.join(run_dir, reg[0]["path"]))
    T = {name: tabs[name]["rows"] for name in parse.REQUIRED_TABS}
    ds["tab_notes"] = {name: tabs[name]["notes"] for name in parse.REQUIRED_TABS}

    def ref(tab, r, key):
        return "registers:%s#row %d:%s" % (parse.slug(tab), r["_row"], r[key])

    ds["people"] = {r["Employee ID"]: dict(r, ref=ref("People", r, "Employee ID")) for r in T["People"]}

    trips = {}
    for r in T["Trips"]:
        trips[r["Trip reference"]] = {
            "trip_id": r["Trip reference"], "employee": r["Employee ID"], "destination": r["Destination"],
            "international": r["International"] == "TRUE", "start": parse.serial_date(r["Start date"]),
            "end": parse.serial_date(r["End date"]), "commitment": parse.serial_date(r["First commitment date"]),
            "estimate": parse.dec(r["Estimate (EUR)"]), "permit_id": r["Permit reference"],
            "trip_revision": parse.intval(r["Trip revision"]), "permit_revision": parse.intval(r["Permit revision"]),
            "ref": ref("Trips", r, "Trip reference")}
    ds["trips"] = trips

    merchant = defaultdict(list)
    for r in T["Merchant payments"]:
        merchant[r["Expense reference"]].append({
            "txn": r["Transaction reference"], "cost_id": r["Expense reference"], "employee": r["Employee ID"],
            "trip_id": r["Trip reference"], "currency": r["Currency"], "gross": parse.dec(r["Gross amount"]),
            "paid": parse.serial_date(r["Paid date"]), "status": r["Payment status"],
            "receipt_ref": r["Receipt reference"], "ref": ref("Merchant payments", r, "Transaction reference")})
    ds["merchant"] = merchant

    ds["fx"] = [{"currency": r["Currency"], "date": parse.serial_date(r["Rate date"]),
                 "rate": parse.dec(r["EUR per currency unit"]), "ref": ref("FX", r, "Rate reference")}
                for r in T["FX"]]
    ds["caps"] = [{"destination": r["Destination"], "category": r["Category"], "currency": r["Currency"],
                   "from": parse.serial_date(r["Effective from"]), "to": parse.serial_date(r["Effective to"]),
                   "amount": parse.dec(r["Amount per unit"]), "ref": ref("Caps", r, "Cap reference")}
                  for r in T["Caps"]]
    ds["budget"] = [{"ledger": r["Ledger reference"], "department": r["Department"], "project": r["Project"],
                     "period": r["Budget period"], "type": r["Entry type"], "obligation": r["Obligation reference"],
                     "amount": parse.dec(r["Allocation or commitment (EUR)"]), "settled": parse.dec(r["Settled (EUR)"]),
                     "refunded": parse.dec(r["Refunded (EUR)"]), "ref": ref("Budget", r, "Ledger reference")}
                    for r in T["Budget"]]

    packets = {r["Decision reference"]: r for r in T["Review packets"]}
    reviews = []
    for r in T["Review ledger"]:
        p = packets.get(r["Decision reference"], {})
        reviews.append({
            "decision_id": r["Decision reference"], "batch": parse.intval(r["Arrival batch"]),
            "subject_type": r["Subject type"], "subject_id": r["Subject reference"],
            "revision": parse.intval(r["Revision"]), "roles": parse.lines_of(r["Review roles"]),
            "reviewer": r["Reviewer"], "outcome": r["Outcome"], "reason": r["Reason"],
            "repair": None if r["Repair requested"] in (None, "None") else r["Repair requested"],
            "source_revisions": parse.lines_of(r["Source revisions"]),
            "time": parse.serial_utc(r["Decision time (UTC)"]),
            "packet": None if not p else {
                "employee": p["Employee ID"], "trip_id": p["Trip reference"], "permit_id": p["Permit reference"],
                "cost_ids": parse.lines_of(p["Expense references"]), "policy_revision": p["Policy revision"],
                "estimate": parse.dec(p["Reviewed estimate (EUR)"]),
                "trip_revision": parse.intval(p["Trip revision"]), "permit_revision": parse.intval(p["Permit revision"]),
                "cancellation_ids": parse.lines_of(p["Travel cancellation references"]),
                "ref": ref("Review packets", p, "Decision reference")},
            "ref": ref("Review ledger", r, "Decision reference")})
    ds["reviews"] = reviews

    ds["finance"] = [{
        "event_id": r["Activity reference"], "batch": parse.intval(r["Arrival batch"]), "type": r["Activity type"],
        "request_id": r["Request reference"], "claim_id": r["Claim reference"], "actor": r["Finance officer"],
        "payee": r["Payee ID"], "currency": r["Currency"], "amount": parse.dec(r["Amount (EUR)"]),
        "original_event_id": r["Original activity reference"], "obligation": parse.dec(r["Obligation (EUR)"]),
        "reason": r["Reason"], "time": parse.serial_utc(r["Activity time (UTC)"]),
        "ref": ref("Finance activity", r, "Activity reference")} for r in T["Finance activity"]]

    ds["cancellations"] = [{
        "event_id": r["Cancellation activity reference"], "cancellation_id": r["Cancellation reference"],
        "action": r["Action"], "target_type": r["Cancelled subject"], "trip_id": r["Trip reference"],
        "trip_revision": parse.intval(r["Trip revision"]), "permit_id": r["Permit reference"],
        "permit_revision": parse.intval(r["Permit revision"]), "initiation_ref": r["Initiation activity reference"],
        "actor": r["Acting employee or supervisor"], "time": parse.serial_utc(r["Activity time (UTC)"]),
        "effective": parse.serial_utc(r["Effective time (UTC)"]), "batch": parse.intval(r["Arrival batch"]),
        "reason": r["Business reason"], "ref": ref("Travel cancellations", r, "Cancellation activity reference")}
        for r in T["Travel cancellations"]]

    claims = parse.parse_claim_pages(os.path.join(run_dir, ini["path"]), "initial-claims")
    upd = need("claim-updates")
    if upd:
        claims += parse.parse_claim_pages(os.path.join(run_dir, upd["path"]), "claim-updates")
    else:
        ds["limits"].append("claim-updates binder unusable: claim revisions it carries cannot be observed; "
                            "batches after the last batch fully covered by the initial binder are not processed")
    ds["claims"] = claims

    rc = need("receipts")
    receipts = defaultdict(list)
    if rc:
        for r in parse.parse_receipts(os.path.join(run_dir, rc["path"]), "receipts"):
            receipts[r["cost_id"]].append(r)
    ds["receipts"] = receipts
    ds["receipts_available"] = bool(rc)
    if not rc:
        ds["limits"].append("receipt binder unusable: every claim line is unresolved for receipt evidence")
    return ds
