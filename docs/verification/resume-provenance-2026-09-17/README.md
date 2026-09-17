# Repeated-resume verification summary

Baseline: `79b82281d305c89181fbb216499d5f1e962c14ed`.

## Defect and correction

A completed task could be reused unchanged and then become stale in a later
resume. The rerun retained the original run's output ownership, so following
its assigned path overwrote an earlier accepted artifact while completion
validation still passed.

The correction resolves ownership against the full preserved run ancestry.
Stale tasks write into the new run; unchanged results remain reusable. Directory,
glob and in-project symlink aliases are handled. Ordinary project output paths
remain unchanged. Ownership in unrelated run records is rejected before a new
run is created.

## Verification

- Baseline suite: 94 tests passed.
- New core regression: failed before correction and passed afterward.
- Corrected suite: 97 tests passed, including three new test methods.
- The same CLI reproducer changed `original_output_unchanged` from false to true.
- Structural validation and `git diff --check` passed.
- Independent checks covered normalized paths, complex globs and a single-file
  symlink, preserving all files in three previous generations.
- Patch application to a clean baseline reproduced the validated changes and
  passed the focused regression and structural checks.

Raw execution logs and traces are not included in this PR. The checks can be
reproduced with Python 3.11+ from the checkout root:

```bash
python3 scripts/reproduce_resume.py --repo . --output resume-after.json
python3 -m unittest discover -s tests -p test_resume_adversarial.py -v
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --project .
python3 experiments/resume-audit/additional_resume_review.py --repo .
```

The reproducer uses temporary fixtures and simulated agent IDs, not native
agent execution. Inspect `original_output_unchanged` in its JSON output; the
reproducer itself returns zero when observation completes. Use the regression
tests for CI assertions.

## Limits

Two additional cross-run assertions remain unresolved and are not included in
the 97 passing tests: overlapping writers in separate runs are not globally
blocked, and idle unclosed agents from an old run are not counted in the new
run's capacity check.

```bash
python3 experiments/resume-audit/cross_run_limitations.py -v
```

Current expected observation: two failures, exit 1. This demonstrates local
ledger behavior, not actual simultaneous native agent execution.

Missing or invalid ancestry is rejected before creating a new run. This change
does not prevent arbitrary agent writes, fabricated evidence, undeclared
inputs, or concurrent external filesystem changes. Linux/Python 3.12.14 was
used for this audit; Windows, macOS, live Codex CLI behavior, model quality,
productivity and cost effects were not tested.
