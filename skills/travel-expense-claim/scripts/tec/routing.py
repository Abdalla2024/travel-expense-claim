"""Who supplies a returned-work request, decided by what the reviewer asked for.

Each route cites the interview that establishes its owner. The review ledger's
"Affected fields" column is the same for every row in the supplied workbook, so
the reviewer's repair text (then the reason) is what distinguishes a request.
A return names the affected owner of a concrete repair (INT5 01:50), so an owner
named in the repair text decides first. Otherwise the funding/evidence routes
apply. A request naming no owner and matching no route, or matching more than
one, is not guessed: the Travel Administration Lead, who passes repairs to their
owners (INT5 01:50), identifies the owner with the reviewer. Who that owner is when
the record names none remains an open point in references/requirements.md.
"""
import re

# (kind, pattern, owner directory column or "employee", plain label, basis)
ROUTES = [
    ("funding_decision", r"\bfund(?:ing|s)?\b|\bbudget\b",
     "Budget owner", "Funding decision needed",
     "INT3 10:48 (the budget owner decides funding)"),
    ("employee_correction", r"\bevidence\b|\breceipts?\b|\bmerchant\b|\btransactions?\b|\btrip\b|\bamounts?\b|\bdocument",
     "employee", "Correction requested by the reviewer",
     "INT1 06:30 (a return goes back to the employee with concrete repair instructions); "
     "INT4 01:20 (the employee supplies the corrected receipt, transaction or evidence)"),
]
UNCLASSIFIED = ("return_unclassified", "Administration reviewer", "Returned work needs clarification",
                "The return names no owner and matches no route; the Travel Administration Lead passes the repair to "
                "the affected owner (INT5 01:50) after identifying that owner with the reviewer. No interview says who "
                "owns such a repair when the record names none (open point)")

# Owner named in the repair text (INT5 01:50: a returned request names an affected owner).
NAMED_OWNERS = [
    (r"\bbudget owner\b", "Budget owner"),
    (r"\bsupervisor\b", "Supervisor"),
    (r"\bdirector\b", "Director"),
    (r"\bfinance\b", "Finance officer"),
    (r"\b(?:travel )?administration\b", "Administration reviewer"),
    (r"\bemployee\b|\bclaimant\b", "employee"),
]


def named_owner(repair):
    """The single owner role a repair text names, or None (none named, or more than one)."""
    if not repair:
        return None
    hits = {src for pat, src in NAMED_OWNERS if re.search(pat, repair, re.I)}
    return hits.pop() if len(hits) == 1 else None


def classify(repair, reason):
    """Return (kind, owner_source, label, basis). An owner named in the repair text decides first (INT5 01:50);
    then the funding/evidence routes, reading the repair text before the reason."""
    owner = named_owner(repair)
    if owner:
        return "named_owner_repair", owner, "Repair requested by the reviewer", \
            "The return names its affected owner in the repair request (INT5 01:50)"
    for text in (repair, reason):
        if not text:
            continue
        hits = [r for r in ROUTES if re.search(r[1], text, re.I)]
        if len(hits) == 1:
            kind, _, owner, label, basis = hits[0]
            return kind, owner, label, basis
        if len(hits) > 1:
            return UNCLASSIFIED[0], UNCLASSIFIED[1], UNCLASSIFIED[2], \
                "The request matches more than one route (%s); not guessed. %s" % (
                    ", ".join(h[0] for h in hits), UNCLASSIFIED[3])
    return UNCLASSIFIED


def owner_for(owner_source, employee, directory):
    return employee if owner_source == "employee" else directory[owner_source]


def sentence(text):
    """Trim trailing punctuation so templates can add their own full stop."""
    return (text or "").strip().rstrip(".;: ")


# Plain-language labels for drafts and reports; codes stay in item references only.
FACT_LABELS = {
    "missing_payment_proof": "Settled merchant transaction missing",
    "payment_proof_mismatch": "Merchant transaction does not match the claimed cost",
    "missing_receipt": "Receipt missing",
    "duplicate_receipt": "More than one receipt for one cost",
    "receipt_mismatch": "Receipt does not match the claimed cost",
    "invalid_units": "Documented nights or days missing",
    "missing_rate": "Finance exchange rate missing",
    "missing_cap": "Finance expense cap missing",
    "unknown_category": "Expense category not defined by policy",
    "late_filing": "Late-filing exception decision needed",
    "late_permit": "Late-permit exception decision needed",
    "permit_unapproved": "Unapproved-permit exception decision needed",
    "permit_timing_ambiguous": "Order of permit approval and commitment unclear",
    "travel_cancellation": "Cost disposition after cancellation needed",
    "cancellation_timing_ambiguous": "Order of payment and cancellation unclear",
    "cancellation_pending": "Cancellation decision pending",
    "cancellation_decision_pending": "Cancellation decision pending",
    "funding_decision": "Funding decision needed",
    "employee_correction": "Correction requested by the reviewer",
    "return_unclassified": "Returned work needs clarification",
    "named_owner_repair": "Repair requested by the reviewer",
    "overpayment": "Overpayment to resolve",
    "finance_resolution_required": "Finance resolution needed",
    "transfer_after_cancellation": "Payment received after cancellation",
    "payment_failed": "Failed payment needs a new attempt",
    "replacement_held": "Replacement payment held",
    "finance_event_unmatched": "Finance record does not match a request",
    "finance_event_rejected": "Finance record could not be accepted",
    "entitlement_unknown": "Entitlement cannot be calculated",
    "receipt_source_unavailable": "Receipt binder unavailable",
    "commitment_without_claim": "Commitments without a claim",
    "conflicting_delivery": "Conflicting cancellation record",
    "trip_missing": "Trip record missing",
    "trip_employee_mismatch": "Trip belongs to another employee",
    "trip_revision_mismatch": "Claim cites an outdated trip revision",
    "payment_after_withdrawal": "Payment on a withdrawn claim",
    "payment_after_rejection": "Payment on a rejected claim",
}


def label(fact_code):
    base = fact_code.split(":")[0]
    return FACT_LABELS.get(base, base.replace("_", " ").capitalize())
