"""Cross-run lifecycle regressions reached through the public CLI only.

The IDs below model observed native threads. These tests exercise the local
ledger and do not claim to create or inspect a real native agent session.
"""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from test_run_checks import RunFixture
import test_run_state as state_tests


class CrossRunLifecycleTests(RunFixture):
    init = state_tests.RunStateTests.init
    stored = state_tests.RunStateTests.stored
    start = state_tests.RunStateTests.start
    submit = state_tests.RunStateTests.submit

    def observe(self, state: str, run_id: str = "current"):
        return self.cli(
            "run.py", "agent", "--run", run_id,
            "--agent-id", "observed-agent-01", "--state", state,
            "--evidence", "Fixture runtime observed the stated lifecycle.",
        )

    def test_other_run_cannot_dispatch_overlapping_active_writer(self) -> None:
        """A different run ID must not bypass an existing file ownership hold."""
        self.init([self.task(ownership=["shared.txt"])])
        self.start()
        self.init([self.task(ownership=["shared.txt"])], run_id="parallel")

        rejected = self.start(
            agent_id="observed-agent-02", run_id="parallel", success=False
        )
        self.assertIn("ownership", rejected.stderr.lower())
        self.assertEqual(self.stored("parallel")["tasks"][0]["status"], "pending")

    def test_resume_does_not_release_unclosed_native_slot(self) -> None:
        """Idle is reusable, but changing run IDs does not close a thread."""
        (self.project / ".codex/config.toml").write_text(
            "[agents]\nmax_concurrent_threads_per_session = 1\n", encoding="utf-8"
        )
        self.init()
        self.start()
        self.submit()
        self.observe("idle")
        self.input.write_text("Changed requirement after the first run.\n", encoding="utf-8")
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")

        rejected = self.start(
            agent_id="observed-agent-02", run_id="resumed", success=False
        )
        self.assertIn("capacity", rejected.stderr.lower())
        self.assertEqual(self.stored("resumed")["tasks"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
