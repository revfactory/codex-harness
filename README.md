<p align="center">
  <img src="codex-harness.png" alt="Codex Harness robot mascot with coding tools" width="800">
</p>

<p align="center">
  <a href=".codex-plugin/plugin.json"><img src="https://img.shields.io/badge/Version-0.1.0-brightgreen.svg" alt="Version 0.1.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="Apache 2.0 License"></a>
  <img src="https://img.shields.io/badge/Codex-Plugin-purple.svg" alt="Codex Plugin">
  <img src="https://img.shields.io/badge/Patterns-6_Architectures-orange.svg" alt="6 Architecture Patterns">
  <img src="https://img.shields.io/badge/Mode-Subagents-green.svg" alt="Codex Subagents">
  <a href="https://github.com/revfactory/codex-harness/stargazers"><img src="https://img.shields.io/github/stars/revfactory/codex-harness?style=social" alt="GitHub Stars"></a>
</p>

# Harness for Codex

**English** | [한국어](README_KO.md) | [日本語](README_JA.md)

A project-scoped harness factory for Codex. It inspects a project, designs a small team, and creates native Codex agents and reusable skills. A parent orchestrator schedules independent tasks in parallel, integrates the results, and owns final verification.

This is an independent migration of [revfactory/harness](https://github.com/revfactory/harness), based on upstream commit [`cceac68`](https://github.com/revfactory/harness/commit/cceac68ea1d0ad198ef4b7b906cd238375836387). The original project's team-design workflow and six architecture patterns are adapted to Codex. Upstream Claude Code benchmarks do not establish performance for this migration.

## Install as a plugin (recommended)

Run these two commands in your terminal. You do not need to clone this repository or run the Python installer:

Add Marketplace  
```bash
codex plugin marketplace add https://github.com/revfactory/codex-harness.git
```

Add Plugin  
```bash
codex plugin add codex-harness@codex-harness
```


Open **your target project in a new Codex session**, then send:

```text
$harness Build a harness for this project. Use subagents in parallel for independent tasks.
```

The plugin provides the `harness` skill, references, and helper scripts. It can inspect your project and create suitable agents and skills when asked. To install the predefined five-agent team and project configuration, use the [project installer](#install-into-another-project-optional).

The command syntax above was checked against Codex CLI **0.153.4**. After adding the marketplace, you can also use `/plugins` in the CLI to select **Codex Harness → Harness for Codex → Install**, then start a new session. See [quickstart](docs/quickstart.md#install-as-a-plugin-recommended) for desktop installation, a local-checkout option, and troubleshooting. [Official plugin guide](https://learn.chatgpt.com/docs/plugins).

## Start in this checkout (for development)

Clone the repository:

```bash
git clone https://github.com/revfactory/codex-harness.git
cd codex-harness
```

Open this directory as a trusted local project in a **new Codex session**, then send:

```text
$harness Build a harness for this project. Use subagents in parallel for independent tasks.
```

Korean also works:

```text
$harness 이 프로젝트에 맞는 하네스를 구성해줘. 독립 작업은 서브에이전트로 병렬 처리해줘.
```

Project agents and the `harness` skill are already in this checkout. If newly generated agents are absent from the current session, start a new thread in the project. See [quickstart](docs/quickstart.md) for installation into another project and a live smoke test.

## Install into another project (optional)

Requires Python 3.11+; the scripts use only the standard library. Run from this checkout:

```bash
python3 scripts/install.py --target /absolute/path/to/project --dry-run
python3 scripts/install.py --target /absolute/path/to/project
python3 scripts/validate.py --project /absolute/path/to/project
```

The installer copies the canonical `harness` skill and five seed agents, and merges supported project configuration forms and the `AGENTS.md` pointer while preserving existing content. Review any reported conflicts. An inline `agents = { ... }` table that needs missing defaults may require expansion to `[agents]`; the installer reports this before writing files. It does not change personal Codex configuration. Open the target in a new trusted local Codex session after installation.

The [Codex plugin manifest](.codex-plugin/plugin.json) packages the skill from the standard `skills/` directory. The [repository marketplace](.agents/plugins/marketplace.json) makes it installable as `codex-harness@codex-harness`. Plugin installation alone does **not** create project agent TOMLs, project configuration, or an `AGENTS.md` pointer; the project installer supplies those files.

## How the team works

| Role | Responsibility | Configured sandbox |
| --- | --- | --- |
| Parent session | Scheduling, shared interfaces, integration, final acceptance | Current session |
| `harness_explorer` | Map relevant code and return cited evidence | Read-only |
| `harness_architect` | Plan boundaries, dependencies, and acceptance criteria in its response | Read-only |
| `harness_worker` | Implement within explicitly owned files | Workspace-write |
| `harness_reviewer` | Report actionable defects without editing | Read-only |
| `harness_qa` | Execute checks; write assigned tests and verification artifacts | Workspace-write |

The parent assigns each task an objective, owned files, dependencies, and acceptance criteria. Workers share a workspace, preserve each other's edits, and return evidence. Shared files have one owner; dependent tasks wait for their inputs. The parent closes or reuses completed agents and handles capacity limits without dropping work.

The project config enables native subagents and requests at most **three concurrent subagent threads**; the parent session coordinates them. Runtime limits may reduce available capacity. Models and reasoning effort inherit from the parent. Child agents do not recursively delegate by default. QA's prohibition on product edits is an instruction boundary within its write-enabled sandbox. See [multi-agent design](docs/multi-agent.md) for the full protocol and sandbox caveats.

## Layout

```text
AGENTS.md                         Project entry point
.codex/config.toml                Project subagent settings
.codex/agents/*.toml               Five native seed agents
skills/harness/                   Single physical skill source
  SKILL.md                        Canonical harness-building workflow
  references/                     Patterns, handoffs, examples, QA guidance
  scripts/create_agent.py         Create a project agent safely
  scripts/validate.py             Structural and run completion validation
  scripts/run.py                  Run state, refreshed context, agent lifecycle
  scripts/communication.py        Explicit collaboration event log
.agents/skills/harness             Symlink → ../../skills/harness
.codex-plugin/plugin.json         Plugin manifest; skills = "./skills/"
.agents/plugins/marketplace.json  Installable repository marketplace
scripts/install.py                Install into a target project
scripts/validate.py               Repository validation entry point
tests/                            Automated installer and validation checks
docs/                             Usage, architecture, migration, compatibility
.harness/runs/<run-id>/            Runtime plans, packets, results, agent registry
_workspace/communications/         Explicit message JSONL logs and optional exports
```

In this checkout, `.agents/skills/harness` links to `skills/harness` for project discovery, so the plugin and project use one source. The installer follows that alias and copies regular files into the target project's `.agents/skills/harness/`; the installed project needs no symlink.

The six design patterns remain available: pipeline, fan-out/fan-in, expert pool, producer/reviewer, supervisor, and hierarchical decomposition. Hierarchical decomposition becomes a parent-managed dependency graph; it does not require recursive agent spawning.

## Run state and agent communication

The shell examples below use paths created by the optional project installer. With only the plugin installed, ask `$harness` to use the helpers from its installed skill directory.

The parent initializes a run from an actual project plan, records native agent IDs, and gives each child a refreshed packet with the project root, stable input fingerprints, decisions, skills, ownership, dependencies, and acceptance criteria. Related follow-ups can reuse the same agent; independent reviews can use fresh context when the runtime supports it. Models and the three-subagent concurrency setting stay inherited/configured as above.

```bash
python3 .agents/skills/harness/scripts/run.py --project . init \
  --plan-file /absolute/path/to/project-plan.json --run-id project-v1
python3 .agents/skills/harness/scripts/run.py --project . ready --run project-v1
python3 .agents/skills/harness/scripts/run.py --project . status --run project-v1
```

Workers proactively share findings, ask focused questions, answer peers, and announce dependency readiness and handoffs. The parent confirms contracts and ownership. Important messages are explicitly logged under `_workspace/communications/<run-id>.jsonl`: record the outward event, use the actual native messaging tool, then record its delivery outcome and correlate replies. Read-only roles ask the parent to log and route their messages. Local logging does not send messages or automatically capture Codex internals.

```bash
python3 .agents/skills/harness/scripts/communication.py --project . --run project-v1 view \
  --format markdown --output _workspace/communications/project-v1.md
python3 .agents/skills/harness/scripts/validate.py --project . --run project-v1 --complete
```

Task completion is separate from native session idleness or termination. Before transferring write ownership, the parent confirms the previous agent has stopped or is idle. On resume, changed inputs/results and affected dependent tasks are invalidated. Use ordinary `resume` when only existing input file contents change. For changed decisions, ownership, acceptance criteria, objective, or added/removed tasks, supply a revised template without editing the old run ledger:

```bash
python3 .agents/skills/harness/scripts/run.py --project . resume \
  --run project-v1 --new-run project-v2 \
  --plan-file /absolute/path/to/revised-project-plan.json
```

Changed contracts and affected descendants become pending; unchanged accepted work can be reused. Product fixes belong to workers; QA verifies the corrected behavior. See the [runtime guide](skills/harness/references/runtime-guide.md) for plan/result schemas, exact commands, and message correlation.

## Verification

```bash
python3 scripts/validate.py --project .
python3 -m unittest discover -s tests -v
```

For an optional live test, run from this checkout with an authenticated Codex client. Choose a new target directory:

```bash
python3 scripts/live_smoke.py run --target _workspace/live-tests/NEW_ID
```

The script exercises two native custom workers, a blocked task and failed completion check, an input correction followed by resume and reuse of the unchanged result, then two QA assertions. It allows up to 1,200 seconds and is excluded from default CI. Inspect its actual transcript, files, and check results; the command itself is not a recorded pass.

**97 automated tests passed**. A repeated-resume correction preserves ancestor outputs; its [verification summary and two unresolved cross-run limitations](docs/verification/resume-provenance-2026-09-17/README.md) are recorded separately. A separate **Codex CLI 0.153.4 run used two native custom workers and an independent QA agent** to verify file creation, peer communication records, a blocked completion, partial resume, unchanged-result reuse, and passing final tests. See the [verification record](docs/verification.md) for evidence and limits, including the earlier read-only smoke and observed ephemeral-session issue. Other clients, sandbox enforcement, and performance were not benchmarked. Repeat the live regression above in your environment.

- [Quickstart](docs/quickstart.md)
- [Multi-agent architecture and task packets](docs/multi-agent.md)
- [Claude Code → Codex migration](docs/migration.md)
- [Codex compatibility](docs/compatibility.md)
- [Service migration starter example](examples/service-migration/README.md)
- [Contributing](CONTRIBUTING.md)

## License and attribution

[Apache License 2.0](LICENSE). Original Harness by the contributors to [revfactory/harness](https://github.com/revfactory/harness). This migration retains the upstream license; its Codex behavior and verification status are documented separately from upstream releases.
