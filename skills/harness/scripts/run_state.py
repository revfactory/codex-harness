"""Persistent parent-owned task state; native agents are controlled separately."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import tomllib

from common import safe_path
from run_support import atomic_json, load_json, locked, project_path, run_path, snapshot_inputs
from validate import ownership_prefix

TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
ACTIVE = {"running", "stop_requested"}
FINISHED = {"completed", "failed", "blocked"}
CONTRACT_FIELDS = ("id", "role", "dependencies", "ownership", "acceptance", "required", "inputs", "context", "max_attempts")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project(project: Path) -> Path:
    project = Path(project).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError(f"Project is not a directory: {project}")
    return project


def _strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be an array of non-empty strings.")
    return list(value)


def _overlap(left: str, right: str) -> bool:
    a, b = ownership_prefix(left), ownership_prefix(right)
    return not a or not b or a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _project_overlap(project: Path, left: str, right: str) -> bool:
    a = project_path(project, ownership_prefix(left) or ".", allow_missing=True).relative_to(project).as_posix()
    b = project_path(project, ownership_prefix(right) or ".", allow_missing=True).relative_to(project).as_posix()
    return _overlap(a, b)


def _contract(objective: str, task: dict) -> str:
    body = {"objective": objective, **{key: task.get(key) for key in CONTRACT_FIELDS}}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def task_contract_fingerprint(objective: str, task: dict) -> str:
    """Public checkpoint digest for the completion validator."""
    return _contract(objective, task)


def _capacity(project: Path) -> int | None:
    path = project / ".codex" / "config.toml"
    if not path.is_file():
        return None
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    agents = config.get("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("Project agents configuration must be a table.")
    value = agents.get("max_concurrent_threads_per_session", agents.get("max_threads"))
    if value is not None and (type(value) is not int or value < 1):
        raise ValueError("Project agent concurrency limit must be a positive integer.")
    return value


def _ordered(tasks: list[dict]) -> list[dict]:
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Task IDs must be unique.")
    active, visited, ordered = set(), set(), []

    def visit(identifier: str) -> None:
        if identifier not in by_id:
            raise ValueError(f"Unknown dependency: {identifier}")
        if identifier in active:
            raise ValueError(f"Dependency cycle at task {identifier}.")
        if identifier in visited:
            return
        active.add(identifier)
        for dependency in by_id[identifier]["dependencies"]:
            visit(dependency)
        active.remove(identifier)
        visited.add(identifier)
        ordered.append(by_id[identifier])

    for identifier in by_id:
        visit(identifier)
    return ordered


def _prepare(project: Path, source: dict, run_id: str, previous: str | None = None) -> dict:
    run_path(project, run_id)
    if not isinstance(source, dict) or not isinstance(source.get("objective"), str) or not source["objective"].strip():
        raise ValueError("Plan needs a non-empty objective.")
    if not isinstance(source.get("tasks"), list):
        raise ValueError("Plan needs a tasks array.")
    plan = {"schema_version": 2, "run_id": run_id, "previous_run_id": previous,
            "project_root": str(project), "objective": source["objective"], "created_at": _now(), "tasks": []}
    for raw in source["tasks"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not TASK_ID.fullmatch(raw["id"]):
            raise ValueError("Task ID must contain only letters, digits, underscores, or hyphens.")
        task = {key: deepcopy(raw[key]) for key in CONTRACT_FIELDS if key in raw}
        task.setdefault("role", "default")
        if not isinstance(task["role"], str) or not task["role"].strip():
            raise ValueError(f"Task {task['id']} needs a role.")
        for field in ("dependencies", "ownership", "acceptance"):
            task[field] = _strings(raw.get(field), f"Task {task['id']} {field}")
        if not task["acceptance"] or type(raw.get("required")) is not bool:
            raise ValueError(f"Task {task['id']} needs acceptance criteria and a required boolean.")
        task.setdefault("max_attempts", 2)
        if type(task["max_attempts"]) is not int or task["max_attempts"] < 1:
            raise ValueError("max_attempts must be a positive integer.")
        context = raw.get("context", {})
        if not isinstance(context, dict):
            raise ValueError("Task context must be an object.")
        task["context"] = {key: _strings(context.get(key, []), f"Task context.{key}") for key in ("decisions", "skill_paths")}
        task["inputs"] = list(dict.fromkeys(_strings(raw.get("inputs", []), "Task inputs") + task["context"]["skill_paths"]))
        for owned in task["ownership"]:
            prefix = ownership_prefix(owned)
            project_path(project, prefix or ".", allow_missing=True)
        for path in task["inputs"]:
            project_path(project, path, allow_missing=True)
            if any(_project_overlap(project, path, owned) for owned in task["ownership"]):
                raise ValueError(f"Task {task['id']}: immutable input overlaps editable ownership: {path}")
        task.update(status="pending", attempts=0, agent_id=None,
                    input_fingerprints=snapshot_inputs(project, task["inputs"]), dependency_fingerprints={})
        task["contract_fingerprint"] = _contract(plan["objective"], task)
        plan["tasks"].append(task)
    _ordered(plan["tasks"])
    return plan


def _load(project: Path, run_id: str) -> tuple[Path, dict, dict]:
    directory = run_path(project, run_id)
    plan = load_json(safe_path(directory / "plan.json"))
    registry = load_json(safe_path(directory / "agents.json"))
    if not isinstance(plan, dict) or plan.get("schema_version") != 2:
        raise ValueError("Run must use schema_version 2; initialize a new run from its plan.")
    if plan.get("run_id") != run_id or plan.get("project_root") != str(project):
        raise ValueError("Run ID or project root does not match its stored plan.")
    if not isinstance(plan.get("tasks"), list) or not isinstance(registry, dict) or not isinstance(registry.get("agents"), dict):
        raise ValueError("Run plan or agent registry is malformed.")
    if registry.get("run_id") != run_id:
        raise ValueError("Agent registry run_id does not match the run.")
    for task in plan["tasks"]:
        if not isinstance(task, dict) or not TASK_ID.fullmatch(str(task.get("id", ""))):
            raise ValueError("Run contains an invalid task ID.")
        for field in ("dependencies", "ownership", "acceptance", "inputs"):
            _strings(task.get(field), f"Task {task['id']} {field}")
        if task.get("status") not in {"pending", "running", "completed", "failed", "blocked", "skipped"}:
            raise ValueError(f"Task {task['id']} has an invalid status.")
        if type(task.get("attempts")) is not int or task["attempts"] < 0:
            raise ValueError(f"Task {task['id']} has an invalid attempts count.")
        if type(task.get("max_attempts")) is not int or task["max_attempts"] < 1:
            raise ValueError(f"Task {task['id']} has an invalid retry limit.")
        if type(task.get("required")) is not bool or (task["required"] and task["status"] == "skipped"):
            raise ValueError(f"Task {task['id']} has an invalid required/skip state.")
    _ordered(plan["tasks"])
    for agent_id, agent in registry["agents"].items():
        if not isinstance(agent_id, str) or not agent_id.strip() or not isinstance(agent, dict):
            raise ValueError("Agent registry contains an invalid entry.")
        if agent.get("state") not in ACTIVE | {"idle", "stopped", "closed"}:
            raise ValueError(f"Agent {agent_id} has an invalid state.")
        _task(plan, agent.get("task_id"))
    for task in plan["tasks"]:
        if task["status"] == "running":
            agent = registry["agents"].get(task.get("agent_id"))
            if agent is None or agent["task_id"] != task["id"]:
                raise ValueError(f"Running task {task['id']} has no matching native agent registry entry.")
    return directory, plan, registry


def _task(plan: dict, task_id: str) -> dict:
    for task in plan["tasks"]:
        if task["id"] == task_id:
            return task
    raise ValueError(f"Unknown task: {task_id}")


def _input_text(plan: dict, task: dict) -> str:
    lines = [f"# Task {task['id']}", "", f"Working root: {plan['project_root']}", f"Run: {plan['run_id']}",
             f"Objective: {plan['objective']}", f"Role: {task['role']}", f"Contract: {task['contract_fingerprint']}"]
    sections = {"Immutable inputs": task["inputs"], "Decisions": task["context"]["decisions"],
                "Skills to read": task["context"]["skill_paths"], "Write ownership": task["ownership"],
                "Acceptance": task["acceptance"], "Dependencies": task["dependencies"]}
    for title, values in sections.items():
        lines.extend(["", f"## {title}", ""] + [f"- {value}" for value in values or ["(none)"]])
    lines.extend(["", "## Version evidence", "", "```json", json.dumps({"inputs": task["input_fingerprints"],
                  "accepted_dependency_outputs": task.get("dependency_fingerprints", {})}, ensure_ascii=False, indent=2), "```", "",
                  "You are not alone. Preserve others' changes and edit only assigned paths.",
                  "The parent owns the run ledger, shared configuration, integration, and acceptance.",
                  "Do not spawn agents. Return completed/blocked/failed with actual checks and evidence.", ""])
    return "\n".join(lines)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".input-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _write_packet(project: Path, directory: Path, plan: dict, task: dict) -> None:
    path = safe_path(directory / f"task-{task['id']}" / "input.md")
    _atomic_text(path, _input_text(plan, task))


def _event(project: Path, run_id: str, kind: str, body: str, task_id: str | None = None) -> None:
    from communication import append_event
    append_event(project, run_id, "parent", "parent", "lifecycle", f"{kind}: {body}", task_id=task_id)


def _write_new(project: Path, plan: dict, results: dict[str, dict] | None = None) -> dict:
    directory = run_path(project, plan["run_id"])
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(exist_ok=False)
    with locked(directory / ".state.lock"):
        for task in plan["tasks"]:
            _write_packet(project, directory, plan, task)
            if results and task["id"] in results:
                atomic_json(directory / f"task-{task['id']}" / "result.json", results[task["id"]])
        atomic_json(directory / "agents.json", {"run_id": plan["run_id"], "agents": {}})
        atomic_json(directory / "plan.json", plan)
    return {"run_id": plan["run_id"], "run_dir": str(directory), "tasks": len(plan["tasks"])}


def init_run(project: Path, plan_file: Path, run_id: str) -> dict:
    project = _project(project)
    if run_path(project, run_id).exists():
        raise ValueError(f"Run already exists: {run_id}")
    plan = _prepare(project, load_json(Path(plan_file)), run_id)
    output = _write_new(project, plan)
    _event(project, run_id, "run_initialized", "Initialized task contracts and context snapshots.")
    return output


def _context_issues(project: Path, plan: dict, task: dict) -> list[str]:
    from run_checks import validate_context
    issues = validate_context(project, task)
    if _contract(plan["objective"], task) != task.get("contract_fingerprint"):
        issues.append("Task decisions or contract changed; create a new run with resume.")
    elif issues:
        issues.append("Create a new run with resume to refresh the immutable context.")
    return issues


def _accepted(project: Path, directory: Path, task: dict) -> tuple[dict | None, list[str]]:
    from run_checks import validate_result
    try:
        path = safe_path(directory / f"task-{task['id']}" / "result.json")
        result = load_json(path)
        errors = validate_result(project, directory, task, result)
        if not isinstance(result, dict):
            return None, errors
        if task.get("artifact_fingerprints") != snapshot_inputs(project, result.get("artifacts", [])):
            errors.append("Accepted output artifacts changed after result recording.")
        return result, errors
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return None, [str(exc)]


def _reasons(project: Path, directory: Path, plan: dict, registry: dict, task: dict) -> list[str]:
    reasons = []
    if task["status"] not in {"pending", "failed", "blocked"}:
        return [f"Task status is {task['status']}."]
    if task["attempts"] >= task.get("max_attempts", 2):
        reasons.append("Retry limit reached; resolve the issue in a new run.")
    reasons.extend(_context_issues(project, plan, task))
    for dependency_id in task["dependencies"]:
        dependency = _task(plan, dependency_id)
        if dependency["status"] != "completed":
            reasons.append(f"Dependency {dependency_id} is {dependency['status']}.")
        else:
            _, errors = _accepted(project, directory, dependency)
            errors.extend(_context_issues(project, plan, dependency))
            reasons.extend(f"Dependency {dependency_id}: {error}" for error in errors)
    active_tasks = {agent["task_id"] for agent in registry["agents"].values() if agent["state"] in ACTIVE}
    active_tasks.update(item["id"] for item in plan["tasks"] if item["status"] == "running")
    for active_id in active_tasks:
        active = _task(plan, active_id)
        if active_id == task["id"] or any(_project_overlap(project, a, b) for a in task["ownership"] for b in active["ownership"]):
            reasons.append(f"Task {active_id} still has an active agent or overlapping write ownership.")
    return reasons


def _ready(project: Path, directory: Path, plan: dict, registry: dict) -> dict:
    ready, blocked = [], {}
    for task in plan["tasks"]:
        if task["status"] not in {"pending", "failed", "blocked"}:
            continue
        reasons = _reasons(project, directory, plan, registry, task)
        if reasons:
            blocked[task["id"]] = reasons
        else:
            ready.append(task["id"])
    return {"run_id": plan["run_id"], "ready": ready, "blocked": blocked,
            "active_agents": [key for key, value in registry["agents"].items() if value["state"] in ACTIVE]}


def ready_tasks(project: Path, run_id: str) -> dict:
    project = _project(project)
    directory = run_path(project, run_id)
    if not directory.is_dir():
        raise ValueError(f"Run does not exist: {run_id}")
    with locked(directory / ".state.lock"):
        directory, plan, registry = _load(project, run_id)
        return _ready(project, directory, plan, registry)


def start_task(project: Path, run_id: str, task_id: str, agent_id: str) -> dict:
    project = _project(project)
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError("Record an existing native agent ID, then deliver its task with the actual native tool.")
    directory = run_path(project, run_id)
    if not directory.is_dir():
        raise ValueError(f"Run does not exist: {run_id}")
    with locked(directory / ".state.lock"):
        directory, plan, registry = _load(project, run_id)
        task = _task(plan, task_id)
        reasons = _reasons(project, directory, plan, registry, task)
        agent = registry["agents"].get(agent_id)
        if agent and agent["state"] != "idle":
            reasons.append(f"Agent {agent_id} is {agent['state']}; only an idle agent may be reused.")
        elif agent and _task(plan, agent["task_id"])["status"] == "running":
            reasons.append("The idle agent's previous task still needs its result recorded.")
        if not agent:
            capacity = _capacity(project)
            occupied = sum(item["state"] != "closed" for item in registry["agents"].values())
            if capacity is not None and occupied >= capacity:
                reasons.append(f"Native agent capacity {capacity} is occupied; reuse an idle agent or confirm a native closure.")
        if reasons:
            raise ValueError("Cannot start task: " + " ".join(reasons))
        dependency_paths = []
        for identifier in task["dependencies"]:
            result, errors = _accepted(project, directory, _task(plan, identifier))
            if errors:
                raise ValueError("Dependency changed before start: " + " ".join(errors))
            dependency_paths.append(str(directory.relative_to(project) / f"task-{identifier}" / "result.json"))
            dependency_paths.extend(result["artifacts"])
        task["dependency_fingerprints"] = snapshot_inputs(project, list(dict.fromkeys(dependency_paths)))
        task.pop("artifact_fingerprints", None)
        task.pop("finished_at", None)
        task.update(status="running", attempts=task["attempts"] + 1, agent_id=agent_id, started_at=_now())
        registry["agents"][agent_id] = {"state": "running", "task_id": task_id,
            "evidence": "Parent registered an existing native agent ID; task transport is separate.", "updated_at": _now()}
        _write_packet(project, directory, plan, task)
        atomic_json(directory / "agents.json", registry)
        atomic_json(directory / "plan.json", plan)
    _event(project, run_id, "task_started", f"Task assigned to native agent {agent_id}.", task_id)
    return {"run_id": run_id, "task_id": task_id, "agent_id": agent_id, "status": "running", "attempts": task["attempts"]}


def record_result(project: Path, run_id: str, task_id: str, result_file: Path) -> dict:
    from run_checks import validate_result
    project = _project(project)
    result = load_json(Path(result_file))
    directory = run_path(project, run_id)
    if not directory.is_dir():
        raise ValueError(f"Run does not exist: {run_id}")
    with locked(directory / ".state.lock"):
        directory, plan, registry = _load(project, run_id)
        task = _task(plan, task_id)
        if task["status"] != "running":
            raise ValueError("A result can only be recorded for a running task.")
        if not isinstance(result, dict) or result.get("status") not in FINISHED:
            raise ValueError("Result status must be completed, blocked, or failed.")
        prospective = {**task, "status": result["status"]}
        errors = validate_result(project, directory, prospective, result)
        if result["status"] == "completed":
            errors.extend(_context_issues(project, plan, prospective))
            if not errors:
                managed = [directory / "plan.json", directory / "agents.json",
                           directory / f"task-{task_id}" / "result.json",
                           project / "_workspace" / "communications" / f"{run_id}.jsonl"]
                for relative in result["artifacts"]:
                    artifact = project_path(project, relative)
                    if any(path == artifact or path.is_relative_to(artifact) for path in managed):
                        errors.append(f"Artifact contains mutable harness state: {relative}. Use a dedicated outputs directory or file.")
        if errors:
            raise ValueError("Result rejected: " + " ".join(errors))
        prospective["artifact_fingerprints"] = snapshot_inputs(project, result["artifacts"])
        prospective["finished_at"] = _now()
        atomic_json(safe_path(directory / f"task-{task_id}" / "result.json"), result)
        task.update(prospective)
        atomic_json(directory / "plan.json", plan)
    _event(project, run_id, "task_result", f"Accepted {result['status']} result; native agent state remains unchanged.", task_id)
    return {"run_id": run_id, "task_id": task_id, "status": result["status"],
            "agent_state": registry["agents"].get(task["agent_id"], {}).get("state")}


def update_agent(project: Path, run_id: str, agent_id: str, state: str, evidence: str) -> dict:
    project = _project(project)
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("Agent lifecycle changes require actual runtime evidence.")
    allowed = {"running": {"idle", "stop_requested", "stopped", "closed"},
               "stop_requested": {"stopped", "closed"}, "idle": {"closed", "stopped"}, "stopped": {"closed"}, "closed": set()}
    directory = run_path(project, run_id)
    if not directory.is_dir():
        raise ValueError(f"Run does not exist: {run_id}")
    with locked(directory / ".state.lock"):
        directory, _, registry = _load(project, run_id)
        agent = registry["agents"].get(agent_id)
        if agent is None:
            raise ValueError(f"Unknown native agent ID: {agent_id}")
        if state not in allowed[agent["state"]]:
            raise ValueError(f"Unsupported agent transition: {agent['state']} -> {state}")
        agent.update(state=state, evidence=evidence.strip(), updated_at=_now())
        atomic_json(directory / "agents.json", registry)
    _event(project, run_id, "agent_lifecycle", f"Native agent {agent_id}: {state}. Evidence: {evidence.strip()}", agent["task_id"])
    return {"run_id": run_id, "agent_id": agent_id, **agent}


def _resume_ancestors(project: Path, plan: dict) -> set[Path]:
    """Include every preserved generation, not only the immediately prior run."""
    ancestors = set()
    while True:
        directory = run_path(project, plan["run_id"])
        if directory in ancestors:
            raise ValueError("Run ancestry contains a cycle.")
        ancestors.add(directory)
        previous = plan.get("previous_run_id")
        if previous is None:
            return ancestors
        plan = load_json(safe_path(run_path(project, previous) / "plan.json"))
        if not isinstance(plan, dict) or plan.get("run_id") != previous or plan.get("project_root") != str(project):
            raise ValueError("Ancestor run ID or project root does not match its stored plan.")


def _resumed_ownership(project: Path, path: str, ancestors: set[Path], new_directory: Path) -> str:
    """Move ancestor output ownership, including globs and symlink aliases."""
    prefix = ownership_prefix(path)
    resolved = project_path(project, prefix or ".", allow_missing=True)
    runs_directory = new_directory.parent
    if resolved == runs_directory or runs_directory.is_relative_to(resolved):
        raise ValueError(f"Ownership includes previous run records: {path}. Assign narrower explicit output paths before resume.")
    if not resolved.is_relative_to(runs_directory):
        return path
    source_directory = runs_directory / resolved.relative_to(runs_directory).parts[0]
    if source_directory == new_directory:
        return path
    if source_directory not in ancestors:
        raise ValueError(f"Ownership includes unrelated run records: {path}. Assign output paths in the new run before resume.")
    normalized = str(PurePosixPath(path))
    suffix = normalized[len(prefix):] + ("/" if path.endswith("/") else "")
    destination = new_directory / resolved.relative_to(source_directory)
    return destination.relative_to(project).as_posix() + suffix


def resume_run(project: Path, old_id: str, new_id: str, plan_file: Path | None = None) -> dict:
    project = _project(project)
    old_directory, new_directory = run_path(project, old_id), run_path(project, new_id)
    if not old_directory.is_dir():
        raise ValueError(f"Run does not exist: {old_id}")
    if new_directory.exists():
        raise ValueError(f"Run already exists: {new_id}")
    with locked(old_directory / ".state.lock"):
        old_directory, old, registry = _load(project, old_id)
        if any(agent["state"] in ACTIVE for agent in registry["agents"].values()):
            raise ValueError("Cannot resume while old native agents are running or stop_requested; confirm they stopped first.")
        source = old if plan_file is None else load_json(Path(plan_file))
        plan = _prepare(project, source, new_id, previous=old_id)
        ancestors = _resume_ancestors(project, old)
        previous_tasks = {task["id"]: task for task in old["tasks"]}
        reused, results, invalidated = set(), {}, {}
        for task in _ordered(plan["tasks"]):
            original = previous_tasks.get(task["id"])
            reason = []
            result = None
            if original is None:
                reason.append("New task has no previous accepted result.")
            else:
                if task["contract_fingerprint"] != original.get("contract_fingerprint"):
                    reason.append("The replacement plan changed this task's contract or objective.")
                if original["status"] != "completed":
                    reason.append(f"Previous status was {original['status']}.")
                reason.extend(_context_issues(project, old, original))
                result, errors = _accepted(project, old_directory, original)
                reason.extend(errors)
            if any(identifier not in reused for identifier in task["dependencies"]):
                reason.append("A dependency must be rerun.")
            if reason:
                # A retried task must write into its new run, preserving all old records.
                mapped = [_resumed_ownership(project, path, ancestors, new_directory) for path in task["ownership"]]
                task["ownership"] = mapped
                for path in task["inputs"]:
                    if any(_project_overlap(project, path, owned) for owned in mapped):
                        raise ValueError(f"Task {task['id']}: resumed ownership overlaps immutable input: {path}")
                task["contract_fingerprint"] = _contract(plan["objective"], task)
                invalidated[task["id"]] = reason
                continue
            result = deepcopy(result)
            result["run_id"] = new_id
            result["reused_from"] = {"run_id": old_id, "task_id": task["id"]}
            task.update(status="completed", reused_from={"run_id": old_id, "task_id": task["id"]},
                        artifact_fingerprints=deepcopy(original["artifact_fingerprints"]))
            # Reused outputs remain in their immutable old location; no old bytes are edited.
            task["dependency_fingerprints"] = deepcopy(original.get("dependency_fingerprints", {}))
            results[task["id"]] = result
            reused.add(task["id"])
        # All reuse decisions are read-only until this preflight has completed.
        output = _write_new(project, plan, results)
    _event(project, new_id, "run_resumed", f"Resumed {old_id}; reused {len(reused)} accepted task results.")
    return {**output, "previous_run_id": old_id, "reused": sorted(reused), "pending": invalidated}


def run_status(project: Path, run_id: str) -> dict:
    project = _project(project)
    directory = run_path(project, run_id)
    if not directory.is_dir():
        raise ValueError(f"Run does not exist: {run_id}")
    with locked(directory / ".state.lock"):
        directory, plan, registry = _load(project, run_id)
        return {**_ready(project, directory, plan, registry), "plan": plan, "agents": registry["agents"]}
