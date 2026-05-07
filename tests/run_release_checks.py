#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


REPO = Path(__file__).resolve().parents[1]
SKILL_FORGE = REPO / "skill-forge"
SOMNIA = REPO.parent / "somnia"


def run(command: list[str], check: bool = True, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True, env=env)
    if check and completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(command)}")
    return completed


def run_json(command: list[str], check: bool = True, env: Optional[dict] = None) -> dict:
    completed = run(command, check=check, env=env)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(f"invalid json from {' '.join(command)}: {exc}") from exc


def py_files() -> list[str]:
    roots = [SKILL_FORGE / "scripts", SOMNIA / "scripts", REPO / "tests"]
    return [str(path) for root in roots for path in sorted(root.rglob("*.py"))]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def check_compile() -> None:
    run([sys.executable, "-m", "py_compile", *py_files()])


def check_secret_scan() -> None:
    result = run_json([sys.executable, str(SKILL_FORGE / "scripts" / "security" / "scan_secrets.py"), "--json"])
    assert_true(result["status"] == "ok", "secret scan failed")


def check_skill_validation() -> None:
    for skill_dir in [SKILL_FORGE, SOMNIA]:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(skill_dir),
                "--json",
            ]
        )
        assert_true(result["valid"], f"{skill_dir.name} validation failed")
        assert_true(result["score"] >= 85, f"{skill_dir.name} score below milestone threshold")


def check_forge_plan() -> None:
    with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "forge_pipeline.py"),
                "--source",
                str(SKILL_FORGE / "examples" / "sample-feature-requests.md"),
                "--source",
                str(SKILL_FORGE / "examples" / "sample-errors.md"),
                "--output",
                output,
                "--target-root",
                target,
                "--eval",
                "hidden",
                "--install",
                "plan",
                "--agent-name",
                "StudyAgent",
                "--json",
            ]
        )
        assert_true(result["install_status"] == "planned", "forge plan did not stay planned")
        assert_true(result["validation"]["valid"], "forge candidate did not validate")


def check_install_gate() -> None:
    with tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                str(SOMNIA),
                "--target-root",
                target,
                "--apply",
                "--json",
            ],
            check=False,
        )
        assert_true(result["status"] == "blocked", "direct apply was not blocked")
        assert_true(not (Path(target) / "somnia").exists(), "direct apply created target")


def check_telegram_dry_run_install() -> None:
    with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "forge_pipeline.py"),
                "--source",
                str(SKILL_FORGE / "examples" / "sample-feature-requests.md"),
                "--source",
                str(SKILL_FORGE / "examples" / "sample-errors.md"),
                "--output",
                output,
                "--target-root",
                target,
                "--eval",
                "hidden",
                "--install",
                "telegram",
                "--telegram-dry-run",
                "approve",
                "--agent-name",
                "StudyAgent",
                "--json",
            ]
        )
        assert_true(result["install_status"] == "installed", "telegram dry-run did not install")
        assert_true(result["install_plan"].get("approved_by") == "telegram", "install audit missing telegram approval")


def check_telegram_missing_config() -> None:
    env = os.environ.copy()
    for key in [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "OPENCLAW_TELEGRAM_BOT_TOKEN",
        "OPENCLAW_TELEGRAM_CHAT_ID",
    ]:
        env.pop(key, None)
    result = run_json(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "install" / "telegram_approval.py"),
            "--skill",
            "example",
            "--profile",
            "workflow",
            "--validation-score",
            "100",
            "--validation-grade",
            "milestone",
            "--evaluation-score",
            "100",
            "--evaluation-passed",
            "--target",
            "/tmp/example",
            "--method",
            "symlink",
            "--bot-token-env",
            "SKILL_FORGE_TEST_NO_TOKEN",
            "--chat-id-env",
            "SKILL_FORGE_TEST_NO_CHAT",
            "--no-default-env-files",
            "--json",
        ],
        check=False,
        env=env,
    )
    assert_true(result["status"] == "missing-config", "missing Telegram config was not detected")


def check_somnia_review() -> None:
    with tempfile.TemporaryDirectory() as report_root, tempfile.TemporaryDirectory() as update_root:
        result = run_json(
            [
                sys.executable,
                str(SOMNIA / "scripts" / "nightly_skill_review.py"),
                "--target-root",
                str(Path.home() / ".openclaw" / "workspace" / "skills"),
                "--report-root",
                report_root,
                "--update-output",
                update_root,
                "--scope",
                "managed",
                "--replay",
                "off",
                "--json",
            ]
        )
        assert_true(result["status"] == "ok", "Somnia review failed")


def main() -> int:
    checks = [
        ("compile", check_compile),
        ("secret-scan", check_secret_scan),
        ("skill-validation", check_skill_validation),
        ("forge-plan", check_forge_plan),
        ("install-gate", check_install_gate),
        ("telegram-dry-run-install", check_telegram_dry_run_install),
        ("telegram-missing-config", check_telegram_missing_config),
        ("somnia-review", check_somnia_review),
    ]
    for name, check in checks:
        check()
        print(f"ok {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
