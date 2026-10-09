"""Failure and partial-source behaviour, exercised offline on a temporary copy of
the primary run's retained inputs with one file deliberately corrupted. The copy
lives in a temp directory and is never retained as a run."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "travel-expense-claim", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from tec import run as runmod  # noqa: E402
from test_primary_run import PRIMARY, RUNS  # noqa: E402


@unittest.skipUnless(PRIMARY, "no primary run to copy")
class SourceFailures(unittest.TestCase):
    def _replay_with_corruption(self, rel):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        shutil.copy(os.path.join(RUNS, PRIMARY, "sources.json"), src)
        shutil.copytree(os.path.join(RUNS, PRIMARY, "sources"), os.path.join(src, "sources"))
        with open(os.path.join(src, rel), "ab") as f:
            f.write(b"corrupted")
        run_dir, meta = runmod.execute(tmp, "rep", "replay", replay_of="src", repo=ROOT)
        with open(os.path.join(run_dir, "sources.json"), encoding="utf-8") as f:
            return run_dir, meta, json.load(f)

    def test_required_source_unusable_fails_without_snapshots(self):
        run_dir, meta, sources = self._replay_with_corruption("sources/policy/notion-page-chunk.json")
        self.assertEqual(meta["outcome"], "failure")
        pol = next(f for f in sources["files"] if f["source_id"] == "policy")
        self.assertEqual((pol["status"], pol["path"], pol["sha256"], pol["version"]), ("unavailable", None, None, None))
        self.assertIn("sha256", pol["error"])
        self.assertEqual(os.listdir(os.path.join(run_dir, "batches")), [])
        with open(os.path.join(run_dir, "report.md"), encoding="utf-8") as f:
            self.assertIn("FAILED", f.read())

    def test_receipt_binder_unusable_is_partial_and_holds_claims(self):
        run_dir, meta, sources = self._replay_with_corruption("sources/binders/receipt-binder.pdf")
        self.assertEqual(meta["outcome"], "partial")
        with open(os.path.join(run_dir, "batches", "batch-1.json"), encoding="utf-8") as f:
            snap = json.load(f)
        c01 = next(c for c in snap["claims"] if c["claim_id"] == "C01")
        self.assertEqual((c01["status"], c01["allowed_cents"]), ("held", None))
        self.assertTrue(any("receipt_source_unavailable" in i["record_id"] for i in snap["issues"]))
        self.assertTrue(any("receipt binder unusable" in x for x in sources["limitations"]))


if __name__ == "__main__":
    unittest.main()
