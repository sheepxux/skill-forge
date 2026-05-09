#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SKILL_FORGE = REPO / "skill-forge"

CASE_RUNTIME_BUDGET_MS = 5000
TOTAL_RUNTIME_BUDGET_MS = 30000
MIN_VALIDATION_SCORE = 85
MIN_EVAL_SCORE = 100


BENCHMARK_CASES = [
    {
        "profile": "academic",
        "skill_name": "bench-citation-coach",
        "goal": "Help Study Agent produce citation-safe academic scaffolds without invented references.",
        "triggers": "APA format, MLA format, source metadata, reference list, citation risk",
        "expected": ["references/citation-style-checklist.md", "Never invent", "Source metadata"],
    },
    {
        "profile": "product",
        "skill_name": "bench-product-spec",
        "goal": "Help Product Agent turn product ideas into scoped MVP specs and Dev Agent handoffs.",
        "triggers": "PRD, MVP scope, user story, acceptance criteria, Dev handoff",
        "expected": ["references/prd-shape.md", "Non-goals", "Acceptance criteria"],
    },
    {
        "profile": "integration",
        "skill_name": "bench-integration-planner",
        "goal": "Help agents plan safe external integrations with credentials, health checks, and failure handling.",
        "triggers": "API key, OAuth, webhook, Telegram bot, health check",
        "expected": ["references/integration-checklist.md", "Never print real secrets", "Health check"],
    },
    {
        "profile": "script",
        "skill_name": "bench-script-packager",
        "goal": "Help agents package repeated file operations into deterministic CLI scripts.",
        "triggers": "CLI, batch process, parse files, validate input, dry-run",
        "expected": ["references/script-contract.md", "scripts/run.py", "exit codes"],
    },
    {
        "profile": "workflow",
        "skill_name": "bench-workflow-handoff",
        "goal": "Help agents standardize repeated handoff workflows with explicit quality gates.",
        "triggers": "handoff checklist, repeatable process, quality gate, decision rules, expected output",
        "expected": ["references/workflow-template.md", "Resource Loading", "Execution Mode"],
    },
]


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    if check and completed.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(command)
            + f"\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def run_json(command: list[str], check: bool = True) -> dict:
    completed = run(command, check=check)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "invalid json from: "
            + " ".join(command)
            + f"\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        ) from exc


def benchmark_case(case: dict, output_root: Path) -> dict:
    started = time.perf_counter()
    run(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "generate_skill_scaffold.py"),
            "--skill-name",
            case["skill_name"],
            "--output",
            str(output_root),
            "--goal",
            case["goal"],
            "--triggers",
            case["triggers"],
            "--template",
            case["profile"],
        ]
    )
    candidate = output_root / case["skill_name"]
    content = (candidate / "SKILL.md").read_text(encoding="utf-8")
    validation = run_json(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
            str(candidate),
            "--json",
        ]
    )
    evaluation = run_json(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "evaluate_skill_candidate.py"),
            str(candidate),
            "--profile",
            case["profile"],
            "--json",
        ]
    )
    runtime_ms = round((time.perf_counter() - started) * 1000)
    failures = []
    if not validation.get("valid"):
        failures.append("validation invalid")
    if validation.get("score", 0) < MIN_VALIDATION_SCORE:
        failures.append(f"validation score below {MIN_VALIDATION_SCORE}: {validation.get('score')}")
    if not evaluation.get("passed"):
        failures.append("hidden evaluation failed")
    if evaluation.get("score", 0) < MIN_EVAL_SCORE:
        failures.append(f"evaluation score below {MIN_EVAL_SCORE}: {evaluation.get('score')}")
    if len(content.splitlines()) > 500:
        failures.append("SKILL.md exceeded 500 lines")
    if runtime_ms > CASE_RUNTIME_BUDGET_MS:
        failures.append(f"case runtime exceeded {CASE_RUNTIME_BUDGET_MS}ms: {runtime_ms}ms")
    for fragment in case["expected"]:
        if fragment not in content:
            failures.append(f"missing expected fragment: {fragment}")
    return {
        "profile": case["profile"],
        "skill_name": case["skill_name"],
        "runtime_ms": runtime_ms,
        "line_count": len(content.splitlines()),
        "validation_score": validation.get("score"),
        "validation_grade": validation.get("grade"),
        "evaluation_score": evaluation.get("score"),
        "passed": not failures,
        "failures": failures,
    }


