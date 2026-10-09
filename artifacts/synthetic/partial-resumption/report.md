# SYNTHETIC scenario: partial-resumption

> **SYNTHETIC SCENARIO — every identifier is SYN-*. These records are invented test inputs, not Alderbridge source data, approvals, replies or Finance decisions.**

Fixture: `tests/fixtures/synthetic_partial_resumption.json`. Produced with `tec_cli.py synthetic-demo`, which runs the same engine and repair queue as a source run. It is kept under `artifacts/synthetic/`, outside `artifacts/runs/`, so it is never mistaken for a source run.

What it shows (interview 4, 01:20):

- **Partial reply:** a reply that answers part of a request resumes only the tasks it supports. The other tasks stay open.
- **Independent work:** an unrelated claim resumes on its own, as soon as its missing decision arrives.
- **No duplicates:** nothing is requested twice, and a redelivered Finance record has no effect.
- **Returned work:** a funding return goes to the budget owner, not the employee (interview 3, 10:48).
- **Stale approvals:** an approval given before late evidence arrived stops counting, and that review resumes (interview 3, 10:50).

## Claim state by batch

| Batch | Claim | Status | Allowed | Paid | Next owner | Lines (status, allowed) | Reason |
|---|---|---|---|---|---|---|---|
| 1 | SYN-C1 | held | — | EUR 0.00 | SYN-E1 | SYN-COST-1 unresolved EUR 60.00; SYN-COST-2 unresolved —; SYN-COST-3 unresolved EUR 40.00 | missing_payment_proof; missing_rate — no settled merchant transaction for SYN-COST-1 |
| 1 | SYN-C2 | held | EUR 120.00 | EUR 0.00 | SYN-BO | SYN-COST-4 supported EUR 120.00 | funding_decision — The budget owner (SYN-BO) returned revision 1 on 2026-09-03: Budget owner requests a funding review before committing. Repair requested: Obtain funding decision. Affected fields: trip, amount, evidence |
| 2 | SYN-C1 | held | — | EUR 0.00 | SYN-E1 | SYN-COST-1 supported EUR 60.00; SYN-COST-2 supported EUR 58.50; SYN-COST-3 unresolved EUR 40.00 | missing_payment_proof — no settled merchant transaction for SYN-COST-3 |
| 2 | SYN-C2 | pending | EUR 120.00 | EUR 0.00 | SYN-FIN | SYN-COST-4 supported EUR 120.00 | awaiting Finance settlement: EUR 0.00 of EUR 120.00 paid |
| 3 | SYN-C1 | ready | EUR 158.50 | EUR 0.00 | SYN-FIN | SYN-COST-1 supported EUR 60.00; SYN-COST-2 supported EUR 58.50; SYN-COST-3 supported EUR 40.00 | approved r1 for EUR 158.50; request REQ-SYN-C1 proposed to Finance |
| 3 | SYN-C2 | closed-reimbursed | EUR 120.00 | EUR 120.00 | — | SYN-COST-4 supported EUR 120.00 | r1 approved; net paid EUR 120.00 equals entitlement |
| 4 | SYN-C1 | closed-reimbursed | EUR 158.50 | EUR 158.50 | — | SYN-COST-1 supported EUR 60.00; SYN-COST-2 supported EUR 58.50; SYN-COST-3 supported EUR 40.00 | r1 approved; net paid EUR 158.50 equals entitlement |
| 4 | SYN-C2 | closed-reimbursed | EUR 120.00 | EUR 120.00 | — | SYN-COST-4 supported EUR 120.00 | r1 approved; net paid EUR 120.00 equals entitlement |

## Replies counted for the current revision

A reply admitted before evidence that arrived later stops counting (interview 3, 10:50), and the review resumes.

- batch-1 SYN-C1: SYN-D-C1-ADM-1
- batch-1 SYN-C2: SYN-D-C2-ADM-1, SYN-D-C2-BO-1, SYN-D-C2-SUP-1
- batch-2 SYN-C1: none
- batch-2 SYN-C2: SYN-D-C2-ADM-1, SYN-D-C2-BO-1, SYN-D-C2-BO-2, SYN-D-C2-SUP-1
- batch-3 SYN-C1: SYN-D-C1-ADM-3, SYN-D-C1-BO-3, SYN-D-C1-SUP-3
- batch-3 SYN-C2: SYN-D-C2-ADM-1, SYN-D-C2-BO-1, SYN-D-C2-BO-2, SYN-D-C2-SUP-1
- batch-4 SYN-C1: SYN-D-C1-ADM-3, SYN-D-C1-BO-3, SYN-D-C1-SUP-3
- batch-4 SYN-C2: SYN-D-C2-ADM-1, SYN-D-C2-BO-1, SYN-D-C2-BO-2, SYN-D-C2-SUP-1

## Repair queue by batch

**batch-1** — opened 4

- `opened` RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-1 — Settled merchant transaction missing (SYN-COST-1, owner SYN-E1)
- `opened` RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3 — Settled merchant transaction missing (SYN-COST-3, owner SYN-E1)
- `opened` RQ-SYN-C1-r1-missing_rate-SYN-COST-2 — Finance exchange rate missing (SYN-COST-2, owner SYN-FIN)
- `opened` RQ-SYN-C2-r1-funding_decision:budget_owner — Funding decision needed (SYN-C2, owner SYN-BO)

**batch-2** — partial-response 1, satisfied 3

- `satisfied` RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-1 — Settled merchant transaction missing (SYN-COST-1, owner SYN-E1); evidence: synthetic#merchant:SYN-M1
- `satisfied` RQ-SYN-C1-r1-missing_rate-SYN-COST-2 — Finance exchange rate missing (SYN-COST-2, owner SYN-FIN); evidence: synthetic#fx:SYN-FX-GBP
- `satisfied` RQ-SYN-C2-r1-funding_decision:budget_owner — Funding decision needed (SYN-C2, owner SYN-BO); evidence: synthetic#finance:SYN-F-C2-acc@batch-2, synthetic#review:SYN-D-C2-BO-2
- `partial-response` from SYN-E1 on SYN-C1 r1: answered RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-1; still open RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3

**batch-3** — satisfied 1

- `satisfied` RQ-SYN-C1-r1-missing_payment_proof-SYN-COST-3 — Settled merchant transaction missing (SYN-COST-3, owner SYN-E1); evidence: synthetic#merchant:SYN-M3

**batch-4** — no change


## Redeliveries

- Exact redelivery of finance `SYN-F-C2-1` in batch-4: no effect.

