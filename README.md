# Travel expense claim

Build a reusable Agent Skill for Alderbridge Consulting's travel reimbursement workflow.

## Start

1. Read the [full Project D task](https://private-pecorino-70e.notion.site/Travel-expense-claim-Task-and-submission-3da0b700541e81249039eff895f77c98) for the scope, workflow and deliverables.
2. Use **Use this template → Create a new repository** on [GitRollTraining/travel-expense-claim](https://github.com/GitRollTraining/travel-expense-claim), then clone your own repository and work there.

The [snapshot schema](snapshot.schema.json) defines the required retained batch-state format.

Follow the shared [Setting Up entire.io for a Project](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details) lesson and verify actual session capture before assessed work. Use [Project D in Work Sim](https://work-sim.catalyte.ai/s/project-d-travel-expense-claim) for your stakeholder interview and obtain relevant business source links and context there.

**Interview rule.** You conduct the stakeholder interview yourself, and the questions are yours. Do not connect a coding agent or any other AI to the interview to run, script, or automate it. The interview transcript is assessed together with the code; a project whose interview was run by an agent is not scored.

- Export your interview as the original Work Sim Markdown, save one final complete file per session under `interviews/`, and commit and push it with your code. Do not rewrite the export. If the export is unavailable, contact the facilitator.

## What is here

| Path | Content |
|---|---|
| [skills/travel-expense-claim/SKILL.md](skills/travel-expense-claim/SKILL.md) | The Skill: inputs, invocation, human boundaries, outputs, error and retry behaviour |
| [skills/travel-expense-claim/scripts/](skills/travel-expense-claim/scripts/) | Implementation (`tec_cli.py` plus the `tec/` package) |
| [skills/travel-expense-claim/references/requirements.md](skills/travel-expense-claim/references/requirements.md) | Requirements matrix with source and interview citations, the four implementation choices, scenarios and limitations |
| [interviews/](interviews/) | Original Work Sim exports, one per session, unmodified |
| [tests/](tests/) | Rule tests, synthetic branch tests (labelled `SYN-*`), and checks on the primary run |
| `artifacts/runs/<run-id>/` | Retained runs: sources, sealed snapshots, `claims.csv`, queue and `report.md` |
| [artifacts/synthetic/partial-resumption-3/](artifacts/synthetic/partial-resumption-3/report.md) | **Synthetic** scenario (all `SYN-*`), kept outside `artifacts/runs/`: a partial reply resuming only the work it supports, a hold's stated cost, and a wrong-role reply kept as history. Earlier copies `partial-resumption/` (`557b1a2`) and `partial-resumption-2/` (`c1411c5`) are kept unmodified |

## Setup

You need Python 3.11 or later (developed on 3.13), network access to notion.site, docs.google.com and drive.usercontent.google.com, and no credentials. All five sources are public links.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # pypdf 6.19.0, jsonschema 4.23.0
```

## Run, replay, verify

```bash
# Fresh run: reads all five native sources now, then processes batches 1-4.
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py run                      # run-id defaults to run-<UTC timestamp>
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py run --run-id my-run
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py run --supersedes <run-id> --reason "why"   # link to the run it replaces

# Labelled offline replay of an earlier run's retained inputs (no fresh access claimed).
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py replay --from <run-id>

# Integrity checks: schema, hash chain, source bindings, money recomputation,
# batch availability, ID separation, queue history, and optional replay equivalence.
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py verify <run-id> [--compare <run-id>]

# Labelled synthetic partial-resumption scenario (SYN-* only; refuses to overwrite a retained copy).
.venv/bin/python skills/travel-expense-claim/scripts/tec_cli.py synthetic-demo --out /tmp/syn-demo

# Tests: rules, synthetic branches, and the current primary run plus its replay.
.venv/bin/python -m unittest discover -s tests -v
```

`tests/test_primary_run.py` encodes the expected results of the current primary run under the current rules. By default it checks the newest fresh run; `TEC_RUN=<run-id>` selects another run that should meet the same expectations. It is not a test for historical runs. For example, `run-20261009T023446Z` predates interview 3, so its C117 ownership correctly differs, runs before `run-20261009T173123Z` predate interview 4, so C21's funding return still sits with the employee there, runs before `run-20261009T175711Z` predate interview 5's return-request wording, and runs before `run-20261009T181801Z` have no hold-impact explanations. Check older runs with `verify <run-id>` (and `--compare` for replays).

The results are success (exit 0), partial (exit 1: some source portion unusable, affected scope reported, affected claims held), or failure (exit 2: a required source unusable, no snapshots, attempt and error recorded). A run ID that already exists is refused (exit 4); sealed outputs are never overwritten. The full table is in [SKILL.md](skills/travel-expense-claim/SKILL.md#errors-and-retry).

## Submitted run results

Primary run **[`run-20261009T181801Z`](artifacts/runs/run-20261009T181801Z/report.md)**: a fresh read of all five sources at code revision `089356e`, outcome `SUCCESS`. Its offline replay is [`replay-20261009T181810Z`](artifacts/runs/replay-20261009T181810Z/report.md). It supersedes `run-20261009T175711Z` (linked by its `run.json` sha256) to apply interview 6. Each held claim now states what the whole-claim hold withholds, why, and what proceeding on independent lines would risk (report §2 "What each hold withholds", queue `hold_impact`). Report §6 tabulates review replies not admitted. Claim states, money, owners, reasons, requests, Finance events, cancellations and issues are identical to the previous primary run in every batch.

| Batch | Claims | closed-reimbursed | pending | held | rejected / withdrawn | Finance events admitted | Open issues | Net paid | Cancellations (status / financial) |
|---|---|---|---|---|---|---|---|---|---|
| batch-1 | 120 | 0 | 105 | 13 | 1 / 1 | 100 | 16 | EUR 0.00 | TC121 requested/unresolved, TC122 requested/no-effect |
| batch-2 | 120 | 95 | 8 | 15 | 1 / 1 | 200 | 17 | EUR 11539.15 | TC018 confirmed/unresolved, TC121 confirmed/unresolved, TC122 confirmed/no-effect |
| batch-3 | 121 | 96 | 11 | 12 | 1 / 1 | 210 | 13 | EUR 11634.15 | TC018 resolved, TC019 unresolved, TC121 resolved, TC122 no-effect |
| batch-4 | 121 | 103 | 5 | 11 | 1 / 1 | 219 | 13 | EUR 12034.15 | TC018 **unresolved** (late transfer), TC019 resolved, TC121 resolved, TC122 no-effect |

Still open after batch-4:
- **Held, employee evidence:** C08 (EMP-01), C114 (EMP-03).
- **Held, budget owner's funding decision:** C21 (LEAD-01, follow-up ADMIN-01).
- **Held, Finance decision (FIN-01, follow-up ADMIN-01):** C10, C22, C23, C25, C112, C116, C18, and C117 (undefined category "entertainment"; no Finance decision exists).
- **Pending review:** C15, C118, C26, C113 (ADMIN-01) and C119 (DIR-01).

Reasons and next actions are in report §2. The drafts are in `queue/drafts/`.

Run history (every run is retained unmodified):
- [`run-20261009T175711Z`](artifacts/runs/run-20261009T175711Z/report.md) with [`replay-20261009T175720Z`](artifacts/runs/replay-20261009T175720Z/report.md): the previous primary run at `c1411c5`, after interview 5 and before interview 6.
- [`run-20261009T173123Z`](artifacts/runs/run-20261009T173123Z/report.md) with [`replay-20261009T173131Z`](artifacts/runs/replay-20261009T173131Z/report.md): at `557b1a2`, after interview 4 and before interview 5.
- [`run-20261009T025952Z`](artifacts/runs/run-20261009T025952Z/report.md) with [`replay-20261009T025958Z`](artifacts/runs/replay-20261009T025958Z/report.md): at `0ebcd29`, after interview 3 and before interview 4.
- [`run-20261009T023446Z`](artifacts/runs/run-20261009T023446Z/report.md) with [`replay-20261009T023452Z`](artifacts/runs/replay-20261009T023452Z/report.md): at `93b2b5b`, before interview 3.
- [`run-20261009T023340Z`](artifacts/runs/run-20261009T023340Z/report.md) with [`replay-20261009T023346Z`](artifacts/runs/replay-20261009T023346Z/report.md): the first run at `698a6b0`, superseded only by the per-tab `content_sha256` addition.

Verification:
- **Primary run:** `verify run-20261009T181801Z` reports 79 checks, 0 failed. This includes that the superseded run is unchanged, and that no request is misplaced, duplicated or written with raw codes.
- **Replay:** `verify replay-20261009T181810Z --compare run-20261009T181801Z` reports 80 checks, 0 failed.
- **Earlier runs:** every one still verifies with 0 failures.
- **Tests:** `python -m unittest discover -s tests` reports 69 tests OK: rules 4, engine branches 8, undefined categories 8, return routing 9, partial resumption 10, interview 6 rules 7, primary run and replay 21, failure paths 2.

Not run or not covered. The supplied sources exercise the branches listed in requirements §3. They do **not** exercise the branches below, which are covered only by synthetic tests (all identifiers `SYN-*`) or not at all:
- **Undefined categories:** a Finance definition, an eligibility instruction (including an ineligible zero), or a reclassification. These are synthetic only (`tests/test_undefined_category.py`). The supplied sources contain no such Finance decision, and reclassification has no native source format. For C117, only "stays unresolved" is checked against real data.
- **Invalid review replies:** wrong-role, wrong-person and stale-revision replies, which are rejected and kept as history without advancing the case (interview 6, 02:09). Synthetic only (`tests/test_engine_synthetic.py`, `tests/test_interview6.py`, `SYN-D-C2-SUP-X` in the synthetic scenario). No supplied reply is rejected, and report §6 says so.
- **Re-review after a late Finance rate or cap:** only the administration, budget-owner and director reviews repeat; the supervisor's stands (interview 6, 02:09). Synthetic only (`tests/test_interview6.py`). No supplied rate or cap row carries an arrival batch.
- **Proceeding on independent lines:** not implemented. We hold the whole claim (permitted, interview 6, 02:08) and explain its cost. The independent-line alternative is described in each hold explanation but never executed.
- **Finance redelivery conflict:** a redelivery whose payload conflicts, synthetic only. The supplied data contains only an exact replay (F-C01-1).
- **Over-refund:** a refund larger than the remaining unrecovered amount, synthetic only.
- **Orphan confirmation:** a cancellation confirmation that arrives before its request, and one by the wrong confirmer, synthetic only.
- **Partial employee evidence and resumption:** synthetic only. This covers evidence arriving in a later batch, a partial reply resuming one line while another stays open, and a reply made stale by late evidence (`artifacts/synthetic/partial-resumption-3/`, `tests/test_partial_resumption.py`, `tests/fixtures/synthetic_partial_response.json`). No supplied evidence row carries an arrival batch. The only real partial response is Finance's on C20.
- **Resuming a returned review:** the reviewer who returned the work evaluates the repair (interview 5, 01:52). This is synthetic only (`tests/test_return_routing.py`, scenario SYN-C2); C21 never receives a later reply.
- **Returns naming an owner, unclassified or ambiguous returns:** routing to an owner named in the repair text, or to the Travel Administration Lead when none or several are named. Synthetic only. Neither supplied return names an owner, and both match a route. Who owns an unnamed repair is still an open point (requirements row 31).
- **A second request for the same fact:** merged into the original item (interview 5, 01:51). Synthetic only; no supplied case produces two requests for the same fact and person.
- **Network outage:** not exercised against live sources. The `FAILURE` and `PARTIAL` paths are tested offline by replaying a temporary copy of the retained inputs with the policy or receipt binder corrupted (`tests/test_failure_paths.py`). Nothing from those tests is retained as a run.

## Design notes

**Trade-offs.**
- **Deterministic engine, no model at runtime.** Every result can be replayed and verified from retained bytes, and a run costs nothing per call. The price is that free-text inputs, such as a reviewer's repair request, are read with keyword patterns (`tec/routing.py`). Text that matches no route, or more than one, goes to the Travel Administration Lead instead of being guessed.
- **Batch-by-batch simulation.** Each batch's snapshot sees only what had arrived. This adds code compared with evaluating everything at once, but it is what makes later corrections, cancellations and late transfers show up as changes rather than as rewritten history.
- **Conservative revalidation.** Every new revision is fully rechecked and needs fresh approvals for that revision. Within a revision, late evidence repeats only what depends on it: a late Finance rate or cap repeats the amount-dependent reviews (interview 6, 02:09), and late receipts or proof repeat all of them (interview 5, 01:52). A new revision may ask reviewers for more work than a dependency-based recheck would, but it never relies on a stale approval.
- **Holding the whole claim rather than paying independent lines.** Interview 6 (02:08–02:09) permits either, if the business cost is explained. We hold for three reasons:
  - Reviews cover the whole claim revision (interview 1, 06:33), so a revision cannot be approved while its entitlement is unknown.
  - Holding keeps `allowed_cents` a true entitlement or null, rather than a partial figure.
  - Paying part of a revision early would mean a second payment, or a Finance adjustment and resolution if the open line changes what was paid (policy ¶11).

  In the supplied data the choice changes no paid amount: only C114 (EUR 20.00) and C117 (EUR 40.00) have a supported line beside an open one, and neither has any review reply. Each hold's cost is stated in the report and queue item.
- **Raw xlsx XML parsing and retained bytes.** Amounts keep their exact decimal text, and each run keeps about 580 KB of sources (about 1.4 MB per run in all) as evidence of what was read. The repository grows with every run.
- **Notion's public page-chunk endpoint** instead of the official API, which would need a credential. No secret is needed, but this route is the one most likely to break. A failed read is recorded as unavailable.
- **Sealed runs, never overwritten.** A behaviour change produces a new run linked with `--supersedes`. History stays auditable, at the cost of more run folders.

**How the rules are verified.**
- **Unit and synthetic tests** pin each rule, citing the interview or policy paragraph.
- **`tests/test_primary_run.py`** checks the real run's per-batch states against expectations derived by hand from the sources.
- **`verify`** independently rechecks every retained run: schema, hash chain, source bytes, money recomputed from admitted Finance events, batch availability, separation of Finance and cancellation IDs, queue history, report and `claims.csv` agreement, and, for runs with interview-4 routing, misplaced, duplicate or raw-coded requests.
- **`verify --compare`** proves a replay is equivalent.
- **The synthetic scenario** is regenerated by the tests and compared byte-for-byte with the retained copy.

**Operating it.**
- **Read the exit code first:** 0 success, 1 partial, 2 failure, 3 verify failed, 4 refused (existing run ID or missing prior state).
- **Then read the details:** `run.json` (`outcome`), `sources.json` (`status`, `error`, `missing_scope`, `limitations`) and report §8.
- **On partial or failed runs:** affected claims are held, never guessed. Fix access and start a new run; nothing sealed is overwritten. Use `replay --from` only to reprocess offline, and it is labelled as such.
- **After every run:** run `verify`.

**Privacy and guardrails.**
- **Data and access:** all data is fictional. The five sources are public links, and no credentials are stored or needed.
- **Network:** the only network calls are the reads of the five sources (`capture.py`). Notion's page may take more than one read if its cursor continues.
- **Writes:** everything is written inside a new run folder, or under `artifacts/synthetic/` for the labelled demo.
- **Drafts:** request drafts are never sent.
- **Authority:** people keep approval, exception and payment authority. The Skill only records replies, exceptions and Finance outcomes that appear in the sources, and never fabricates them. Instructions inside imported records are treated as data.

**Cost and tools.**
- **Runtime:** Python 3.13 with `pypdf` and `jsonschema`. A fresh run takes about 9 s and a replay about 1 s (`run.json` timestamps for `run-20261009T181801Z` and its replay). There are no model or API charges.
- **Development:** the cost was the coding session in Claude Code (model `claude-opus-5-5`), captured by Entire. For example, `entire checkpoint tokens 01M4GVJBHER3RKPK9HJ7F2XSTM` reports 2,871k tokens for one checkpoint, 99.6% of them cache reads of the long session context.

## Coding-session capture (Entire)

Entire session capture is enabled for this repository with Claude Code as the agent (`.entire/settings.json`). Each commit made during the coding session carries an `Entire-Checkpoint:` trailer. The checkpoint itself is stored under `refs/entire/checkpoints/<xx>/<id>`, pushed to origin, and holds that session's `transcript.jsonl` and metadata.

```bash
entire checkpoint list                                             # checkpoints on main with their commits
entire checkpoint explain <checkpoint-id>                          # session, commit and files for one checkpoint
git log --format='%h %(trailers:key=Entire-Checkpoint,valueonly)'  # commit -> checkpoint
git ls-remote origin 'refs/entire/checkpoints/*'                   # checkpoint refs on origin
```

| Commit | Checkpoint | Ref |
|---|---|---|
| `3c3b11d` Conducted first interview | `01M4F4ZYG5P8001XZPAAXEZW7S` | `refs/entire/checkpoints/7S/01M4F4ZYG5P8001XZPAAXEZW7S` |
| `698a6b0` Implement the Skill and add interview 2 | `01M4F8457CN8F0E1BK2MK5EFGB` | `refs/entire/checkpoints/GB/01M4F8457CN8F0E1BK2MK5EFGB` |
| `93b2b5b` Record a content hash for each workbook tab | `01M4F86M9TBJT5A5VX620Q4866` | `refs/entire/checkpoints/66/01M4F86M9TBJT5A5VX620Q4866` |
| `d08c9dd` Retain the primary run, its replay, and failure-path tests | `01M4F88R8CRY3AEAFDBESDF7J6` | `refs/entire/checkpoints/J6/01M4F88R8CRY3AEAFDBESDF7J6` |
| `0ebcd29` Apply interview 3 | `01M4F9MCXWGX0GKTVEQMEFKHXR` | `refs/entire/checkpoints/XR/01M4F9MCXWGX0GKTVEQMEFKHXR` |
| `3d0a55f` Retain the interview-3 run and its replay | `01M4F9NY3FAVCDDJ58E425WNYQ` | `refs/entire/checkpoints/YQ/01M4F9NY3FAVCDDJ58E425WNYQ` |
| `d280d4c` Correct README, Skill and partial-run wording after readiness audit | `01M4FA5Z1QAMRFRDDN2RTNG21R` | `refs/entire/checkpoints/1R/01M4FA5Z1QAMRFRDDN2RTNG21R` |
| `ed40dea` Add the fourth Work Sim interview export | `01M4GV5TX59Z8MP15HEEJVN45Z` | `refs/entire/checkpoints/5Z/01M4GV5TX59Z8MP15HEEJVN45Z` |
| `bc521a1` Route returned work by the reviewer's request; resume per fact | `01M4GVBGEZK7GAG2SHZD297H02` | `refs/entire/checkpoints/02/01M4GVBGEZK7GAG2SHZD297H02` |
| `557b1a2` Retain a labelled synthetic partial-resumption scenario | `01M4GVG3F4B6B7NTRYHQX5FWJ6` | `refs/entire/checkpoints/J6/01M4GVG3F4B6B7NTRYHQX5FWJ6` |
| `3f270f7` Retain the interview-4 run and replay | `01M4GVJBHER3RKPK9HJ7F2XSTM` | `refs/entire/checkpoints/TM/01M4GVJBHER3RKPK9HJ7F2XSTM` |
| `6c5c85d` Document interview 4, synthetic-only coverage and design notes | `01M4GVNRY7R0PMV03CKQ80WDFV` | `refs/entire/checkpoints/FV/01M4GVNRY7R0PMV03CKQ80WDFV` |
| `6c669b7` List all verified commit-to-checkpoint pairs in the README | `01M4GVPSCQHWZYWETRA7HDE257` | `refs/entire/checkpoints/57/01M4GVPSCQHWZYWETRA7HDE257` |
| `d99df28` Add the fifth Work Sim interview export | `01M4GWZ3CAW7YBDPVRVPP5Y1XH` | `refs/entire/checkpoints/XH/01M4GWZ3CAW7YBDPVRVPP5Y1XH` |
| `8df26cc` Apply interview 5 to returned work, resumption and duplicate requests | `01M4GWZ5APFGGH4MFX887MQ77V` | `refs/entire/checkpoints/7V/01M4GWZ5APFGGH4MFX887MQ77V` |
| `c1411c5` Retain the synthetic partial-resumption scenario with interview-5 wording | `01M4GWZC7YA6SEXTA87JT7GP7Z` | `refs/entire/checkpoints/7Z/01M4GWZC7YA6SEXTA87JT7GP7Z` |
| `e682d98` Retain the interview-5 run and replay | `01M4GX0YYFDY14XNK8JQFQD39P` | `refs/entire/checkpoints/9P/01M4GX0YYFDY14XNK8JQFQD39P` |
| `492ef36` Document interview 5: return content, owners, re-review, grouping | `01M4GX3A25NCDD9TC65GSH31B4` | `refs/entire/checkpoints/B4/01M4GX3A25NCDD9TC65GSH31B4` |

All eighteen belong to Claude Code session `96590d86-1b96-4de5-9951-fef2a17d395f`. Each pair was checked against the commit trailer and the ref on origin. The commit that updated this table carries its own `Entire-Checkpoint:` trailer, shown by `git log`.

## Support and handoff

- Start from `artifacts/runs/<run-id>/report.md`:
  - §2 lists every open claim with owner, reason and next action.
  - §3 covers cancellation processes, including those without a claim.
  - §4 shows the repair queue and its per-batch updates, including partial responses.
  - §8 records source access and limitations.
- Request drafts are in `queue/drafts/<owner>.md`. They are local and unsent; a person reviews and sends them.
- Finance or reviewer answers arrive only as new source records in a later batch. The Skill never records an answer itself.
- A held claim's queue item and report §2 state what the hold withholds, why, and what proceeding on the independent lines would risk (interview 6, 02:08–02:09).
- A returned claim goes to the owner the return names. Otherwise it goes to whoever must supply what the reviewer asked for: a funding decision to the budget owner (C21 → LEAD-01), an evidence correction to the employee. Anything else goes to the Travel Administration Lead to identify the owner (interviews 3–5). The reviewer who returned the work evaluates the repair.
- An undefined expense category (for example "entertainment" on C117) stays unresolved and holds its claim until Finance supplies a definition or a cost-specific eligibility instruction (interview 3). The Travel Administration Lead follows up. Never assume eligibility or ineligibility in code.
- If a run reports `PARTIAL` or `FAILURE`, read `sources.json` (`error`, `missing_scope`) and rerun when the native location is reachable. Use `replay` only for offline reprocessing, and it is labelled as such.
