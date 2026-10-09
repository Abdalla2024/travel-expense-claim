# Travel expense claim — operations handoff (`run-20261009T023446Z`)

- **Mode:** fresh-read
- **Outcome:** success · **Case clock:** 2026-11-15 Europe/Amsterdam (frozen; arrival batch decides availability)
- **Code revision:** `93b2b5bdf0231f8454e212fa33543713c4c452c3` · **Policy:** POL-2026.2 (Notion block version 29)
- **Sealed snapshots:** [batch-1.json](batches/batch-1.json) `48ec6dc6993f…`, [batch-2.json](batches/batch-2.json) `01d159b4f8be…`, [batch-3.json](batches/batch-3.json) `a32245be80e9…`, [batch-4.json](batches/batch-4.json) `f653253e6955…`
- **Outputs:** [claims.csv](claims.csv) · [sources.json](sources.json) · [queue/items.json](queue/items.json) · [queue/events.jsonl](queue/events.jsonl) · [queue/drafts/](queue/drafts/)

People keep every approval, exception and payment decision. This run only prepared local work from supplied scenario facts: it sent nothing, booked nothing and moved no money.

## 1. Position after batch-4

| Status | Claims |
|---|---|
| closed-reimbursed | 103 |
| closed-no-payment | 0 |
| rejected | 1 |
| withdrawn | 1 |
| ready | 0 |
| pending | 5 |
| held | 11 |
| **total** | **121** |

- Net confirmed payments across all claims: **EUR 12034.15** (219 admitted Finance events).
- Reimbursed and closed: 103 claims, EUR 11934.15.
- Open claims: 16. Known outstanding balance on them: EUR 1205.01; 9 open claims have an unknown entitlement (blank money).

## 2. Unresolved work (owner, reason, evidence or action needed)

| Claim | Rev | Trip | Status | Allowed | Paid | Balance | Next owner | Reason | Next action |
|---|---|---|---|---|---|---|---|---|---|
| C08 | 1 | T08 | held | — | EUR 0.00 | — | EMP-01 | missing_payment_proof — no settled merchant transaction for COST-08 | Employee supplies the settled merchant transaction for COST-08 |
| C10 | 1 | T10 | held | — | EUR 0.00 | — | FIN-01 | late_permit — permit P10 approved 2026-09-02 after first commitment 2026-09-01 | Finance decides a late_permit exception for COST-10 |
| C18 | 2 | T18B | held | EUR 100.00 | EUR 100.00 | EUR 0.00 | FIN-01 | finance_resolution_required; transfer_after_cancellation — F-C18-3 settled EUR 100.00 after Finance cancelled REQ-C18 | Finance records an explicit resolution for C18 at EUR 100.00; Finance resolves the late transfer on REQ-C18 (apply to a current revision or recover it) |
| C21 | 1 | T21 | held | EUR 80.00 | EUR 0.00 | EUR 80.00 | EMP-01 | returned — budget_owner returned r1: Budget owner requests a funding review before committing. | Obtain funding decision. |
| C22 | 1 | T22 | held | — | EUR 0.00 | — | FIN-01 | missing_rate — no Finance GBP rate for payment date 2026-09-01 | Finance supplies or confirms the GBP rate for 2026-09-01 |
| C23 | 1 | T23 | held | — | EUR 0.00 | — | FIN-01 | missing_cap — no lodging cap for BE in EUR on 2026-09-01 | Finance supplies or confirms the BE lodging cap in EUR for 2026-09-01 |
| C25 | 1 | T25 | held | — | EUR 0.00 | — | FIN-01 | permit_unapproved — permit P25 incomplete before commitment 2026-09-01 | Finance decides a permit_unapproved exception for COST-25 |
| C112 | 1 | T112 | held | — | EUR 0.00 | — | FIN-01 | late_filing — first submitted 2026-09-02 after deadline 2026-09-01 | Finance grants or refuses a late-filing exception for C112 r1 COST-112-1 |
| C114 | 1 | T114 | held | — | EUR 0.00 | — | EMP-03 | missing_payment_proof — no settled merchant transaction for COST-114-2 | Employee supplies the settled merchant transaction for COST-114-2 |
| C116 | 1 | T116 | held | — | EUR 0.00 | — | FIN-01 | missing_cap; missing_rate — no lodging cap for NL in USD on 2026-09-01 | Finance supplies or confirms the GBP rate for 2026-09-01; Finance supplies or confirms the NL lodging cap in USD for 2026-09-01 |
| C117 | 1 | T117 | held | — | EUR 0.00 | — | ADMIN-01 | unknown_category — category 'entertainment' is not defined by policy | Administration obtains a policy classification for 'entertainment' (raise with operations lead) |
| C15 | 1 | T15 | pending | EUR 0.00 | EUR 0.00 | EUR 0.00 | ADMIN-01 | awaiting administration/budget_owner/supervisor review of r1 | ADMIN-01 responds (review or Finance outcome) |
| C26 | 1 | T26 | pending | EUR 100.00 | EUR 0.00 | EUR 100.00 | ADMIN-01 | awaiting administration/budget_owner/supervisor review of r1 | ADMIN-01 responds (review or Finance outcome) |
| C113 | 1 | T113 | pending | EUR 25.00 | EUR 0.00 | EUR 25.00 | ADMIN-01 | awaiting administration/budget_owner/supervisor review of r1 | ADMIN-01 responds (review or Finance outcome) |
| C118 | 1 | T118 | pending | EUR 0.00 | EUR 0.00 | EUR 0.00 | ADMIN-01 | awaiting administration/budget_owner/supervisor review of r1 | ADMIN-01 responds (review or Finance outcome) |
| C119 | 1 | T119 | pending | EUR 1000.01 | EUR 0.00 | EUR 1000.01 | DIR-01 | awaiting director review of r1 | DIR-01 responds (review or Finance outcome) |

