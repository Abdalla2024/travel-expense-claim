# Requirements matrix: travel-expense-claim

Sources of each rule are marked:

- **S1/S2/S3**: stakeholder instruction from interview 1, 2 or 3. Times refer to `interviews/*.md`.
- **P ¶n**: policy POL-2026.2, paragraph n in page order.
- **W**: workbook tab note or record.
- **I**: our implementation choice.
- **L**: known limitation.

Policy paragraphs, counted in page order: ¶1 scope and clock · ¶2 evidence · ¶3 caps, FX and exceptions · ¶4 permits and roles · ¶5 deadlines · ¶6 administration and budget review · ¶7 requests and replies · ¶8 material change · ¶9 request identity · ¶10 Finance facts · ¶11 net paid and closure · ¶12 holds and human authority · ¶13–¶16 cancellations. The code cites the same numbers as `POL ¶n`.

## 1. Rules

| # | Requirement | Basis | Understanding | Confidence / open point | Implementation | Next action |
|---|---|---|---|---|---|---|
| 1 | Sources | S1, S2 10:03–10:12, P ¶1 | Five native locations, read fresh every run. No document named LOG-0014 ("fixed source manifest") exists. | **L:** The policy's reference to it is unresolved, and is recorded in `sources.json.limitations`. | `capture.py` reads all five; a failed read is retained as `unavailable` | — |
| 2 | Source identity | S2 10:09–10:10 | There are no native revision labels for the workbook or PDFs. | **I:** Notion block version for the policy; the HTTP ETag/Last-Modified as observed (or null) for the others; sha256, `observed_at`, locator. Nothing is invented. | `sources.json` | — |
| 3 | DW-D-2 | S2 10:08 | The workflow contract; its rules are inside the policy. | Resolved | Not fetched | — |
| 4 | Batches | S2 10:04–10:06, W | The batch number alone decides availability. UTC times are business times. Later batches never change earlier results. | High | Simulation consumes batch by batch and seals a snapshot after each | — |
| 5 | Case clock | P ¶1, S2 10:05 | Frozen at 2026-11-15 Europe/Amsterdam. Business times must not exceed the end of that day. | High | `Engine.clock_end`; events after it are rejected | — |
| 6 | Replay identity | P ¶10, P ¶14, S2 10:06 | An event ID has an immutable payload. An exact redelivery has no effect; a conflicting one holds the case. | High | `fin_seen` / `canc_seen` payload keys | — |
| 7 | Permits | S1 06:19, P ¶4 | International trips need an approved permit before the first commitment. A late permit cannot be approved retroactively. | High | `permit_state`; produces `late_permit` or `permit_unapproved` (owner Finance) | — |
| 8 | Review roles | S1 06:33, S2 10:08, P ¶4 | Administration, then budget owner and supervisor; a director when the amount is strictly above €1,000.00. Budget owner and supervisor may give one response if they are the same person. | High | `_review_errors`, `roles_needed` | — |
| 9 | Reply validity | S2 10:09, P ¶7 | Must match subject type, ID and exact revision. The actor must be the directory actor. The packet must describe that revision. | High | Invalid replies are kept in `rejected_imports` and shown in the report | — |
| 10 | Evidence | S1 06:32, P ¶2 | A matching receipt plus a separate settled merchant transaction. Employee, trip, cost, currency and gross must match. | High | Line findings `missing_receipt`, `missing_payment_proof`, … (owner employee) | — |
| 11 | Pay after submit | S2 10:06–10:07 | A cost may be submitted before it is paid. It is held until settled proof exists, then proceeds. The payment date sets the FX rate and the caps. | High (C113 proceeds) | `paid_date` from the settled merchant transaction | — |
| 12 | Caps | S1 06:31, P ¶3, W Caps | Lodging per night, meals per day, in the expense currency, effective on the payment date. Transport and conference are uncapped. Personal is 0. | High | `CAPPED` / `UNCAPPED` (taken from POL-2026.2; a different policy revision makes the run partial until they are re-read) | — |
| 13 | FX and rounding | S1 06:32, P ¶3, W FX | Finance's exact rate for the payment date; EUR is 1. Each line is rounded half-up to cents before summing. | High | `cents()`; decimals are read as exact text | — |
| 14 | Missing rate or cap | S2 10:10–10:11 | Finance supplies or confirms it. The claim stays held until then. | High | `missing_rate` / `missing_cap` (owner FIN-01) | — |
| 15 | Deadline | S1 06:32, P ¶5 | Trip end plus two calendar months, inclusive, clamped to month end. The first submission date of each cost counts. | High | `add_months_clamped`; `late_filing` (owner Finance) | — |
| 16 | Exceptions | S1 06:29, P ¶3, P ¶15 | Finance-only and bound to a version. `covered_issues` resolves eligibility; a cancellation exception must name the cancellation ID. | High | Applied per line; the original finding is kept in the reason | — |
| 17 | Zero entitlement | S2 10:07–10:08 | Still needs the full review before closing with no payment. | High (C15/C118 stay pending) | `closed-no-payment` only after all approvals | — |
| 18 | Corrections | S1 06:23, 06:33, P ¶8, S2 10:05 | A new revision forces a recheck. After acceptance, a Finance resolution is needed before closing or replacing. | High | See choice 2 | — |
| 19 | Requests | P ¶9 | A stable request ID. A prepaid cost is linked, not paid twice. | High | `REQ-<claim>`; a replacement after a Finance cancellation becomes `REQ-<claim>-r<n>` | — |
| 20 | Finance facts | S1 06:20–06:35, P ¶10–¶11 | Only supplied outcomes count. A failed payment doesn't change the paid amount. A refund names its transfer. Net paid = settled − refunds. | High | `_finance_errors`, `_apply_finance` | — |
| 21 | Closure | S1 06:31, 06:35–06:36, P ¶11 | See choice 3. Trip closure is separate from claim closure. | High | `evaluate_claim`, `evaluate_cancellation` | — |
| 22 | Cancellations | P ¶13–¶16 | Employee requests, supervisor confirms. Confirmation must come strictly later. A request alone pauses readiness. A process with no claim has no financial effect. | High | Separate state; IDs kept apart from Finance event IDs | — |
| 23 | Repair routing | S1 06:28, S2 10:10 | Evidence goes to the employee; rate and cap gaps go to Finance; the claim is held meanwhile. | High | See choice 4 | — |
| 24 | Human authority | P ¶12, task | Never fabricate replies, approve, send, book or pay. | High | Drafts only, never sent | — |
| 25 | Undefined categories | P ¶2, S3 10:48, 10:50, 10:52 | Any category the policy does not define is unresolved, on every claim. It is never assumed eligible or ineligible, never mapped to another category, and never waived by the Skill. | High | `unknown_category` finding; line `unresolved`, allowed blank | Finance decision for C117 "entertainment" (none exists yet) |
| 26 | Whole-claim hold | S3 10:49 | While any line is unresolved, the claim is held. Supported lines are still calculated but the claim is not completed on them. | High | Claim allowed blank; no request proposed | — |
| 27 | Who resolves | S3 10:48, 10:49, 10:51 | Finance is the authority for policy definitions, tables and eligibility instructions. The budget owner decides funding only. The employee may be asked to clarify the specific cost item, but is not the policy authority. The Travel Administration Lead follows up on missing replies. | High. **I:** the lead is identified with the directory's administration reviewer (ADMIN-01), because the lead performs the administration check (S1 06:18) | Issue `owner` = `decision_authority` = Finance officer; `follow_up` = administration reviewer; drafts addressed to Finance with the follow-up named | — |
| 28 | Finance resolution of a category | S3 10:51–10:52, P ¶3 | Resolved only by a valid Finance instruction bound to the claim, revision and cost (directory Finance officer): a replacement allowed amount, or a reclassification recorded on the updated revision with the original kept as history. Allowed 0 means ineligible: zero entitlement with the claimed amount and evidence kept. | High for the rule. **L:** the supplied binders have no reclassification field, so reclassification is supported in the engine (`exception.category`) and tested synthetically, but no parser populates it | Line `excluded` with "claimed … retained with evidence"; reclassification noted in the line reason | — |
| 29 | Revalidation and closure after resolution | S3 10:50, 10:52, P ¶8 | Changed evidence, categories or amounts invalidate earlier approvals. The updated revision needs every required approval, Finance processing and reconciliation before closure. | High | Same full-recheck path as row 18 | — |

