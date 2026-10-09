# DRAFT request to FIN-01 — not sent

Prepared locally by the travel-expense-claim Skill (run `replay-20261009T025958Z`). A person must review and send it; the Skill never sends requests.

FIN-01 is asked as the party who supplies each fact or decision below. Follow-up on missing replies: ADMIN-01 (Travel Administration Lead).

## claim C10 revision 1 (trip T10 r1, permit P10 r1)

- **late_permit** for COST-10 — permit P10 approved 2026-09-02 after first commitment 2026-09-01. Requested: Finance decides a late_permit exception for COST-10. Sources: initial-claims#page 10, receipts#page 5:R-COST-10, registers:merchant-payments#row 14:M-COST-10. (`RQ-C10-r1-late_permit-COST-10`, opened replay-20261009T025958Z/batch-1)

## claim C18 revision 2 (trip T18B r1)

- **finance_resolution_required** — cancellation-after-acceptance TC018 awaits Finance resolution; correction-after-acceptance C18 r2 awaits Finance resolution; transfer-after-cancellation F-C18-3 awaits Finance resolution. Requested: Finance records an explicit resolution for C18 at EUR 100.00. Sources: claim-updates#page 4. (`RQ-C18-r2-finance_resolution_required`, opened replay-20261009T025958Z/batch-4)
- **transfer_after_cancellation** — F-C18-3 settled EUR 100.00 after Finance cancelled REQ-C18. Requested: Finance resolves the late transfer on REQ-C18 (apply to a current revision or recover it). Sources: claim-updates#page 4, registers:finance-activity#row 21:F-C18-3. (`RQ-C18-r2-transfer_after_cancellation`, opened replay-20261009T025958Z/batch-4)

## claim C22 revision 1 (trip T22 r1)

- **missing_rate** for COST-22 — no Finance GBP rate for payment date 2026-09-01. Requested: Finance supplies or confirms the GBP rate for 2026-09-01. Sources: initial-claims#page 22, receipts#page 11:R-COST-22, registers:merchant-payments#row 26:M-COST-22. (`RQ-C22-r1-missing_rate-COST-22`, opened replay-20261009T025958Z/batch-1)

## claim C23 revision 1 (trip T23 r1)

- **missing_cap** for COST-23 — no lodging cap for BE in EUR on 2026-09-01. Requested: Finance supplies or confirms the BE lodging cap in EUR for 2026-09-01. Sources: initial-claims#page 23, receipts#page 12:R-COST-23, registers:merchant-payments#row 27:M-COST-23. (`RQ-C23-r1-missing_cap-COST-23`, opened replay-20261009T025958Z/batch-1)

## claim C25 revision 1 (trip T25 r1, permit P25 r1)

- **permit_unapproved** for COST-25 — permit P25 incomplete before commitment 2026-09-01. Requested: Finance decides a permit_unapproved exception for COST-25. Sources: initial-claims#page 24, receipts#page 14:R-COST-25, registers:merchant-payments#row 31:M-COST-25. (`RQ-C25-r1-permit_unapproved-COST-25`, opened replay-20261009T025958Z/batch-1)

## claim C112 revision 1 (trip T112 r1)

- **late_filing** for COST-112-1 — first submitted 2026-09-02 after deadline 2026-09-01. Requested: Finance grants or refuses a late-filing exception for C112 r1 COST-112-1. Sources: initial-claims#page 111, receipts#page 94:R-COST-112-1, registers:merchant-payments#row 192:M-COST-112-1. (`RQ-C112-r1-late_filing-COST-112-1`, opened replay-20261009T025958Z/batch-1)

## claim C116 revision 1 (trip T116 r1)

- **missing_cap** for COST-116-1 — no lodging cap for NL in USD on 2026-09-01. Requested: Finance supplies or confirms the NL lodging cap in USD for 2026-09-01. Sources: initial-claims#page 115, receipts#page 97:R-COST-116-1, registers:merchant-payments#row 197:M-COST-116-1, registers:fx#row 7:FX-USD. (`RQ-C116-r1-missing_cap-COST-116-1`, opened replay-20261009T025958Z/batch-1)
- **missing_rate** for COST-116-2 — no Finance GBP rate for payment date 2026-09-01. Requested: Finance supplies or confirms the GBP rate for 2026-09-01. Sources: initial-claims#page 115, receipts#page 98:R-COST-116-2, registers:merchant-payments#row 198:M-COST-116-2. (`RQ-C116-r1-missing_rate-COST-116-2`, opened replay-20261009T025958Z/batch-1)

## claim C117 revision 1 (trip T117 r1)

- **unknown_category** for COST-117-1 — receipt category 'entertainment' is not defined by policy POL-2026.2; eligibility unknown. Requested: Finance (FIN-01) supplies an authoritative definition of 'entertainment' or a specific eligibility instruction for COST-117-1 C117 r1 (claimed 10.00 EUR); the employee (EMP-03) may only be asked to clarify the purchase; the Travel Administration Lead (ADMIN-01) follows up. Sources: initial-claims#page 116, receipts#page 98:R-COST-117-1, registers:merchant-payments#row 199:M-COST-117-1. (`RQ-C117-r1-unknown_category-COST-117-1`, opened replay-20261009T025958Z/batch-1)
