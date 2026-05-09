#!/usr/bin/env python3
import hashlib
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
sys.path.insert(0, str(SKILL_FORGE / "scripts"))
from lib.approval import issue_token


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
    skill_dirs = [SKILL_FORGE]
    if SOMNIA.exists():
        skill_dirs.append(SOMNIA)
    for skill_dir in skill_dirs:
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


def check_console_doctor() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
    env["TELEGRAM_BOT_TOKEN"] = "release-check-token"
    env["TELEGRAM_CHAT_ID"] = "123456"
    with tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "skill_forge.py"),
                "doctor",
                "--target-root",
                target,
                "--no-default-env-files",
                "--json",
            ],
            env=env,
        )
        assert_true(result["version"] == "1.1.0", "console doctor reported the wrong version")
        names = {item["name"]: item for item in result["checks"]}
        assert_true(names["skill-package"]["status"] == "ok", "console doctor did not find the skill package")
        assert_true(names["approval-secret"]["status"] == "ok", "console doctor did not find approval secret")
        assert_true("explicit env" in names["approval-secret"]["detail"], "doctor should report explicit approval secret source")


def check_console_demo() -> None:
    with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "skill_forge.py"),
                "demo",
                "--output",
                output,
                "--target-root",
                target,
                "--json",
            ]
        )
        assert_true(result["status"] == "ok", "console demo command failed")
        assert_true(result.get("install_status") == "planned", "console demo did not stay plan-only")
        assert_true(result.get("validation", {}).get("valid"), "console demo candidate did not validate")


def check_install_gate() -> None:
    with tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                str(SKILL_FORGE),
                "--target-root",
                target,
                "--apply",
                "--json",
            ],
            check=False,
        )
        assert_true(result["status"] == "blocked", "direct apply without token was not blocked")
        assert_true("token" in result.get("reason", ""), "block reason should mention approval token")
        assert_true(not (Path(target) / "skill-forge").exists(), "direct apply created target")


def check_install_rejects_forged_token() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
    with tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                str(SKILL_FORGE),
                "--target-root",
                target,
                "--apply",
                "--approval-token",
                "deadbeef.cafef00d",
                "--json",
            ],
            check=False,
            env=env,
        )
        assert_true(result["status"] == "blocked", "forged token was not blocked")
        assert_true(not (Path(target) / "skill-forge").exists(), "forged token created target")


def check_telegram_dry_run_blocked() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
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
            ],
            env=env,
        )
        assert_true(
            result["install_status"] == "dry-run-blocked",
            f"dry-run approval was not blocked: {result['install_status']}",
        )
        assert_true(
            not (Path(target) / "citation-helper").exists(),
            "dry-run approval still created the install target",
        )
        approval = result.get("approval") or {}
        claims = approval.get("approval_claims") or {}
        assert_true(claims.get("mode") == "dry-run", "dry-run token should declare mode=dry-run")


def check_dry_run_without_secret_has_no_token() -> None:
    env = os.environ.copy()
    env.pop("SKILL_FORGE_APPROVAL_SECRET", None)
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
            "--source-dir",
            str(SKILL_FORGE),
            "--bot-token-env",
            "SKILL_FORGE_TEST_NO_TOKEN",
            "--chat-id-env",
            "SKILL_FORGE_TEST_NO_CHAT",
            "--no-default-env-files",
            "--dry-run",
            "approve",
            "--json",
        ],
        env=env,
    )
    assert_true(result["approved"], "dry-run approve should still approve")
    assert_true(result.get("approval_token") is None, "dry-run without a secret should not mint a token")
    assert_true(result.get("token_error") == "no-secret-available", "missing token error was not surfaced")


