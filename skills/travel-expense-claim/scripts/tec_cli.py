#!/usr/bin/env python3
"""travel-expense-claim Skill entry point.

  tec_cli.py run     [--run-id ID] [--supersedes RUN_ID --reason TEXT]   fresh read of all five native sources
  tec_cli.py replay  --from RUN_ID [--run-id ID]           labelled offline replay of RUN_ID's retained inputs
  tec_cli.py verify  RUN_ID [--compare RUN_ID]             integrity and consistency checks
  tec_cli.py synthetic-demo [--fixture F --out DIR]         labelled SYN-* scenario (written outside artifacts/runs)

Exit codes: 0 success, 1 partial (some source portion unusable; affected scope reported),
2 failure (a required source unusable; no batch processed), 3 verification failed, 4 usage/state error.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

from tec import run as runmod, verify as vermod  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tec_cli.py")
    ap.add_argument("--runs-dir", default=os.path.join(REPO, "artifacts", "runs"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--run-id")
    r.add_argument("--supersedes", help="earlier run this run replaces (recorded by hash; never modified)")
    r.add_argument("--reason", help="why the earlier run is superseded")
    p = sub.add_parser("replay")
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--run-id")
    syn = sub.add_parser("synthetic-demo", help="run a labelled SYN-* fixture through the engine (never a source run)")
    syn.add_argument("--fixture", default=os.path.join(REPO, "tests", "fixtures", "synthetic_partial_resumption.json"))
    syn.add_argument("--out", default=os.path.join(REPO, "artifacts", "synthetic", "partial-resumption-3"))
    v = sub.add_parser("verify")
    v.add_argument("run_id")
    v.add_argument("--compare")
    v.add_argument("--schema", default=os.path.join(REPO, "snapshot.schema.json"))
    a = ap.parse_args(argv)

    if a.cmd in ("run", "replay"):
        if a.cmd == "replay" and not os.path.exists(os.path.join(a.runs_dir, a.src, "sources.json")):
            print("replay source run %s has no retained sources.json (missing or corrupt prior state)" % a.src, file=sys.stderr)
            return 4
        run_id = a.run_id or runmod.new_run_id("run" if a.cmd == "run" else "replay")
        try:
            sup = getattr(a, "supersedes", None)
            if sup and not os.path.exists(os.path.join(a.runs_dir, sup, "run.json")):
                print("superseded run %s has no run.json (missing or corrupt prior state)" % sup, file=sys.stderr)
                return 4
            run_dir, meta = runmod.execute(a.runs_dir, run_id, "fresh" if a.cmd == "run" else "replay",
                                           replay_of=getattr(a, "src", None), repo=REPO,
                                           supersedes=sup, reason=getattr(a, "reason", None))
        except FileExistsError as e:
            print(str(e), file=sys.stderr)
            return 4
        print("%s %s -> %s" % (meta["outcome"].upper(), run_id, os.path.relpath(run_dir, REPO)))
        if meta["outcome"] == "failure":
            print(meta["failure"], file=sys.stderr)
        return {"success": 0, "partial": 1, "failure": 2}[meta["outcome"]]

    if a.cmd == "synthetic-demo":
        from tec import synthetic
        try:
            synthetic.run_demo(a.fixture, a.out)
        except FileExistsError as e:
            print(str(e), file=sys.stderr)
            return 4
        print("SYNTHETIC scenario written to %s (not a source run)" % os.path.relpath(a.out, REPO))
        return 0

    run_dir = os.path.join(a.runs_dir, a.run_id)
    if not os.path.exists(os.path.join(run_dir, "run.json")):
        print("run %s has no run.json (missing or corrupt prior state)" % a.run_id, file=sys.stderr)
        return 4
    res = vermod.verify(run_dir, a.schema, os.path.join(a.runs_dir, a.compare) if a.compare else None)
    failed = 0
    for name, ok, detail in res:
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok or not detail else "  -> %s" % (detail,)))
        failed += not ok
    print("%d checks, %d failed" % (len(res), failed))
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
