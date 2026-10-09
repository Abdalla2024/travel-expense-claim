#!/usr/bin/env python3
"""travel-expense-claim Skill entry point.

  tec_cli.py run     [--run-id ID] [--runs-dir DIR]        fresh read of all five native sources
  tec_cli.py replay  --from RUN_ID [--run-id ID]           labelled offline replay of RUN_ID's retained inputs
  tec_cli.py verify  RUN_ID [--compare RUN_ID]             integrity and consistency checks

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
    p = sub.add_parser("replay")
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--run-id")
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
            run_dir, meta = runmod.execute(a.runs_dir, run_id, "fresh" if a.cmd == "run" else "replay",
                                           replay_of=getattr(a, "src", None), repo=REPO)
        except FileExistsError as e:
            print(str(e), file=sys.stderr)
            return 4
        print("%s %s -> %s" % (meta["outcome"].upper(), run_id, os.path.relpath(run_dir, REPO)))
        if meta["outcome"] == "failure":
            print(meta["failure"], file=sys.stderr)
        return {"success": 0, "partial": 1, "failure": 2}[meta["outcome"]]

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