## 3. Trip and permit cancellation processes

Cancellation processes are tracked separately from claims. A process with no claim is reported here and never turned into a claim row.

| Cancellation | Target | Trip / permit | Status | Requested | Effective | Affected claims | Original requests | Financial status | Next owner | Events |
|---|---|---|---|---|---|---|---|---|---|---|
| TC018 | trip | T18 r1 / no permit | confirmed | 2026-09-12T09:00:00Z | 2026-09-12T10:00:00Z | C18 | REQ-C18 | unresolved | FIN-01 | TC018-requested, TC018-confirmed |
| TC019 | trip | T19 r1 / no permit | confirmed | 2026-09-13T08:00:00Z | 2026-09-13T09:00:00Z | C19 | REQ-C19 | resolved | — | TC019-requested, TC019-confirmed |
| TC121 | permit | T121 r1 / P121 r1 | confirmed | 2026-09-10T10:00:00Z | 2026-09-12T10:00:00Z | C121 | REQ-C121 | resolved | — | TC121-requested, TC121-confirmed |
| TC122 | trip | T122 r1 / P122 r1 | confirmed | 2026-09-10T09:00:00Z | 2026-09-12T09:00:00Z | none (no claim) | — | no-financial-effect | — | TC122-requested, TC122-confirmed |

## 4. Repair queue

Grouping: by responsible person, then subject. There is one item per missing fact or return reason. Each item keeps its subject, revision, trip/permit revision, source locators, owner, next action, and the run/batch where it was opened and last changed. The history is append-only ([events.jsonl](queue/events.jsonl)). An item is marked satisfied only when the inputs that close that fact arrive. If a response from an owner covers only part of what was asked, the event is logged as `partial-response` and the unanswered items stay open. Drafts in [queue/drafts/](queue/drafts/) are local and unsent.

### Open items after batch-4

| Owner | Item | Subject | Rev | Trip/permit rev | Missing fact or return reason | Next action | Opened | Last changed |
|---|---|---|---|---|---|---|---|---|
| ADMIN-01 | `RQ-C117-r1-unknown_category-COST-117-1` | claim C117 COST-117-1 | 1 | T117 r1 | category 'entertainment' is not defined by policy | Administration obtains a policy classification for 'entertainment' (raise with operations lead) | batch-1 | batch-1 |
| EMP-01 | `RQ-C08-r1-missing_payment_proof-COST-08` | claim C08 COST-08 | 1 | T08 r1 | no settled merchant transaction for COST-08 | Employee supplies the settled merchant transaction for COST-08 | batch-1 | batch-1 |
| EMP-01 | `RQ-C21-r1-returned:D-C21-1-claim-budget_owner-1` | claim C21 | 1 | T21 r1 | budget_owner returned r1: Budget owner requests a funding review before committing. | Obtain funding decision. | batch-1 | batch-1 |
| EMP-03 | `RQ-C114-r1-missing_payment_proof-COST-114-2` | claim C114 COST-114-2 | 1 | T114 r1 | no settled merchant transaction for COST-114-2 | Employee supplies the settled merchant transaction for COST-114-2 | batch-1 | batch-1 |
| FIN-01 | `RQ-C10-r1-late_permit-COST-10` | claim C10 COST-10 | 1 | T10 r1 / P10 r1 | permit P10 approved 2026-09-02 after first commitment 2026-09-01 | Finance decides a late_permit exception for COST-10 | batch-1 | batch-1 |
| FIN-01 | `RQ-C18-r2-finance_resolution_required` | claim C18 | 2 | T18B r1 | cancellation-after-acceptance TC018 awaits Finance resolution; correction-after-acceptance C18 r2 awaits Finance resolution; transfer-after-cancellation F-C18-3 awaits Finance resolution | Finance records an explicit resolution for C18 at EUR 100.00 | batch-4 | batch-4 |
| FIN-01 | `RQ-C18-r2-transfer_after_cancellation` | claim C18 | 2 | T18B r1 | F-C18-3 settled EUR 100.00 after Finance cancelled REQ-C18 | Finance resolves the late transfer on REQ-C18 (apply to a current revision or recover it) | batch-4 | batch-4 |
| FIN-01 | `RQ-C22-r1-missing_rate-COST-22` | claim C22 COST-22 | 1 | T22 r1 | no Finance GBP rate for payment date 2026-09-01 | Finance supplies or confirms the GBP rate for 2026-09-01 | batch-1 | batch-1 |
| FIN-01 | `RQ-C23-r1-missing_cap-COST-23` | claim C23 COST-23 | 1 | T23 r1 | no lodging cap for BE in EUR on 2026-09-01 | Finance supplies or confirms the BE lodging cap in EUR for 2026-09-01 | batch-1 | batch-1 |
| FIN-01 | `RQ-C25-r1-permit_unapproved-COST-25` | claim C25 COST-25 | 1 | T25 r1 / P25 r1 | permit P25 incomplete before commitment 2026-09-01 | Finance decides a permit_unapproved exception for COST-25 | batch-1 | batch-1 |
| FIN-01 | `RQ-C112-r1-late_filing-COST-112-1` | claim C112 COST-112-1 | 1 | T112 r1 | first submitted 2026-09-02 after deadline 2026-09-01 | Finance grants or refuses a late-filing exception for C112 r1 COST-112-1 | batch-1 | batch-1 |
| FIN-01 | `RQ-C116-r1-missing_cap-COST-116-1` | claim C116 COST-116-1 | 1 | T116 r1 | no lodging cap for NL in USD on 2026-09-01 | Finance supplies or confirms the NL lodging cap in USD for 2026-09-01 | batch-1 | batch-1 |
| FIN-01 | `RQ-C116-r1-missing_rate-COST-116-2` | claim C116 COST-116-2 | 1 | T116 r1 | no Finance GBP rate for payment date 2026-09-01 | Finance supplies or confirms the GBP rate for 2026-09-01 | batch-1 | batch-1 |