## 2. Implementation choices (adopted in the coding session)

1. **Incomplete claims and independent work.** An unresolved line holds the whole claim revision, because reviews cover the whole revision (S1 06:28, 06:33). Independent claims, permits and cancellations continue (P ¶12). For example, C08, C114, C22, C23, C116 and C117 are held while C27–C98 close, and TC122 is processed with no claim.
2. **Revalidation after material corrections.**
   - Every new revision is fully recalculated and rechecked, and needs fresh approvals for that exact revision. Older decisions stay as history (P ¶8).
   - Approvals given before a cancellation don't count after it (C19 r2, C121 r1).
   - A request that was already accepted needs a Finance resolution or cancellation before a replacement can go out (C18, C19).
3. **Financial completion and delivery scope.**
   - `closed-reimbursed` requires all of: the full role set for the current revision, a known entitlement, net paid equal to that entitlement, every required Finance resolution, and no open issue.
   - A resolution is required after any of: a correction or cancellation after acceptance, an adjustment, a refund, or a transfer after cancellation.
   - `balance_cents = allowed_cents − paid_cents`, or null when the entitlement is unknown.
   - Rejection, withdrawal, no-payment closure, reimbursement closure and cancellation processes are kept apart.
   - The scope was checked against the actual run. C18 stays held with FIN-01. C19 closes at €80.00 only in batch 4. C16 and C120 close in batch 3. C15 and C118 stay pending with ADMIN-01.
