"""Who supplies a returned-work request, decided by what the reviewer asked for.

Each route cites the interview that establishes its owner. The review ledger's
"Affected fields" column is the same for every row in the supplied workbook, so
the reviewer's repair text (then the reason) is what distinguishes a request.
A request matching no route, or more than one, is not guessed: it goes to the
Travel Administration Lead to clarify with the reviewer (an open point in
references/requirements.md).
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
                "No interview settles this kind of request; the Travel Administration Lead clarifies it with the "
                "reviewer (INT1 06:18 coordinates reviews; INT3 10:51 follows up on missing replies)")


def classify(repair, reason):
    """Return (kind, owner_source, label, basis). Repair text is read before the reason."""
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