### Queue updates by batch

**run-20261009T023446Z / batch-1** — opened 16

- 16 items opened (initial backlog; see table above and events.jsonl)

**run-20261009T023446Z / batch-2** — opened 4, satisfied 3

- `opened` `RQ-C121-r1-travel_cancellation:TC121-COST-121` (FIN-01)
- `opened` `RQ-C17-r1-payment_failed` (FIN-01)
- `opened` `RQ-C18-r1-travel_cancellation:TC018-COST-18` (FIN-01)
- `opened` `RQ-C20-r1-overpayment` (FIN-01)
- `satisfied` `RQ-C121-r1-cancellation_pending:TC121` (SUP-01); evidence: registers:travel-cancellations#row 9:TC121-confirmed
- `satisfied` `RQ-TC121-decision-pending` (SUP-01); evidence: registers:travel-cancellations#row 9:TC121-confirmed
- `satisfied` `RQ-TC122-decision-pending` (SUP-01); evidence: registers:travel-cancellations#row 7:TC122-confirmed

**run-20261009T023446Z / batch-3** — opened 2, partial-response 1, satisfied 2, superseded 4

- `opened` `RQ-C19-r2-travel_cancellation:TC019-COST-19` (FIN-01)
- `opened` `RQ-C20-r1-finance_resolution_required` (FIN-01)
- `superseded` `RQ-C09-r1-returned:D-C09-1-claim-budget_owner-1` (EMP-01); evidence: claim-updates#page 1, registers:finance-activity#row 46:F-C09-accepted
- `superseded` `RQ-C12-r1-late_filing-COST-12` (FIN-01); evidence: claim-updates#page 5, registers:finance-activity#row 47:F-C12-accepted
- `superseded` `RQ-C121-r1-travel_cancellation:TC121-COST-121` (FIN-01); evidence: claim-updates#page 6, registers:finance-activity#row 224:F-C121-accepted
- `satisfied` `RQ-C17-r1-payment_failed` (FIN-01); evidence: registers:finance-activity#row 17:F-C17-2
- `superseded` `RQ-C18-r1-travel_cancellation:TC018-COST-18` (FIN-01); evidence: claim-updates#page 4, registers:finance-activity#row 20:F-C18-2
- `satisfied` `RQ-C20-r1-overpayment` (FIN-01); evidence: registers:finance-activity#row 27:F-C20-2
- `partial-response` FIN-01 C20 r1: satisfied RQ-C20-r1-overpayment; still open RQ-C20-r1-finance_resolution_required

**run-20261009T023446Z / batch-4** — opened 2, satisfied 1, superseded 1

- `opened` `RQ-C18-r2-finance_resolution_required` (FIN-01)
- `opened` `RQ-C18-r2-transfer_after_cancellation` (FIN-01)
- `superseded` `RQ-C19-r2-travel_cancellation:TC019-COST-19` (FIN-01); evidence: claim-updates#page 7, registers:finance-activity#row 24:F-C19-3, registers:finance-activity#row 25:F-C19-4
- `satisfied` `RQ-C20-r1-finance_resolution_required` (FIN-01); evidence: registers:finance-activity#row 28:F-C20-3

## 5. Significant changes by batch

### batch-1 — `batches/batch-1.json` (sha256 `48ec6dc6993f9cab…`, predecessor none)

Claims known: 120 (held 13, pending 105, rejected 1, withdrawn 1). Admitted Finance events: 100. Open issues: 16.

Events consumed:

- [cancellation] TC122: trip cancellation requested for T122 by EMP-01 — registers:travel-cancellations#row 6:TC122-requested
- [cancellation] TC121: permit cancellation requested for P121 by EMP-01 — registers:travel-cancellations#row 8:TC121-requested
- [review] C09: budget_owner return r1: Please supply the revised trip evidence. — registers:review-ledger#row 32:D-C09-1-claim-budget_owner-1
- [review] C14: budget_owner reject r1: Client work was cancelled. — registers:review-ledger#row 40:D-C14-1-claim-budget_owner-1
- [review] C21: budget_owner return r1: Budget owner requests a funding review before committing. — registers:review-ledger#row 57:D-C21-1-claim-budget_owner-1

### batch-2 — `batches/batch-2.json` (sha256 `01d159b4f8be5d4e…`, predecessor `batches/batch-1.json`)

Claims known: 120 (closed-reimbursed 95, held 15, pending 8, rejected 1, withdrawn 1). Admitted Finance events: 200. Open issues: 17.

State transitions (paid/allowed):

