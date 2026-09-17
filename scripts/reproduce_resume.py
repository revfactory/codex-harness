#!/usr/bin/env python3
"""Reproduce resume provenance with normal CLI calls and isolated fixture files.

No native agent runs: agent IDs and lifecycle observations are explicit fixtures.
The same script reports old-output preservation before and after a product fix.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scripts = args.repo.resolve() / "skills/harness/scripts"
    trace = []
    with tempfile.TemporaryDirectory(prefix="resume-provenance-reproducer-") as temporary:
        root = Path(temporary)
        project = root / "project"
        project.mkdir()
        agents = project / ".codex/agents"
        agents.mkdir(parents=True)
        (agents / "test-worker.toml").write_text(
            'name = "test_worker"\ndescription = "Fixture worker"\n'
            'developer_instructions = "Only a local CLI test fixture."\n', encoding="utf-8")
        (project / ".codex/config.toml").write_text(
            "[agents]\nenabled = true\nmax_concurrent_threads_per_session = 3\n", encoding="utf-8")
        specification = project / "spec.txt"
        specification.write_text("version one\n", encoding="utf-8")
        original_path = ".harness/runs/current/task-export/outputs/report.txt"
        original = project / original_path
        plan = {"objective": "Export the report for the current specification.", "tasks": [{
            "id": "export", "role": "test_worker", "dependencies": [],
            "ownership": [original_path], "inputs": ["spec.txt"],
            "context": {"decisions": [], "skill_paths": []},
            "acceptance": ["The report matches the current specification."], "required": True}]}
        plan_file = root / "plan-template.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")

        def cli(script: str, *arguments: object) -> subprocess.CompletedProcess:
            command = [sys.executable, str(scripts / script), "--project", str(project),
                       *(str(item) for item in arguments)]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                    timeout=30, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            trace.append({"command": command, "returncode": result.returncode,
                          "stdout": result.stdout, "stderr": result.stderr})
            if result.returncode:
                raise RuntimeError(json.dumps(trace[-1], ensure_ascii=False))
            return result

        def complete_task(run: str, artifact: str, text: str) -> None:
            cli("run.py", "start", "--run", run, "--task", "export", "--agent-id", "fixture-native-id")
            output = project / artifact
            if not output.resolve().is_relative_to(project.resolve()):
                raise RuntimeError("Unexpected fixture ownership escape")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            assert output.read_text(encoding="utf-8") == text
            result = {"run_id": run, "task_id": "export", "status": "completed",
                      "summary": "The CLI fixture wrote and read back the expected report bytes.",
                      "artifacts": [artifact], "issues": [], "checks": [{
                          "name": "Report byte equality", "status": "passed", "required": True,
                          "evidence": f"The reproducer verified that report bytes equal {text!r}."}]}
            result_file = root / f"{run}-result.json"
            result_file.write_text(json.dumps(result), encoding="utf-8")
            cli("run.py", "result", "--run", run, "--task", "export", "--result-file", result_file)
            cli("run.py", "agent", "--run", run, "--agent-id", "fixture-native-id", "--state", "closed",
                "--evidence", "CLI fixture is quiescent; no native agent execution is claimed.")

        cli("run.py", "init", "--run-id", "current", "--plan-file", plan_file)
        complete_task("current", original_path, "Accepted version one")
        before = original.read_text(encoding="utf-8")
        first = json.loads(cli("run.py", "resume", "--run", "current", "--new-run", "reused").stdout)
        specification.write_text("version two\n", encoding="utf-8")
        second = json.loads(cli("run.py", "resume", "--run", "reused", "--new-run", "rerun").stdout)
        new_plan = json.loads((project / ".harness/runs/rerun/plan.json").read_text(encoding="utf-8"))
        assigned = new_plan["tasks"][0]["ownership"][0]
        complete_task("rerun", assigned, "Accepted version two")
        completion = cli("validate.py", "--run", "rerun", "--complete")
        after = original.read_text(encoding="utf-8")
        report = {
            "repo": str(args.repo.resolve()),
            "scope": "Normal local CLI transitions; native agent execution is not tested.",
            "first_resume_reused": first["reused"],
            "second_resume_pending": list(second["pending"]),
            "assigned_write_path": assigned,
            "expected_write_path": ".harness/runs/rerun/task-export/outputs/report.txt",
            "original_output_before": before, "original_output_after": after,
            "original_output_unchanged": before == after,
            "completion_returncode": completion.returncode,
            "completion_stdout": completion.stdout,
            "commands": trace,
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
