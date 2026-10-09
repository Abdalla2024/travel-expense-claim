# Travel expense claim

Build a reusable Agent Skill for Alderbridge Consulting's travel reimbursement workflow.

## Start

1. Read the [full Project D task](https://private-pecorino-70e.notion.site/Travel-expense-claim-Task-and-submission-3da0b700541e81249039eff895f77c98) for the scope, workflow and deliverables.
2. Use **Use this template → Create a new repository** on [GitRollTraining/travel-expense-claim](https://github.com/GitRollTraining/travel-expense-claim), then clone your own repository and work there.

The [snapshot schema](snapshot.schema.json) defines the required retained batch-state format.

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

# Tests: rules, synthetic branches, and the newest primary run plus its replay.
.venv/bin/python -m unittest discover -s tests -v
TEC_RUN=<run-id> .venv/bin/python -m unittest tests.test_primary_run    # pin a specific run
```

The results are success (exit 0), partial (exit 1: some source portion unusable, affected scope reported, affected claims held), or failure (exit 2: a required source unusable, no snapshots, attempt and error recorded). A run ID that already exists is refused (exit 4); sealed outputs are never overwritten. The full table is in [SKILL.md](skills/travel-expense-claim/SKILL.md#errors-and-retry).

## Submitted run results

Primary run **[`run-20261009T025952Z`](artifacts/runs/run-20261009T025952Z/report.md)**: a fresh read of all five sources at code revision `0ebcd29`, outcome `SUCCESS`. It supersedes `run-20261009T023446Z` (linked by its `run.json` sha256) to apply interview 3. The only business difference is that C117's undefined-category issue is now owned by Finance (FIN-01) as decision authority, with the Travel Administration Lead (ADMIN-01) following up. Statuses, money, requests, Finance events and cancellations are identical in every batch.

| Batch | Claims | closed-reimbursed | pending | held | rejected / withdrawn | Finance events admitted | Open issues | Net paid | Cancellations (status / financial) |
|---|---|---|---|---|---|---|---|---|---|
| batch-1 | 120 | 0 | 105 | 13 | 1 / 1 | 100 | 16 | EUR 0.00 | TC121 requested/unresolved, TC122 requested/no-effect |
| batch-2 | 120 | 95 | 8 | 15 | 1 / 1 | 200 | 17 | EUR 11539.15 | TC018 confirmed/unresolved, TC121 confirmed/unresolved, TC122 confirmed/no-effect |
| batch-3 | 121 | 96 | 11 | 12 | 1 / 1 | 210 | 13 | EUR 11634.15 | TC018 resolved, TC019 unresolved, TC121 resolved, TC122 no-effect |
| batch-4 | 121 | 103 | 5 | 11 | 1 / 1 | 219 | 13 | EUR 12034.15 | TC018 **unresolved** (late transfer), TC019 resolved, TC121 resolved, TC122 no-effect |

Still open after batch-4:
- **Held, employee:** C08 and C21 (EMP-01), C114 (EMP-03).
- **Held, Finance decision (FIN-01, follow-up ADMIN-01):** C10, C22, C23, C25, C112, C116, C18, and C117 (undefined category "entertainment"; no Finance decision exists).
- **Pending review:** C15, C118, C26, C113 (ADMIN-01) and C119 (DIR-01).

Reasons and next actions are in report §2. The drafts are in `queue/drafts/`.

Run history (every run is retained unmodified):
- [`replay-20261009T025958Z`](artifacts/runs/replay-20261009T025958Z/report.md): labelled offline replay of the primary run, equivalent (`verify replay-20261009T025958Z --compare run-20261009T025952Z`: 77 checks, 0 failed).
- [`run-20261009T023446Z`](artifacts/runs/run-20261009T023446Z/report.md) with [`replay-20261009T023452Z`](artifacts/runs/replay-20261009T023452Z/report.md): the previous primary run at `93b2b5b`, before interview 3.
- [`run-20261009T023340Z`](artifacts/runs/run-20261009T023340Z/report.md) with [`replay-20261009T023346Z`](artifacts/runs/replay-20261009T023346Z/report.md): the first run at `698a6b0`, superseded only by the per-tab `content_sha256` addition.

Verification of the primary run: `verify run-20261009T025952Z` reports 76 checks, 0 failed (including that the superseded run is retained unchanged). `python -m unittest discover -s tests` reports 41 tests OK, with the rule, synthetic-branch, undefined-category, primary-run, replay and failure-path suites.

Not run or not covered:
- A fresh run during a real network outage. The `FAILURE` and `PARTIAL` paths are tested offline instead, by replaying a temporary copy of the retained inputs with the policy or receipt binder corrupted (`tests/test_failure_paths.py`). Nothing from those tests is retained as a run.
- Partial employee evidence. It does not occur in the supplied batches and is tested only with the labelled synthetic fixture.

## Support and handoff

- Start from `artifacts/runs/<run-id>/report.md`:
  - §2 lists every open claim with owner, reason and next action.
  - §3 covers cancellation processes, including those without a claim.
  - §4 shows the repair queue and its per-batch updates, including partial responses.
  - §8 records source access and limitations.
- Request drafts are in `queue/drafts/<owner>.md`. They are local and unsent; a person reviews and sends them.
- Finance or reviewer answers arrive only as new source records in a later batch. The Skill never records an answer itself.
- An undefined expense category (for example "entertainment" on C117) stays unresolved and holds its claim until Finance supplies a definition or a cost-specific eligibility instruction (interview 3). The Travel Administration Lead follows up. Never assume eligibility or ineligibility in code.
- If a run reports `PARTIAL` or `FAILURE`, read `sources.json` (`error`, `missing_scope`) and rerun when the native location is reachable. Use `replay` only for offline reprocessing, and it is labelled as such.