def check_pipeline_blocks_when_token_missing() -> None:
    env = os.environ.copy()
    for key in [
        "SKILL_FORGE_APPROVAL_SECRET",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "OPENCLAW_TELEGRAM_BOT_TOKEN",
        "OPENCLAW_TELEGRAM_CHAT_ID",
    ]:
        env.pop(key, None)
    with tempfile.TemporaryDirectory() as fake_home, \
         tempfile.TemporaryDirectory() as output, \
         tempfile.TemporaryDirectory() as target:
        env["HOME"] = fake_home
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
            ],
            env=env,
        )
        assert_true(
            result["install_status"] == "approval-token-missing",
            f"missing token did not block install: {result.get('install_status')}",
        )
        assert_true(
            not any(Path(target).iterdir()),
            "approval-token-missing path still mutated the target root",
        )
        approval = result.get("approval") or {}
        assert_true(approval.get("approved") is True, "approval should still report approved=true")
        assert_true(approval.get("approval_token") is None, "approval_token should be absent when no secret")
        assert_true(approval.get("token_error") == "no-secret-available", "token_error must be surfaced")


def _scaffold_candidate(parent: Path, skill_name: str = "release-check-skill") -> Path:
    run(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "generate_skill_scaffold.py"),
            "--skill-name",
            skill_name,
            "--output",
            str(parent),
            "--goal",
            f"{skill_name} validates the install gate end to end.",
            "--triggers",
            "release-check, gate audit, signed token",
            "--template",
            "workflow",
        ]
    )
    return parent / skill_name


def check_scaffold_quality_design() -> None:
    with tempfile.TemporaryDirectory() as gen:
        candidate = _scaffold_candidate(Path(gen), "quality-engine-skill")
        content = (candidate / "SKILL.md").read_text(encoding="utf-8")
        assert_true("## Core Workflow" in content, "generated skill should use a lean core workflow section")
        assert_true("## Resource Loading" in content, "generated skill should explain progressive resource loading")
        assert_true("## Execution Mode" in content, "generated skill should declare degree-of-freedom guidance")
        assert_true("references/workflow-template.md" in content, "generated skill should link bundled references")
        assert_true(not (candidate / "README.md").exists(), "generated skill should not include extraneous README docs")

        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(candidate),
                "--json",
            ]
        )
        assert_true(result["valid"], "quality-engine scaffold should validate")
        assert_true(result["score"] >= 85, "quality-engine scaffold should reach milestone quality")

        (candidate / "README.md").write_text("# Not for agent context\n", encoding="utf-8")
        invalid = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(candidate),
                "--json",
            ],
            check=False,
        )
        assert_true(not invalid["valid"], "validator should reject extraneous user-facing docs")
        assert_true(any("bloat agent context" in error for error in invalid["errors"]),
                    "extraneous-doc error should explain context bloat")


def check_profile_golden_scaffolds() -> None:
    cases = [
        (
            "academic",
            "citation-coach",
            "Help Study Agent produce citation-safe academic plans without inventing references.",
            "APA format, MLA format, source metadata, reference list",
            ["references/citation-style-checklist.md", "Never invent"],
        ),
        (
            "product",
            "product-spec-writer",
            "Help Product Agent turn ideas into MVP specs and Dev Agent handoffs.",
            "PRD, MVP scope, acceptance criteria, Dev handoff",
            ["references/prd-shape.md", "Non-goals"],
        ),
        (
            "integration",
            "telegram-notion-connector",
            "Help agents plan safe Telegram and Notion integrations with health checks.",
            "Telegram bot, Notion database, API key, health check",
            ["references/integration-checklist.md", "Never print real secrets"],
        ),
        (
            "script",
            "batch-report-cli",
            "Help agents package repeated reporting work into deterministic CLI scripts.",
            "CLI, batch process, generate report, validate input",
            ["references/script-contract.md", "scripts/run.py"],
        ),
        (
            "workflow",
            "handoff-checklist",
            "Help agents standardize repeated handoff checklists and quality gates.",
            "handoff checklist, repeatable process, quality gate",
            ["references/workflow-template.md", "Execution Mode"],
        ),
    ]
    with tempfile.TemporaryDirectory() as gen:
        root = Path(gen)
        for template, skill_name, goal, triggers, expected_fragments in cases:
            run(
                [
                    sys.executable,
                    str(SKILL_FORGE / "scripts" / "generate_skill_scaffold.py"),
                    "--skill-name",
                    skill_name,
                    "--output",
                    str(root),
                    "--goal",
                    goal,
                    "--triggers",
                    triggers,
                    "--template",
                    template,
                ]
            )
            candidate = root / skill_name
            content = (candidate / "SKILL.md").read_text(encoding="utf-8")
            assert_true(len(content.splitlines()) <= 500, f"{template} scaffold SKILL.md is too long")
            assert_true("## Resource Loading" in content, f"{template} scaffold missing Resource Loading")
            assert_true("## Execution Mode" in content, f"{template} scaffold missing Execution Mode")
            for fragment in expected_fragments:
                assert_true(fragment in content, f"{template} scaffold missing expected fragment: {fragment}")
            result = run_json(
                [
                    sys.executable,
                    str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                    str(candidate),
                    "--json",
                ]
            )
            assert_true(result["valid"], f"{template} golden scaffold did not validate")
            assert_true(result["score"] >= 85, f"{template} golden scaffold below milestone threshold")