- C01 r1 pending EUR 0.00/EUR 100.00 → r1 closed-reimbursed EUR 100.00/EUR 100.00
- C02 r1 pending EUR 0.00/EUR 540.00 → r1 closed-reimbursed EUR 540.00/EUR 540.00
- C03 r1 pending EUR 0.00/EUR 200.00 → r1 closed-reimbursed EUR 200.00/EUR 200.00
- C04 r1 pending EUR 0.00/EUR 100.00 → r1 closed-reimbursed EUR 100.00/EUR 100.00
- C05 r1 pending EUR 0.00/EUR 1000.00 → r1 closed-reimbursed EUR 1000.00/EUR 1000.00
- C06 r1 pending EUR 0.00/EUR 1000.01 → r1 closed-reimbursed EUR 1000.01/EUR 1000.01
- C07 r1 pending EUR 0.00/EUR 300.00 → r1 closed-reimbursed EUR 300.00/EUR 300.00
- C11 r1 pending EUR 0.00/EUR 60.00 → r1 closed-reimbursed EUR 60.00/EUR 60.00
- C16 r1 pending EUR 0.00/EUR 100.00 → r1 pending EUR 40.00/EUR 100.00
- C18 r1 pending EUR 0.00/EUR 100.00 → r1 held EUR 0.00/—
- C19 r1 pending EUR 0.00/EUR 100.00 → r1 closed-reimbursed EUR 100.00/EUR 100.00
- C20 r1 pending EUR 0.00/EUR 100.00 → r1 held EUR 110.00/EUR 100.00
- C27 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C28 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C29 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C30 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C31 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C32 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C33 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C34 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C35 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C36 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C37 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C38 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C39 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C40 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C41 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C42 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C43 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C44 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C45 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C46 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C47 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C48 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C49 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C50 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C51 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C52 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C53 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C54 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C55 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C56 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C57 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C58 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C59 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C60 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C61 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C62 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C63 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C64 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C65 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C66 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C67 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C68 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C69 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C70 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C71 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C72 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C73 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C74 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C75 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C76 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C77 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C78 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C79 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C80 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C81 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C82 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C83 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C84 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C85 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C86 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C87 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C88 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C89 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C90 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C91 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C92 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C93 r1 pending EUR 0.00/EUR 35.00 → r1 closed-reimbursed EUR 35.00/EUR 35.00
- C94 r1 pending EUR 0.00/EUR 45.00 → r1 closed-reimbursed EUR 45.00/EUR 45.00
- C95 r1 pending EUR 0.00/EUR 55.00 → r1 closed-reimbursed EUR 55.00/EUR 55.00
- C96 r1 pending EUR 0.00/EUR 65.00 → r1 closed-reimbursed EUR 65.00/EUR 65.00
- C97 r1 pending EUR 0.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C98 r1 pending EUR 0.00/EUR 85.00 → r1 closed-reimbursed EUR 85.00/EUR 85.00
- C99 r1 pending EUR 0.00/EUR 999.99 → r1 closed-reimbursed EUR 999.99/EUR 999.99
- C100 r1 pending EUR 0.00/EUR 1000.00 → r1 closed-reimbursed EUR 1000.00/EUR 1000.00
- C101 r1 pending EUR 0.00/EUR 1000.01 → r1 closed-reimbursed EUR 1000.01/EUR 1000.01
- C102 r1 pending EUR 0.00/EUR 149.99 → r1 closed-reimbursed EUR 149.99/EUR 149.99
- C103 r1 pending EUR 0.00/EUR 150.00 → r1 closed-reimbursed EUR 150.00/EUR 150.00
- C104 r1 pending EUR 0.00/EUR 150.00 → r1 closed-reimbursed EUR 150.00/EUR 150.00
- C105 r1 pending EUR 0.00/EUR 39.99 → r1 closed-reimbursed EUR 39.99/EUR 39.99
- C106 r1 pending EUR 0.00/EUR 40.00 → r1 closed-reimbursed EUR 40.00/EUR 40.00
- C107 r1 pending EUR 0.00/EUR 40.00 → r1 closed-reimbursed EUR 40.00/EUR 40.00
- C108 r1 pending EUR 0.00/EUR 2.08 → r1 closed-reimbursed EUR 2.08/EUR 2.08
- C109 r1 pending EUR 0.00/EUR 2.08 → r1 closed-reimbursed EUR 2.08/EUR 2.08
- C110 r1 pending EUR 0.00/EUR 25.00 → r1 closed-reimbursed EUR 25.00/EUR 25.00
- C111 r1 pending EUR 0.00/EUR 25.00 → r1 closed-reimbursed EUR 25.00/EUR 25.00
- C115 r1 pending EUR 0.00/EUR 15.00 → r1 closed-reimbursed EUR 15.00/EUR 15.00
- C120 r1 pending EUR 0.00/EUR 75.00 → r1 pending EUR 30.00/EUR 75.00
- C121 r1 held EUR 0.00/EUR 30.00 → r1 held EUR 0.00/—

Events consumed:

