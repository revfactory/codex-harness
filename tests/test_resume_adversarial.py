"""Normal-CLI regressions for multi-generation resume provenance."""

from __future__ import annotations

import json
import unittest

from test_run_checks import RunFixture
import test_run_state as state_tests


class ResumeAdversarialTests(RunFixture):
    init = state_tests.RunStateTests.init
    stored = state_tests.RunStateTests.stored
    ready = state_tests.RunStateTests.ready
    start = state_tests.RunStateTests.start
    submit = state_tests.RunStateTests.submit
    release = state_tests.RunStateTests.release

    def test_second_resume_remaps_reused_ancestor_output_before_rerun(self) -> None:
        """A reused task can later become stale without editing ancestor files."""
        old_output = ".harness/runs/current/task-01/outputs/report.txt"
        self.init([self.task(ownership=[old_output])])
        self.start()
        output = self.project / old_output
        output.parent.mkdir(parents=True)
        output.write_text("Accepted version one", encoding="utf-8")
        self.submit(self.result(artifacts=[old_output]))
        self.release()
        original_bytes = output.read_bytes()

        first = self.cli("run.py", "resume", "--run", "current", "--new-run", "reused")
        self.assertEqual(json.loads(first.stdout)["reused"], ["01"])
        self.input.write_text("version two\n", encoding="utf-8")
        second = self.cli("run.py", "resume", "--run", "reused", "--new-run", "rerun")
        self.assertIn("01", json.loads(second.stdout)["pending"])
        task = self.stored("rerun")["tasks"][0]
        expected_output = ".harness/runs/rerun/task-01/outputs/report.txt"
        self.assertEqual(task["ownership"], [expected_output],
                         "A stale task retained its ancestor run's output ownership.")
        self.start(run_id="rerun")
        fresh_output = self.project / expected_output
        fresh_output.parent.mkdir(parents=True, exist_ok=True)
        fresh_output.write_text("Accepted version two", encoding="utf-8")
        self.submit(self.result(run_id="rerun", artifacts=[expected_output]), run_id="rerun")
        self.release(run_id="rerun")
        self.complete(run_id="rerun")
        self.assertEqual(output.read_bytes(), original_bytes)

    def test_repeated_reuse_preserves_history_for_directory_alias_and_project_outputs(self) -> None:
        """Contract changes obey the same old-run protection as input changes."""
        for kind in ("directory", "glob", "alias", "project"):
            with self.subTest(kind=kind):
                origin = f"origin-{kind}"
                final = f"final-{kind}"
                relative_dir = f".harness/runs/{origin}/task-01/outputs"
                artifact = f"{relative_dir}/report.txt"
                owned = relative_dir + "/"
                expected = f".harness/runs/{final}/task-01/outputs/"
                if kind == "glob":
                    owned += "*.txt"
                    expected += "*.txt"
                elif kind == "alias":
                    (self.project / "output-alias").symlink_to(self.project / relative_dir, target_is_directory=True)
                    owned = "output-alias/"
                    artifact = "output-alias/report.txt"
                elif kind == "project":
                    owned = "reports/project-report.txt"
                    artifact = owned
                    expected = owned

                self.init([self.task(ownership=[owned])], run_id=origin)
                self.start(run_id=origin)
                original_output = self.project / artifact
                original_output.resolve().parent.mkdir(parents=True, exist_ok=True)
                original_output.write_text("Version one", encoding="utf-8")
                self.submit(self.result(run_id=origin, artifacts=[artifact]), run_id=origin)
                self.release(run_id=origin)

                previous = origin
                for index in range(3):
                    current = f"reuse-{kind}-{index}"
                    result = self.cli("run.py", "resume", "--run", previous, "--new-run", current)
                    self.assertEqual(json.loads(result.stdout)["reused"], ["01"])
                    previous = current
                template = self.stored(previous)
                template["tasks"][0]["acceptance"].append("The revised output has been inspected.")
                template_file = self.directory / f"template-{kind}.json"
                template_file.write_text(json.dumps(template), encoding="utf-8")
                self.cli("run.py", "resume", "--run", previous, "--new-run", final,
                         "--plan-file", template_file)
                task = self.stored(final)["tasks"][0]
                self.assertEqual(task["status"], "pending")
                self.assertEqual(task["ownership"], [expected])

                old_directory = self.project / ".harness/runs" / origin
                old_bytes = {p.relative_to(old_directory): p.read_bytes()
                             for p in old_directory.rglob("*") if p.is_file()}
                self.start(run_id=final)
                new_artifact = artifact if kind == "project" else f".harness/runs/{final}/task-01/outputs/report.txt"
                new_output = self.project / new_artifact
                new_output.parent.mkdir(parents=True, exist_ok=True)
                new_output.write_text("Version two", encoding="utf-8")
                self.submit(self.result(run_id=final, artifacts=[new_artifact]), run_id=final)
                self.release(run_id=final)
                self.complete(run_id=final)
                self.assertEqual(old_bytes, {p.relative_to(old_directory): p.read_bytes()
                                            for p in old_directory.rglob("*") if p.is_file()})

    def test_resume_rejects_writing_an_unrelated_run(self) -> None:
        """A replacement plan cannot redirect a rerun into unrelated history."""
        self.init(run_id="unrelated")
        unrelated_dir = self.project / ".harness/runs/unrelated"
        before = {p.relative_to(unrelated_dir): p.read_bytes()
                  for p in unrelated_dir.rglob("*") if p.is_file()}
        self.init()
        template = self.stored()
        template["tasks"][0]["ownership"] = [".harness/runs/unrelated/task-01/outputs/report.txt"]
        template_file = self.directory / "unrelated-template.json"
        template_file.write_text(json.dumps(template), encoding="utf-8")
        self.cli("run.py", "resume", "--run", "current", "--new-run", "redirected",
                 "--plan-file", template_file, success=False)
        self.assertFalse((self.project / ".harness/runs/redirected").exists())
        self.assertEqual(before, {p.relative_to(unrelated_dir): p.read_bytes()
                                 for p in unrelated_dir.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