def _issue_token(env: dict, skill: str, source: Path, target: str, ttl: int = 600) -> str:
    payload = run_json(
        [
            sys.executable,
            str(SKILL_FORGE / "scripts" / "install" / "telegram_approval.py"),
            "--skill",
            skill,
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
            target,
            "--method",
            "symlink",
            "--source-dir",
            str(source),
            "--token-ttl",
            str(ttl),
            "--bot-token-env",
            "SKILL_FORGE_TEST_NO_TOKEN",
            "--chat-id-env",
            "SKILL_FORGE_TEST_NO_CHAT",
            "--no-default-env-files",
            "--dry-run",
            "approve",
            "--json",
        ],
        env=env,
    )
    assert_true(payload.get("approved") is True, "approval helper did not approve")
    token = payload.get("approval_token")
    assert_true(bool(token), "approval helper did not mint a token")
    return token


def check_install_with_valid_token_succeeds() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
    with tempfile.TemporaryDirectory() as gen, tempfile.TemporaryDirectory() as target:
        candidate = _scaffold_candidate(Path(gen))
        target_path = str(Path(target) / candidate.name)
        token = _issue_token(env, candidate.name, candidate, target_path)
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                str(candidate),
                "--target-root",
                target,
                "--method",
                "symlink",
                "--apply",
                "--approval-token",
                token,
                "--allow-dry-run-install",
                "--json",
            ],
            env=env,
        )
        assert_true(result.get("installed") is True, f"valid token did not install: {result}")
        assert_true(result.get("approved_by") == "dry-run", "dry-run audit field should be dry-run")
        installed = Path(target_path)
        assert_true(installed.is_symlink() or installed.exists(), "install target was not created")


def check_install_rejects_tampered_source() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
    with tempfile.TemporaryDirectory() as gen, tempfile.TemporaryDirectory() as target:
        candidate = _scaffold_candidate(Path(gen))
        target_path = str(Path(target) / candidate.name)
        token = _issue_token(env, candidate.name, candidate, target_path)
        skill_md = candidate / "SKILL.md"
        skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\n<!-- tamper -->\n", encoding="utf-8")
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                str(candidate),
                "--target-root",
                target,
                "--method",
                "symlink",
                "--apply",
                "--approval-token",
                token,
                "--allow-dry-run-install",
                "--json",
            ],
            check=False,
            env=env,
        )
        assert_true(result.get("status") == "blocked", f"tampered source was not blocked: {result}")
        reason = result.get("reason", "")
        assert_true(
            "source_hash" in reason or "claim-mismatch" in reason,
            f"block reason should mention source_hash or claim-mismatch: {reason}",
        )
        assert_true(not Path(target_path).exists() and not Path(target_path).is_symlink(),
                    "tampered apply still created the install target")