def benchmark_forge_pipeline(output_root: Path, target_root: Path) -> dict:
    started = time.perf_counter()
    result = run_json(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "forge_pipeline.py"),
            "--source",
            str(SKILL_FORGE / "examples" / "sample-feature-requests.md"),
            "--source",
            str(SKILL_FORGE / "examples" / "sample-errors.md"),
            "--output",
            str(output_root),
            "--target-root",
            str(target_root),
            "--eval",
            "hidden",
            "--install",
            "plan",
            "--agent-name",
            "StudyAgent",
            "--json",
        ]
    )
    runtime_ms = round((time.perf_counter() - started) * 1000)
    failures = []
    if result.get("install_status") != "planned":
        failures.append(f"install status was not planned: {result.get('install_status')}")
    if not result.get("validation", {}).get("valid"):
        failures.append("forge pipeline candidate did not validate")
    if result.get("validation", {}).get("score", 0) < MIN_VALIDATION_SCORE:
        failures.append("forge pipeline validation score below threshold")
    if runtime_ms > TOTAL_RUNTIME_BUDGET_MS:
        failures.append(f"forge pipeline runtime exceeded {TOTAL_RUNTIME_BUDGET_MS}ms: {runtime_ms}ms")
    return {
        "name": "forge_pipeline_plan",
        "runtime_ms": runtime_ms,
        "validation_score": result.get("validation", {}).get("score"),
        "install_status": result.get("install_status"),
        "passed": not failures,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Skill Forge benchmark cases.")
    parser.add_argument("--json", action="store_true", help="Print JSON benchmark results.")
    args = parser.parse_args()

    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as generated, tempfile.TemporaryDirectory() as target:
        output_root = Path(generated)
        target_root = Path(target)
        cases = [benchmark_case(case, output_root) for case in BENCHMARK_CASES]
        pipeline = benchmark_forge_pipeline(output_root / "pipeline", target_root)
    total_runtime_ms = round((time.perf_counter() - started) * 1000)
    failures = [
        f"{case['profile']}: {failure}"
        for case in cases
        for failure in case["failures"]
    ]
    failures.extend(f"forge_pipeline_plan: {failure}" for failure in pipeline["failures"])
    if total_runtime_ms > TOTAL_RUNTIME_BUDGET_MS:
        failures.append(f"total runtime exceeded {TOTAL_RUNTIME_BUDGET_MS}ms: {total_runtime_ms}ms")
    payload = {
        "status": "ok" if not failures else "failed",
        "total_runtime_ms": total_runtime_ms,
        "case_runtime_budget_ms": CASE_RUNTIME_BUDGET_MS,
        "total_runtime_budget_ms": TOTAL_RUNTIME_BUDGET_MS,
        "min_validation_score": MIN_VALIDATION_SCORE,
        "min_eval_score": MIN_EVAL_SCORE,
        "cases": cases,
        "pipeline": pipeline,
        "failures": failures,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"benchmark {payload['status']} total_runtime_ms={total_runtime_ms}")
        for case in cases:
            print(
                f"{'ok' if case['passed'] else 'failed'} {case['profile']} "
                f"validation={case['validation_score']} eval={case['evaluation_score']} "
                f"runtime_ms={case['runtime_ms']}"
            )
        print(
            f"{'ok' if pipeline['passed'] else 'failed'} {pipeline['name']} "
            f"validation={pipeline['validation_score']} runtime_ms={pipeline['runtime_ms']}"
        )
        for failure in failures:
            print(f"failure: {failure}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
