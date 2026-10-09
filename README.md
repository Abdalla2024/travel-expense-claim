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

## Submitted run

See [SUBMITTED-RUN](#submitted-run-results) below for run IDs, batch results and verification output.

## Support and handoff

- Start from `artifacts/runs/<run-id>/report.md`:
  - §2 lists every open claim with owner, reason and next action.
  - §3 covers cancellation processes, including those without a claim.
  - §4 shows the repair queue and its per-batch updates, including partial responses.
  - §8 records source access and limitations.
- Request drafts are in `queue/drafts/<owner>.md`. They are local and unsent; a person reviews and sends them.
- Finance or reviewer answers arrive only as new source records in a later batch. The Skill never records an answer itself.
- A missing company rule (for example the undefined "entertainment" category on C117) goes to the operations lead. Do not guess it in code.
- If a run reports `PARTIAL` or `FAILURE`, read `sources.json` (`error`, `missing_scope`) and rerun when the native location is reachable. Use `replay` only for offline reprocessing, and it is labelled as such.