- [cancellation] TC018: trip cancellation requested for T18 by EMP-01 — registers:travel-cancellations#row 10:TC018-requested
- [cancellation] TC122: confirmed by SUP-01, effective 2026-09-12T09:00:00Z — registers:travel-cancellations#row 7:TC122-confirmed
- [cancellation] TC018: confirmed by SUP-01, effective 2026-09-12T10:00:00Z — registers:travel-cancellations#row 11:TC018-confirmed
- [cancellation] TC121: confirmed by SUP-01, effective 2026-09-12T10:00:00Z — registers:travel-cancellations#row 9:TC121-confirmed
- [finance] C01: F-C01-1 settled REQ-C01 EUR 100.00 (accepted -> settled) — registers:finance-activity#row 6:F-C01-1
- [finance] C02: F-C02-1 settled REQ-C02 EUR 540.00 (accepted -> settled) — registers:finance-activity#row 7:F-C02-1
- [finance] C03: F-C03-1 settled REQ-C03 EUR 200.00 (accepted -> settled) — registers:finance-activity#row 8:F-C03-1
- [finance] C04: F-C04-1 settled REQ-C04 EUR 100.00 (accepted -> settled) — registers:finance-activity#row 9:F-C04-1
- [finance] C05: F-C05-1 settled REQ-C05 EUR 1000.00 (accepted -> settled) — registers:finance-activity#row 10:F-C05-1
- [finance] C06: F-C06-1 settled REQ-C06 EUR 1000.01 (accepted -> settled) — registers:finance-activity#row 11:F-C06-1
- [finance] C07: F-C07-1 settled REQ-C07 EUR 300.00 (accepted -> settled) — registers:finance-activity#row 12:F-C07-1
- [finance] C100: F-C100-1 settled REQ-C100 EUR 1000.00 (accepted -> settled) — registers:finance-activity#row 196:F-C100-1
- [finance] C101: F-C101-1 settled REQ-C101 EUR 1000.01 (accepted -> settled) — registers:finance-activity#row 198:F-C101-1
- [finance] C102: F-C102-1 settled REQ-C102 EUR 149.99 (accepted -> settled) — registers:finance-activity#row 200:F-C102-1
- [finance] C103: F-C103-1 settled REQ-C103 EUR 150.00 (accepted -> settled) — registers:finance-activity#row 202:F-C103-1
- [finance] C104: F-C104-1 settled REQ-C104 EUR 150.00 (accepted -> settled) — registers:finance-activity#row 204:F-C104-1
- [finance] C105: F-C105-1 settled REQ-C105 EUR 39.99 (accepted -> settled) — registers:finance-activity#row 206:F-C105-1
- [finance] C106: F-C106-1 settled REQ-C106 EUR 40.00 (accepted -> settled) — registers:finance-activity#row 208:F-C106-1
- [finance] C107: F-C107-1 settled REQ-C107 EUR 40.00 (accepted -> settled) — registers:finance-activity#row 210:F-C107-1
- [finance] C108: F-C108-1 settled REQ-C108 EUR 2.08 (accepted -> settled) — registers:finance-activity#row 212:F-C108-1
- [finance] C109: F-C109-1 settled REQ-C109 EUR 2.08 (accepted -> settled) — registers:finance-activity#row 214:F-C109-1
- [finance] C11: F-C11-1 settled REQ-C11 EUR 60.00 (accepted -> settled) — registers:finance-activity#row 13:F-C11-1
- [finance] C110: F-C110-1 settled REQ-C110 EUR 25.00 (accepted -> settled) — registers:finance-activity#row 216:F-C110-1
- [finance] C111: F-C111-1 settled REQ-C111 EUR 25.00 (accepted -> settled) — registers:finance-activity#row 218:F-C111-1
- [finance] C115: F-C115-1 settled REQ-C115 EUR 15.00 (accepted -> settled) — registers:finance-activity#row 220:F-C115-1
- [finance] C120: F-C120-1 settled REQ-C120 EUR 30.00 — registers:finance-activity#row 222:F-C120-1
- [finance] C16: F-C16-1 settled REQ-C16 EUR 40.00 — registers:finance-activity#row 14:F-C16-1
- [finance] C17: F-C17-1 failed REQ-C17 — registers:finance-activity#row 16:F-C17-1
- [finance] C18: F-C18-1 cancellation_requested REQ-C18 (accepted -> cancel-pending) — registers:finance-activity#row 19:F-C18-1
- [finance] C19: F-C19-1 settled REQ-C19 EUR 100.00 (accepted -> settled) — registers:finance-activity#row 22:F-C19-1
- [finance] C20: F-C20-1 settled REQ-C20 EUR 110.00 (accepted -> settled) — registers:finance-activity#row 26:F-C20-1
- [finance] C27: F-C27-1 settled REQ-C27 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 50:F-C27-1
- [finance] C28: F-C28-1 settled REQ-C28 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 52:F-C28-1
- [finance] C29: F-C29-1 settled REQ-C29 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 54:F-C29-1
- [finance] C30: F-C30-1 settled REQ-C30 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 56:F-C30-1
- [finance] C31: F-C31-1 settled REQ-C31 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 58:F-C31-1
- [finance] C32: F-C32-1 settled REQ-C32 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 60:F-C32-1
- [finance] C33: F-C33-1 settled REQ-C33 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 62:F-C33-1
- [finance] C34: F-C34-1 settled REQ-C34 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 64:F-C34-1
- [finance] C35: F-C35-1 settled REQ-C35 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 66:F-C35-1
- [finance] C36: F-C36-1 settled REQ-C36 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 68:F-C36-1
- [finance] C37: F-C37-1 settled REQ-C37 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 70:F-C37-1
- [finance] C38: F-C38-1 settled REQ-C38 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 72:F-C38-1
- [finance] C39: F-C39-1 settled REQ-C39 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 74:F-C39-1
- [finance] C40: F-C40-1 settled REQ-C40 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 76:F-C40-1
- [finance] C41: F-C41-1 settled REQ-C41 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 78:F-C41-1
- [finance] C42: F-C42-1 settled REQ-C42 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 80:F-C42-1
- [finance] C43: F-C43-1 settled REQ-C43 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 82:F-C43-1
- [finance] C44: F-C44-1 settled REQ-C44 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 84:F-C44-1
- [finance] C45: F-C45-1 settled REQ-C45 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 86:F-C45-1
- [finance] C46: F-C46-1 settled REQ-C46 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 88:F-C46-1
- [finance] C47: F-C47-1 settled REQ-C47 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 90:F-C47-1
- [finance] C48: F-C48-1 settled REQ-C48 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 92:F-C48-1
- [finance] C49: F-C49-1 settled REQ-C49 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 94:F-C49-1
- [finance] C50: F-C50-1 settled REQ-C50 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 96:F-C50-1
- [finance] C51: F-C51-1 settled REQ-C51 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 98:F-C51-1
- [finance] C52: F-C52-1 settled REQ-C52 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 100:F-C52-1
- [finance] C53: F-C53-1 settled REQ-C53 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 102:F-C53-1
- [finance] C54: F-C54-1 settled REQ-C54 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 104:F-C54-1
- [finance] C55: F-C55-1 settled REQ-C55 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 106:F-C55-1
- [finance] C56: F-C56-1 settled REQ-C56 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 108:F-C56-1
- [finance] C57: F-C57-1 settled REQ-C57 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 110:F-C57-1
- [finance] C58: F-C58-1 settled REQ-C58 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 112:F-C58-1
- [finance] C59: F-C59-1 settled REQ-C59 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 114:F-C59-1
- [finance] C60: F-C60-1 settled REQ-C60 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 116:F-C60-1
- [finance] C61: F-C61-1 settled REQ-C61 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 118:F-C61-1
- [finance] C62: F-C62-1 settled REQ-C62 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 120:F-C62-1
- [finance] C63: F-C63-1 settled REQ-C63 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 122:F-C63-1
- [finance] C64: F-C64-1 settled REQ-C64 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 124:F-C64-1
- [finance] C65: F-C65-1 settled REQ-C65 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 126:F-C65-1
- [finance] C66: F-C66-1 settled REQ-C66 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 128:F-C66-1
- [finance] C67: F-C67-1 settled REQ-C67 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 130:F-C67-1
- [finance] C68: F-C68-1 settled REQ-C68 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 132:F-C68-1
- [finance] C69: F-C69-1 settled REQ-C69 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 134:F-C69-1
- [finance] C70: F-C70-1 settled REQ-C70 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 136:F-C70-1
- [finance] C71: F-C71-1 settled REQ-C71 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 138:F-C71-1
- [finance] C72: F-C72-1 settled REQ-C72 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 140:F-C72-1
- [finance] C73: F-C73-1 settled REQ-C73 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 142:F-C73-1
- [finance] C74: F-C74-1 settled REQ-C74 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 144:F-C74-1
- [finance] C75: F-C75-1 settled REQ-C75 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 146:F-C75-1
- [finance] C76: F-C76-1 settled REQ-C76 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 148:F-C76-1
- [finance] C77: F-C77-1 settled REQ-C77 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 150:F-C77-1
- [finance] C78: F-C78-1 settled REQ-C78 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 152:F-C78-1
- [finance] C79: F-C79-1 settled REQ-C79 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 154:F-C79-1
- [finance] C80: F-C80-1 settled REQ-C80 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 156:F-C80-1
- [finance] C81: F-C81-1 settled REQ-C81 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 158:F-C81-1
- [finance] C82: F-C82-1 settled REQ-C82 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 160:F-C82-1
- [finance] C83: F-C83-1 settled REQ-C83 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 162:F-C83-1
- [finance] C84: F-C84-1 settled REQ-C84 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 164:F-C84-1
- [finance] C85: F-C85-1 settled REQ-C85 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 166:F-C85-1
- [finance] C86: F-C86-1 settled REQ-C86 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 168:F-C86-1
- [finance] C87: F-C87-1 settled REQ-C87 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 170:F-C87-1
- [finance] C88: F-C88-1 settled REQ-C88 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 172:F-C88-1
- [finance] C89: F-C89-1 settled REQ-C89 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 174:F-C89-1
- [finance] C90: F-C90-1 settled REQ-C90 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 176:F-C90-1
- [finance] C91: F-C91-1 settled REQ-C91 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 178:F-C91-1
- [finance] C92: F-C92-1 settled REQ-C92 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 180:F-C92-1
- [finance] C93: F-C93-1 settled REQ-C93 EUR 35.00 (accepted -> settled) — registers:finance-activity#row 182:F-C93-1
- [finance] C94: F-C94-1 settled REQ-C94 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 184:F-C94-1
- [finance] C95: F-C95-1 settled REQ-C95 EUR 55.00 (accepted -> settled) — registers:finance-activity#row 186:F-C95-1
- [finance] C96: F-C96-1 settled REQ-C96 EUR 65.00 (accepted -> settled) — registers:finance-activity#row 188:F-C96-1
- [finance] C97: F-C97-1 settled REQ-C97 EUR 75.00 (accepted -> settled) — registers:finance-activity#row 190:F-C97-1
- [finance] C98: F-C98-1 settled REQ-C98 EUR 85.00 (accepted -> settled) — registers:finance-activity#row 192:F-C98-1
- [finance] C99: F-C99-1 settled REQ-C99 EUR 999.99 (accepted -> settled) — registers:finance-activity#row 194:F-C99-1