def check_approval_rejects_missing_source() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
    with tempfile.TemporaryDirectory() as gen, tempfile.TemporaryDirectory() as target:
        missing_source = Path(gen) / "missing-skill"
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "telegram_approval.py"),
                "--skill",
                "missing-skill",
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
                str(Path(target) / "missing-skill"),
                "--method",
                "symlink",
                "--source-dir",
                str(missing_source),
                "--bot-token-env",
                "SKILL_FORGE_TEST_NO_TOKEN",
                "--chat-id-env",
                "SKILL_FORGE_TEST_NO_CHAT",
                "--no-default-env-files",
                "--dry-run",
                "approve",
                "--json",
            ],
            env=env,
        )
        assert_true(result.get("approved") is True, "dry-run approval should still record the decision")
        assert_true(result.get("approval_token") is None, "missing source should not receive a token")
        assert_true(
            str(result.get("token_error", "")).startswith("invalid-source-dir:"),
            "missing source should surface invalid-source-dir token_error",
        )
        assert_true(
            not (Path(target) / "missing-skill").exists()
            and not (Path(target) / "missing-skill").is_symlink(),
            "missing source approval mutated target",
        )


def check_install_rejects_missing_source_even_with_token() -> None:
    env = os.environ.copy()
    env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"
    with tempfile.TemporaryDirectory() as gen, tempfile.TemporaryDirectory() as target:
        missing_source = (Path(gen) / "missing-skill").resolve()
        target_path = Path(target) / "missing-skill"
        secret = hashlib.sha256(b"release-check-secret").digest()
        token = issue_token(
            {
                "request_id": "release-check-missing-source",
                "skill": "missing-skill",
                "profile": "workflow",
                "source_dir": str(missing_source),
                "source_hash": "missing",
                "target": str(target_path),
                "method": "symlink",
                "mode": "dry-run",
            },
            secret,
            ttl_seconds=600,
        )
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                str(missing_source),
                "--target-root",
                target,
                "--method",
                "symlink",
                "--apply",
                "--approval-token",
                token,
                "--allow-dry-run-install",
                "--json",
            ],
            check=False,
            env=env,
        )
        assert_true(result.get("status") == "blocked", f"missing source was not blocked: {result}")
        assert_true("candidate skill directory" in result.get("reason", ""), "block reason should mention source dir")
        assert_true(not target_path.exists() and not target_path.is_symlink(), "missing source created target")


def check_uninstall_apply_requires_token() -> None:
    with tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "install" / "propose_skill_install.py"),
                "any-skill",
                "--target-root",
                target,
                "--uninstall",
                "--apply",
                "--json",
            ],
            check=False,
        )
        assert_true(result.get("status") == "blocked", "uninstall --apply without token was not blocked")
        assert_true("token" in result.get("reason", ""), "uninstall block reason should mention approval token")


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


def check_update_path_guard() -> None:
    with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as target:
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "evolve" / "propose_skill_update.py"),
                "--skill",
                "../outside",
                "--output",
                output,
                "--target-root",
                target,
                "--json",
            ],
            check=False,
        )
        assert_true(result["status"] == "invalid-skill-name", "unsafe skill name was not rejected")
        assert_true(not (Path(output).parent / "outside").exists(), "unsafe candidate path was created")


def check_somnia_review() -> None:
    if not SOMNIA.exists():
        print("skip somnia-review (sibling ../somnia not found)")
        return
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
        ("scaffold-quality-design", check_scaffold_quality_design),
        ("profile-golden-scaffolds", check_profile_golden_scaffolds),
        ("console-doctor", check_console_doctor),
        ("console-demo", check_console_demo),
        ("install-gate", check_install_gate),
        ("install-forged-token", check_install_rejects_forged_token),
        ("install-with-valid-token", check_install_with_valid_token_succeeds),
        ("install-rejects-tampered-source", check_install_rejects_tampered_source),
        ("approval-rejects-missing-source", check_approval_rejects_missing_source),
        ("install-rejects-missing-source", check_install_rejects_missing_source_even_with_token),
        ("uninstall-apply-requires-token", check_uninstall_apply_requires_token),
        ("telegram-dry-run-blocked", check_telegram_dry_run_blocked),
        ("dry-run-without-secret", check_dry_run_without_secret_has_no_token),
        ("pipeline-blocks-when-token-missing", check_pipeline_blocks_when_token_missing),
        ("telegram-missing-config", check_telegram_missing_config),
        ("update-path-guard", check_update_path_guard),
        ("somnia-review", check_somnia_review),
    ]
    for name, check in checks:
        check()
        print(f"ok {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
