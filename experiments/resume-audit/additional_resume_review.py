"""Reproduce the two additional normal-CLI checks from final_review.md.

This checks the local harness ledger using fixture agent IDs. It does not
create native agent sessions or verify operating-system sandbox enforcement.

Usage:
    python3 additional_resume_review.py --repo /path/to/codex-harness
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Codex Harness repository root.")
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve(strict=True)
    if not (repo / "tests/test_run_lifecycle.py").is_file():
        parser.error("--repo must contain tests/test_run_lifecycle.py")
    sys.path.insert(0, str(repo / "tests"))
    from test_run_lifecycle import RunLifecycleTests

    class AdditionalResumeReview(RunLifecycleTests):
        def runTest(self):
            for kind in ("normalized-glob", "file-symlink"):
                with self.subTest(kind=kind):
                    origin, last = "origin-" + kind, "final-" + kind
                    output_suffix = (
                        "task-01/outputs/nested/report1.txt"
                        if kind == "normalized-glob" else "task-01/outputs/report.txt"
                    )
                    target = f".harness/runs/{origin}/{output_suffix}"
                    if kind == "normalized-glob":
                        owned = f"./.harness//runs/{origin}/task-01/outputs/**/report?.txt"
                        expected = f".harness/runs/{last}/task-01/outputs/**/report?.txt"
                    else:
                        (self.project / "file-output-alias").symlink_to(self.project / target)
                        owned = "file-output-alias"
                        expected = f".harness/runs/{last}/task-01/outputs/report.txt"
                    self.init([self.task(ownership=[owned])], run_id=origin)
                    self.start(run_id=origin)
                    output = self.project / target
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text("Initial accepted content")
                    self.submit(self.result(run_id=origin, artifacts=[target]), run_id=origin)
                    self.observe("closed", run_id=origin)
                    previous, preserved = origin, []
                    for number in range(2):
                        reused = f"reuse-{kind}-{number}"
                        result = self.cli("run.py", "resume", "--run", previous, "--new-run", reused)
                        self.assertEqual(json.loads(result.stdout)["reused"], ["01"])
                        self.assertEqual(self.stored(reused)["tasks"][0]["ownership"], [owned])
                        self.complete(run_id=reused)
                        preserved.append(previous)
                        previous = reused
                    preserved.append(previous)

                    def snapshot():
                        return {
                            run: {
                                p.relative_to(self.project / ".harness/runs" / run): p.read_bytes()
                                for p in (self.project / ".harness/runs" / run).rglob("*")
                                if p.is_file()
                            }
                            for run in preserved
                        }

                    before = snapshot()
                    self.input.write_text("Changed requirement for " + kind)
                    self.cli("run.py", "resume", "--run", previous, "--new-run", last)
                    self.assertEqual(self.stored(last)["tasks"][0]["ownership"], [expected])
                    self.start(run_id=last)
                    new_target = f".harness/runs/{last}/{output_suffix}"
                    (self.project / new_target).parent.mkdir(parents=True, exist_ok=True)
                    (self.project / new_target).write_text("New accepted content")
                    self.submit(self.result(run_id=last, artifacts=[new_target]), run_id=last)
                    self.observe("closed", run_id=last)
                    self.complete(run_id=last)
                    self.assertEqual(before, snapshot())
                    print(
                        "VERIFIED", kind,
                        ": matching output created; three prior generations byte-for-byte unchanged",
                    )

    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([AdditionalResumeReview()]))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