### batch-3 — `batches/batch-3.json` (sha256 `a32245be80e91bfe…`, predecessor `batches/batch-2.json`)

Claims known: 121 (closed-reimbursed 96, held 12, pending 11, rejected 1, withdrawn 1). Admitted Finance events: 210. Open issues: 13.

State transitions (paid/allowed):

- C09 r1 held EUR 0.00/EUR 80.00 → r2 pending EUR 0.00/EUR 80.00
- C12 r1 held EUR 0.00/— → r2 pending EUR 0.00/EUR 70.00
- C16 r1 pending EUR 40.00/EUR 100.00 → r1 closed-reimbursed EUR 100.00/EUR 100.00
- C18 r1 held EUR 0.00/— → r2 pending EUR 0.00/EUR 100.00
- C19 r1 closed-reimbursed EUR 100.00/EUR 100.00 → r2 held EUR 100.00/—
- C20 r1 held EUR 110.00/EUR 100.00 → r1 held EUR 100.00/EUR 100.00
- C24 new r1 → pending
- C120 r1 pending EUR 30.00/EUR 75.00 → r1 closed-reimbursed EUR 75.00/EUR 75.00
- C121 r1 held EUR 0.00/— → r2 pending EUR 0.00/EUR 20.00

Events consumed:

- [revision] C09: r1 -> r2 (Trip replaced after client rescheduling) — claim-updates#page 1
- [revision] C19: r1 -> r2 (Finance approved corrected supported amount) — claim-updates#page 2
- [revision] C18: r1 -> r2 (Trip reassigned while cancellation is awaiting Finance) — claim-updates#page 4
- [revision] C12: r1 -> r2 (Finance grants the documented late-filing exception) — claim-updates#page 5
- [revision] C121: r1 -> r2 (Finance confirms supported remaining cost after permit cancellation) — claim-updates#page 6
- [cancellation] TC019: trip cancellation requested for T19 by EMP-01 — registers:travel-cancellations#row 12:TC019-requested
- [cancellation] TC019: confirmed by SUP-01, effective 2026-09-13T09:00:00Z — registers:travel-cancellations#row 13:TC019-confirmed
- [request] C09: REQ-C09 proposed for EUR 80.00 (r2)
- [request] C12: REQ-C12 proposed for EUR 70.00 (r2)
- [request] C24: REQ-C24 proposed for EUR 50.00 (r1)
- [request] C121: REQ-C121 proposed for EUR 20.00 (r2)
- [finance] C09: F-C09-accepted accepted REQ-C09 EUR 80.00 (proposed -> accepted) — registers:finance-activity#row 46:F-C09-accepted
- [finance] C12: F-C12-accepted accepted REQ-C12 EUR 70.00 (proposed -> accepted) — registers:finance-activity#row 47:F-C12-accepted
- [finance] C120: F-C120-2 settled REQ-C120 EUR 45.00 (accepted -> settled) — registers:finance-activity#row 223:F-C120-2
- [finance] C121: F-C121-accepted accepted REQ-C121 EUR 20.00 (proposed -> accepted) — registers:finance-activity#row 224:F-C121-accepted
- [finance] C16: F-C16-2 settled REQ-C16 EUR 60.00 (accepted -> settled) — registers:finance-activity#row 15:F-C16-2
- [finance] C17: F-C17-2 retry_authorized REQ-C17 — registers:finance-activity#row 17:F-C17-2
- [finance] C18: F-C18-2 cancelled REQ-C18 (cancel-pending -> cancelled) — registers:finance-activity#row 20:F-C18-2
- [finance] C19: F-C19-2 adjustment REQ-C19 EUR 80.00 — registers:finance-activity#row 23:F-C19-2
- [finance] C20: F-C20-2 refund REQ-C20 EUR 10.00 — registers:finance-activity#row 27:F-C20-2
- [finance] C24: F-C24-accepted accepted REQ-C24 EUR 50.00 (proposed -> accepted) — registers:finance-activity#row 48:F-C24-accepted

