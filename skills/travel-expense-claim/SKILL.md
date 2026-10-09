---
name: travel-expense-claim
description: Process Alderbridge travel permits, expense claims, review replies, Finance outcomes and trip/permit cancellations batch by batch from the five native sources; produce sealed snapshots, claims.csv, a repair queue with local drafts, and an operations handoff report. Use when asked to run, replay, verify or explain a travel-claim reconciliation run.
---

# Travel expense claim

This Skill prepares local work for the operations lead. People make every approval, exception, booking and payment decision. The Skill never fabricates a reply, recommends approval, sends a request, books travel or moves money. It reads only the facts the scenario supplies and records what they cause.

## Inputs

There are five native sources, all read fresh on every `run`. URLs and routes are in `scripts/tec/capture.py`.

| source_id | Native location | Route |
|---|---|---|
| `policy` | Notion page "Alderbridge travel reimbursement policy" | Notion public page-chunk API, following the cursor until it is exhausted |
| `registers:<tab>` | Google Sheets "Travel registers" (10 tabs) | `export?format=xlsx`; cells read from the raw XML |
| `initial-claims` | Drive "Initial claim binder" PDF | Drive download |
| `claim-updates` | Drive "Claim updates binder" PDF | Drive download |
| `receipts` | Drive "Receipt binder" PDF | Drive download |

Business rules come from the policy and the two interviews (`interviews/`). They are summarized with citations in [references/requirements.md](references/requirements.md). Don't add rules that appear in neither. If a company rule is missing, raise it with the operations lead or facilitator.

## Invocation

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt          # once
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py run           # fresh read of all five sources
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py replay --from <run-id>   # labelled offline replay
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py verify <run-id> [--compare <run-id>]
```

## Outputs (`artifacts/runs/<run-id>/`)

- `sources.json`: per piece, the source_id, retained path, sha256, `read` or `unavailable`, error, native url, locator, UTC `observed_at` and observed version. Also completeness, missing scope and limitations.
- `sources/…`: the exact retained bytes.
- `batches/batch-<n>.json`: one sealed `travel-claim-snapshot/2` per arrival batch. Each is chained to its predecessor and to `sources.json` by sha256.
- `claims.csv`: one current row per claim. Money is in integer EUR cents; unknown money is left blank.
- `queue/items.json`, `queue/events.jsonl`, `queue/drafts/<owner>.md`: the repair queue. Drafts are never sent.
- `report.md`: the operations handoff. `run.json` holds run metadata, the code revision and snapshot hashes.

## Processing contract

1. **Batches.** Availability is decided by arrival batch only. Within batch *b* the order is: claim revisions → cancellation deliveries → review replies → readiness (proposes `REQ-<claim>`) → Finance activity → final evaluation → seal. Nothing from a later batch may influence an earlier snapshot.
2. **Holds.** An unresolved fact holds only its own claim revision. Independent claims and cancellations continue.
3. **Corrections.** A new revision gets a full recheck and needs fresh approvals for that exact revision. After acceptance, a Finance resolution or cancellation is required before closure or any replacement.
4. **Closure.** See requirements §2.3. `balance_cents = allowed_cents − paid_cents`.
5. **Repair queue.** Grouped by owner, one item per fact. Append-only events. A partial response satisfies only what it supports.
6. **Duplicates.** An exact redelivery has no effect. A conflicting redelivery holds the case and keeps the money already admitted.

## Errors and retry

| Situation | Behaviour | Exit |
|---|---|---|
| All five sources complete | Every batch is processed | 0 `SUCCESS` |
| `claim-updates` or `receipts` unusable, or a source only partly read | Processed; the affected scope is recorded in `sources.json` and the report. Affected claims are held, never guessed | 1 `PARTIAL` |
| `policy`, any workbook tab, or `initial-claims` unusable | No snapshots. `sources.json` records the attempt and error; `report.md` explains | 2 `FAILURE` |
| Verification check fails | Lists the failing checks | 3 |
| Run ID exists, or prior state is missing or corrupt | Refuses to overwrite and reports the problem | 4 |

Retry with a new `run`; a new run ID is created and nothing sealed is overwritten. To reprocess without network access, use `replay --from <run-id>`. It reuses that run's retained bytes, checks their sha256, and labels the result `offline-replay`.

## Supporting files

- `scripts/tec/capture.py`: fresh reads, completeness checks, replay copying.
- `scripts/tec/parse.py`, `scripts/tec/dataset.py`: parse the retained sources into typed records with locators.
- `scripts/tec/engine.py`: the rules and state transitions, each citing a policy paragraph or interview time.
- `scripts/tec/repair_queue.py`: the queue and drafts.
- `scripts/tec/run.py`, `scripts/tec/report.py`: sealed outputs.
- `scripts/tec/verify.py`: integrity checks.
- `references/requirements.md`: the requirements matrix, implementation choices, scenarios and limitations.