4. **Repair queue and partial responses.**
   - Grouped by owner, one item per fact or return reason.
   - The history is append-only, with supersede and replacement links.
   - A batch that closes only some of an owner's items on a subject logs `partial-response`, and the rest stay open. In the supplied data, C20's refund closes the overpayment but the resolution item stays open in batch 3.
   - Partial employee evidence is not present in the supplied data. It is tested with the labelled fixture `tests/fixtures/synthetic_partial_response.json`.

## 3. Material scenarios (expected results checked in `tests/test_primary_run.py`)

| Branch | Subjects |
|---|---|
| Ordinary path | C27–C98 and others |
| Director boundary | C05 / C06 / C101 / C119 |
| Caps | C07, C102–C107 |
| Rounding | C108 / C109 |
| Personal or zero entitlement | C15, C115, C118 |
| Unknown category | C117 |
| Missing evidence | C08, C114 |
| Missing rate or cap | C22, C23, C116 |
| Deadline | C11, C110–C112, C12 r1→r2 |
| Pay after submission | C113 |
| Permits | P02 ok, P10 late, P25 unapproved |
| Return / reject / withdraw | C09 r1→r2 (new trip T09B), C21, C14, C13 |
| Prepaid link | C03 + C24 |
| Partial payment | C16, C120 |
| Failed → retry | C17 |
| Overpayment → refund → resolution | C20 |
| Correction and cancellation after payment | C19 r1→r3 + TC019 |
| Cancellation during Finance acceptance, reassignment, late transfer | C18 + TC018 |
| Permit-only cancellation | C121 + TC121 |
| Cancellation with no claim | TC122 |
| Exact replays | F-C01-1, TC122-confirmed (batch 4) |

## 4. Remaining limitations

- LOG-0014 is referenced by the policy but does not exist (stakeholder-confirmed).
- No native revision IDs exist for the workbook or PDFs.
- The PDFs are parsed from their text layer. A layout change would make parsing fail loudly (the run becomes partial or failed), never silently.
- The category "entertainment" (C117) is not defined by the policy, and Finance has supplied no definition or instruction. C117 stays held with FIN-01 as the decision authority and ADMIN-01 following up (S3). No eligibility decision is made by the Skill.
- The binders have no field for a Finance reclassification. The engine accepts one on a bound exception, but no supplied source carries it.
- The Notion route is the public page-chunk endpoint the published page itself uses. If Notion changes it, the read is recorded as unavailable.