### batch-4 — `batches/batch-4.json` (sha256 `f653253e6955b5f4…`, predecessor `batches/batch-3.json`)

Claims known: 121 (closed-reimbursed 103, held 11, pending 5, rejected 1, withdrawn 1). Admitted Finance events: 219. Open issues: 13.

State transitions (paid/allowed):

- C09 r2 pending EUR 0.00/EUR 80.00 → r2 closed-reimbursed EUR 80.00/EUR 80.00
- C12 r2 pending EUR 0.00/EUR 70.00 → r2 closed-reimbursed EUR 70.00/EUR 70.00
- C17 r1 pending EUR 0.00/EUR 100.00 → r1 closed-reimbursed EUR 100.00/EUR 100.00
- C18 r2 pending EUR 0.00/EUR 100.00 → r2 held EUR 100.00/EUR 100.00
- C19 r2 held EUR 100.00/— → r3 closed-reimbursed EUR 80.00/EUR 80.00
- C20 r1 held EUR 100.00/EUR 100.00 → r1 closed-reimbursed EUR 100.00/EUR 100.00
- C24 r1 pending EUR 0.00/EUR 50.00 → r1 closed-reimbursed EUR 50.00/EUR 50.00
- C121 r2 pending EUR 0.00/EUR 20.00 → r2 closed-reimbursed EUR 20.00/EUR 20.00

Events consumed:

- [revision] C19: r2 -> r3 (Finance confirms retained business cost after trip cancellation) — claim-updates#page 7
- [replay] TC122: exact redelivery of TC122-confirmed: no effect — registers:travel-cancellations#row 14:TC122-confirmed
- [replay] C01: exact redelivery of F-C01-1 in batch 4: no effect — registers:finance-activity#row 31:F-C01-1
- [finance] C09: F-C09-1 settled REQ-C09 EUR 80.00 (accepted -> settled) — registers:finance-activity#row 29:F-C09-1
- [finance] C12: F-C12-1 settled REQ-C12 EUR 70.00 (accepted -> settled) — registers:finance-activity#row 32:F-C12-1
- [finance] C121: F-C121-1 settled REQ-C121 EUR 20.00 (accepted -> settled) — registers:finance-activity#row 225:F-C121-1
- [finance] C17: F-C17-3 settled REQ-C17 EUR 100.00 (accepted -> settled) — registers:finance-activity#row 18:F-C17-3
- [finance] C18: F-C18-3 settled REQ-C18 EUR 100.00 — registers:finance-activity#row 21:F-C18-3
- [finance] C19: F-C19-3 refund REQ-C19 EUR 20.00 — registers:finance-activity#row 24:F-C19-3
- [finance] C19: F-C19-4 resolution REQ-C19 EUR 80.00 — registers:finance-activity#row 25:F-C19-4
- [finance] C20: F-C20-3 resolution REQ-C20 EUR 100.00 — registers:finance-activity#row 28:F-C20-3
- [finance] C24: F-C24-1 settled REQ-C24 EUR 50.00 (accepted -> settled) — registers:finance-activity#row 30:F-C24-1

## 6. Replays, rejected imports and unmatched events

- Exact redelivery of cancellation `TC122-confirmed` in batch-4: no effect. Event identity and money were preserved.
- Exact redelivery of finance `F-C01-1` in batch-4: no effect. Event identity and money were preserved.
- No review, Finance or cancellation delivery was rejected or left unmatched.

## 7. Budget ledger context (for reviewers; not an approval)

Allocation EUR 20000.00 − prior net settled EUR 2000.00 − prior remaining commitments EUR 3000.00 − this workflow's accepted requests EUR 11954.15 = **EUR 3045.85** available (Consulting / Client-A / 2026; each commitment's settled portion is subtracted once).

## 8. Sources and limitations

`sources.json` source_version `content-set-sha256:c4dec79a5a379f2d2830410ba75f3901f282135452dbbbceed5082b6bf7f166e`.

| source_id | status | completeness | locator | observed_at (UTC) | version | sha256 | path |
|---|---|---|---|---|---|---|---|
| policy | read | complete | Notion page 3d80b700-541e-81ed-93eb-d386abc1dcb0, 16 content blocks, title 'Project D · Alderbridge travel reimbursement policy · POL-2026.2' | 2026-10-09T02:34:46Z | notion-block-version:29; last_edited_time:2026-09-12T04:41:17.498000Z | a03594e3cf1eb139… | sources/policy/notion-page-chunk.json |
| registers:people | read | complete | tab 'People', header row 5, data rows 6-19 (14 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:trips | read | complete | tab 'Trips', header row 5, data rows 6-128 (123 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:merchant-payments | read | complete | tab 'Merchant payments', header row 5, data rows 6-206 (201 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:fx | read | complete | tab 'FX', header row 5, data rows 6-7 (2 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:caps | read | complete | tab 'Caps', header row 5, data rows 6-7 (2 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:budget | read | complete | tab 'Budget', header row 5, data rows 6-8 (3 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:review-ledger | read | complete | tab 'Review ledger', header row 5, data rows 6-312 (307 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:review-packets | read | complete | tab 'Review packets', header row 5, data rows 6-312 (307 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:finance-activity | read | complete | tab 'Finance activity', header row 5, data rows 6-225 (220 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| registers:travel-cancellations | read | complete | tab 'Travel cancellations', header row 5, data rows 6-14 (9 rows) | 2026-10-09T02:34:47Z | null | 75843f989144244e… | sources/registers/travel-registers.xlsx |
| initial-claims | read | complete | PDF pages 1-120 (footer 'Page X of 120' verified) | 2026-10-09T02:34:47Z | http:{"last-modified": "Sat, 12 Sep 2026 02:56:31 GMT"} | b42a28754b187736… | sources/binders/initial-claim-binder.pdf |
| claim-updates | read | complete | PDF pages 1-7 (footer 'Page X of 7' verified) | 2026-10-09T02:34:49Z | http:{"last-modified": "Sat, 12 Sep 2026 02:56:29 GMT"} | 03c15787d18e2928… | sources/binders/claim-updates-binder.pdf |
| receipts | read | complete | PDF pages 1-102 (footer 'Page X of 102' verified) | 2026-10-09T02:34:50Z | http:{"last-modified": "Sat, 12 Sep 2026 02:56:31 GMT"} | 4c3dc47f187ccc5c… | sources/binders/receipt-binder.pdf |

- Policy paragraph 1 says 'Read the fixed source manifest before each run' and cites LOG-0014. The operations lead confirmed in interview 2 (10:03, 10:11) that no such document exists and instructed us to proceed with the five native sources (10:12). The reference stays recorded here as unresolved.
- The workbook and the PDFs expose no native revision identifier (interview 2, 10:09). Their `version` is the HTTP validator the server returned, or null; identity is the retained bytes' sha256 plus retrieval time and locator.
- Google Sheets regenerates the xlsx on every export, so the workbook's byte sha256 differs between fresh runs even when no cell changed. Each workbook tab therefore also records `content_sha256`, a hash over its canonical cell text (notes, header, rows), to compare content across runs.
- DW-D-2 (cited by every review) is the business workflow contract whose rules are contained in the policy (interview 2, 10:08); it is not a separate fetchable source.

Verify this run with `.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py verify run-20261009T023446Z`.
