#!/usr/bin/env python3
import hashlib
import json
import os
import re
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
        expected_version = (SKILL_FORGE / "VERSION").read_text(encoding="utf-8").strip()
        assert_true(
            result["version"] == expected_version,
            f"console doctor reported version {result['version']!r}, expected {expected_version!r}",
        )
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


def check_frontmatter_metadata_allowlist() -> None:
    with tempfile.TemporaryDirectory() as gen:
        candidate = _scaffold_candidate(Path(gen), "frontmatter-allowlist-skill")
        skill_md = candidate / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        text = text.replace(
            "---\nname:",
            "---\nversion: 1.0.0\nlicense: MIT\nauthor: Test Author\nname:",
            1,
        )
        skill_md.write_text(text, encoding="utf-8")
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(candidate),
                "--json",
            ]
        )
        assert_true(result["valid"], "skill with allowed metadata frontmatter should validate")
        assert_true(result["score"] == 100, f"version/license/author should not cap score, got {result['score']}")
        assert_true(
            not any("frontmatter should only contain" in w for w in result.get("warnings", [])),
            "allowed frontmatter keys should not warn",
        )

        # Unknown key should still cap.
        text = skill_md.read_text(encoding="utf-8")
        text = text.replace("---\nversion:", "---\nmysterious_key: oops\nversion:", 1)
        skill_md.write_text(text, encoding="utf-8")
        capped = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(candidate),
                "--json",
            ]
        )
        assert_true(capped["score"] <= 89, "unknown frontmatter keys should still cap below milestone")


def check_workflow_section_required() -> None:
    with tempfile.TemporaryDirectory() as gen:
        candidate = _scaffold_candidate(Path(gen), "workflow-required-skill")
        skill_md = candidate / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        # Strip the entire Core Workflow section.
        stripped = re.sub(
            r"(?ms)^## Core Workflow\s*\n.*?(?=^## )",
            "",
            text,
            count=1,
        )
        assert_true(stripped != text, "fixture must remove the Core Workflow section")
        skill_md.write_text(stripped, encoding="utf-8")
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(candidate),
                "--json",
            ]
        )
        assert_true(result["score"] <= 89, f"missing workflow section should cap at 89, got {result['score']}")
        assert_true(
            any("Core Workflow or Default Workflow" in w for w in result.get("warnings", [])),
            "missing-workflow warning should fire",
        )


def check_numbered_steps_must_live_in_workflow() -> None:
    with tempfile.TemporaryDirectory() as gen:
        candidate = _scaffold_candidate(Path(gen), "numbered-steps-scope-skill")
        skill_md = candidate / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        # Replace the numbered Core Workflow with a bullet list, then add 4 numbered
        # items inside Quality Gates so the *document* still has 4+ numbered steps.
        text = re.sub(
            r"(?ms)(^## Core Workflow\s*\n)(.*?)(?=^## )",
            lambda m: m.group(1) + "- step one as a bullet\n- step two as a bullet\n- step three as a bullet\n\n",
            text,
            count=1,
        )
        text = text.replace(
            "## Quality Gates\n",
            "## Quality Gates\n\n1. first numbered gate\n2. second numbered gate\n3. third numbered gate\n4. fourth numbered gate\n",
            1,
        )
        skill_md.write_text(text, encoding="utf-8")
        result = run_json(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                str(candidate),
                "--json",
            ]
        )
        assert_true(
            any("workflow section should include at least 4 numbered steps" in w for w in result.get("warnings", [])),
            "numbered-step bonus must require numbered steps inside the workflow section",
        )


def check_scaffold_description_anchored_to_user_triggers() -> None:
    with tempfile.TemporaryDirectory() as gen:
        run(
            [
                sys.executable,
                str(SKILL_FORGE / "scripts" / "generate_skill_scaffold.py"),
                "--skill-name",
                "anchored-scaffold-skill",
                "--output",
                gen,
                "--goal",
                "Help an agent run a niche, well-specified probe.",
                "--triggers",
                "probe payload, parse signed envelope, dump signing keyset, replay last token",
                "--template",
                "script",
            ]
        )
        text = (Path(gen) / "anchored-scaffold-skill" / "SKILL.md").read_text(encoding="utf-8")
        # Description (frontmatter) must NOT contain profile-default trigger flooding.
        match = re.search(r"^description: (.*)$", text, re.MULTILINE)
        assert_true(match is not None, "scaffold should expose a frontmatter description")
        description = match.group(1)
        assert_true("probe payload" in description, "user-supplied triggers must reach the description")
        for default_only in ("automation script", "convert files", "export data"):
            assert_true(
                default_only not in description,
                f"profile-default trigger {default_only!r} should not flood a well-specified description",
            )


def _seed_installed_skill(target_root: Path, name: str, profile_label: str,
                          triggers: list, body_extra: str = "") -> None:
    """Drop a minimal SKILL.md into target_root/<name>/ and register it in the manifest."""
    skill_dir = target_root / name
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)
    triggers_block = "\n".join(f"- `{t}`" for t in triggers)
    description_triggers = ", ".join(triggers[:6]) or name
    skill_md = f"""---
name: {name}
description: Help an agent with {profile_label} tasks. Use when the user asks for {description_triggers}, or when an agent needs a reusable {profile_label} skill with bundled references, quality gates, and clear output contracts.
---

# {name.replace('-', ' ').title()}

## Trigger Cues

Use this skill when the user mentions:

{triggers_block}

## Core Workflow

1. Step one.
2. Step two.
3. Step three.
4. Step four.

## Resource Loading

- Read references/notes.md when applicable.

## Execution Mode

medium freedom

## Output Contract

- summary
- structured artifact

## Quality Gates

- Be deterministic.
- Be honest.

{body_extra}

## Resources

References:
- references/notes.md
"""
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    (skill_dir / "references" / "notes.md").write_text("notes\n", encoding="utf-8")
    manifest_path = target_root / ".skill-forge-installs.json"
    manifest = {"installs": {}}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {"installs": {}}
    manifest.setdefault("installs", {})[name] = {
        "skill": name,
        "source": str(skill_dir),
        "target": str(skill_dir),
        "method": "symlink",
        "active": True,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")


def _decide(target_root: Path, name: str, triggers: str, template: str,
            reason: str = "", evolve_threshold: float = 0.45,
            ambiguous_margin: float = 0.1) -> dict:
    return run_json([
        sys.executable,
        str(SKILL_FORGE / "scripts" / "decide_skill_action.py"),
        "--target-root", str(target_root),
        "--skill-name", name,
        "--triggers", triggers,
        "--template", template,
        "--reason", reason,
        "--evolve-threshold", str(evolve_threshold),
        "--ambiguous-margin", str(ambiguous_margin),
        "--json",
    ])


def check_decide_routes_to_evolve_when_similar() -> None:
    with tempfile.TemporaryDirectory() as root_str:
        root = Path(root_str)
        triggers = ["citation review", "APA format", "MLA format", "source metadata",
                    "reference list", "bibliography"]
        _seed_installed_skill(root, "citation-helper", "academic citation", triggers,
                              body_extra="Cover APA, MLA, Chicago, and bibliography metadata. Never invent references.")
        result = _decide(
            root,
            name="literature-citation-helper",
            triggers="APA format, MLA format, source metadata, reference list, bibliography",
            template="academic",
            reason="user keeps asking for APA literature reviews with source metadata",
        )
        assert_true(result["decision"] == "evolve",
                    f"similar academic opportunity should evolve, got {result['decision']} ({result['fitness']})")
        assert_true(result["target_skill"] == "citation-helper",
                    f"target_skill should be citation-helper, got {result['target_skill']}")
        assert_true(result["fitness"] >= 0.45,
                    f"fitness should clear the threshold, got {result['fitness']}")


def check_decide_routes_to_forge_when_novel() -> None:
    with tempfile.TemporaryDirectory() as root_str:
        root = Path(root_str)
        _seed_installed_skill(root, "citation-helper", "academic citation",
                              ["APA format", "MLA format", "source metadata"])
        result = _decide(
            root,
            name="vector-db-prober",
            triggers="probe vector store, dump schema, sample rows, detect index, infer embedding dim",
            template="script",
            reason="user wants to introspect unknown vector databases via CLI",
        )
        assert_true(result["decision"] == "forge",
                    f"novel script opportunity should forge, got {result['decision']}")
        assert_true(result["target_skill"] is None, "forge decision should have no target_skill")


def check_decide_respects_profile_mismatch() -> None:
    with tempfile.TemporaryDirectory() as root_str:
        root = Path(root_str)
        _seed_installed_skill(root, "citation-helper", "academic citation",
                              ["APA format", "MLA format", "Chicago citation", "bibliography"])
        # Topic + name overlap with the academic skill, BUT script profile.
        result = _decide(
            root,
            name="citation-cli-tool",
            triggers="CLI, batch process, parse files, validate input, exit code",
            template="script",
            reason="wrap citation work in a deterministic CLI",
        )
        assert_true(result["decision"] == "forge",
                    f"profile-mismatched opportunity must NOT evolve an academic skill, got {result['decision']}")
        for alt in result.get("alternatives", []):
            if alt["skill"] == "citation-helper":
                assert_true(alt["fitness"] == 0.0,
                            f"profile-mismatched candidate must score 0, got {alt['fitness']}")
                assert_true(not alt["reasoning"]["profile_match"],
                            "profile_match should be false in reasoning")


def check_decide_flags_ambiguous_when_tied() -> None:
    with tempfile.TemporaryDirectory() as root_str:
        root = Path(root_str)
        # Two academic skills with IDENTICAL triggers — any matching opportunity ties.
        identical_triggers = ["APA format", "MLA format", "source metadata",
                              "reference list", "bibliography"]
        _seed_installed_skill(root, "citation-helper", "academic citation", identical_triggers)
        _seed_installed_skill(root, "research-helper", "academic citation", identical_triggers)
        result = _decide(
            root,
            name="literature-citation-helper",  # name overlap with neither so no exact-name short-circuit
            triggers="APA format, MLA format, source metadata, reference list, bibliography",
            template="academic",
            reason="academic write-up with citations",
        )
        assert_true(result["decision"] == "ambiguous",
                    f"two equally-fit installed skills must produce ambiguous, got {result['decision']}")
        alts = result.get("alternatives", [])
        assert_true(len(alts) >= 2, "ambiguous decision should surface both top candidates")
        assert_true(abs(alts[0]["fitness"] - alts[1]["fitness"]) < result["ambiguous_margin"],
                    "top two fitnesses should be within ambiguous margin")


def check_forge_pipeline_prefer_evolve_routes_through_decide() -> None:
    """End-to-end: when --prefer-evolve sees an installed skill matching the
    detected opportunity, the pipeline routes to evolve and writes a synthetic
    forge-routing feedback record (instead of generating a brand-new skill)."""
    with tempfile.TemporaryDirectory() as root_str, \
         tempfile.TemporaryDirectory() as out_str, \
         tempfile.TemporaryDirectory() as feedback_dir, \
         tempfile.TemporaryDirectory() as updates_dir:
        root = Path(root_str)
        # Pre-seed an installed citation-helper that the detect script's top
        # opportunity (also "citation-helper" from sample-feature-requests.md)
        # will exact-name-match against.
        _seed_installed_skill(root, "citation-helper", "academic citation",
                              ["APA format", "MLA format", "source metadata",
                               "reference list", "Chicago citation", "bibliography"])

        env = os.environ.copy()
        env["SKILL_FORGE_APPROVAL_SECRET"] = "release-check-secret"

        feedback_file = Path(feedback_dir) / "skill-feedback.jsonl"
        result = run_json([
            sys.executable,
            str(SKILL_FORGE / "scripts" / "forge_pipeline.py"),
            "--source", str(SKILL_FORGE / "examples" / "sample-feature-requests.md"),
            "--source", str(SKILL_FORGE / "examples" / "sample-errors.md"),
            "--output", out_str,
            "--target-root", str(root),
            "--eval", "hidden",
            "--install", "plan",
            "--prefer-evolve",
            "--agent-name", "StudyAgent",
            "--json",
        ], env=env)

        assert_true(result.get("routed_to") == "evolve",
                    f"prefer-evolve with matching installed skill should route to evolve, got {result.get('routed_to')}")
        routing = result.get("routing", {})
        assert_true(routing.get("decision") == "evolve",
                    f"routing decision should be evolve, got {routing.get('decision')}")
        assert_true(routing.get("target_skill") == "citation-helper",
                    f"routing target should be citation-helper, got {routing.get('target_skill')}")
        feedback_record = result.get("feedback_record", {})
        assert_true(feedback_record.get("entry", {}).get("source") == "forge-routing",
                    "synthetic feedback must be tagged source=forge-routing for audit")
        evolve_result = result.get("evolve_result", {})
        assert_true(evolve_result.get("status") == "ok",
                    f"evolve sub-pipeline should succeed, got status={evolve_result.get('status')}")


def check_forge_pipeline_default_does_not_route() -> None:
    """Backward compat: without --prefer-evolve, forge_pipeline must behave
    exactly as before (no routing call, no evolve dispatch)."""
    with tempfile.TemporaryDirectory() as root_str, tempfile.TemporaryDirectory() as out_str:
        root = Path(root_str)
        _seed_installed_skill(root, "citation-helper", "academic citation",
                              ["APA format", "MLA format", "source metadata",
                               "reference list", "Chicago citation", "bibliography"])
        result = run_json([
            sys.executable,
            str(SKILL_FORGE / "scripts" / "forge_pipeline.py"),
            "--source", str(SKILL_FORGE / "examples" / "sample-feature-requests.md"),
            "--source", str(SKILL_FORGE / "examples" / "sample-errors.md"),
            "--output", out_str,
            "--target-root", str(root),
            "--eval", "hidden",
            "--install", "plan",
            "--agent-name", "StudyAgent",
            "--json",
        ])
        assert_true(result.get("routed_to") == "forge",
                    f"default behavior should be routed_to=forge, got {result.get('routed_to')}")
        assert_true(result.get("routing") is None,
                    "default behavior must not invoke decide (routing should be None)")
        assert_true(Path(result["skill_dir"]).is_dir(),
                    "default behavior should still produce a candidate skill directory")


def check_extraneous_docs_case_insensitive() -> None:
    with tempfile.TemporaryDirectory() as gen:
        candidate = _scaffold_candidate(Path(gen), "case-probe-skill")
        for filename in ("readme.md", "Readme.MD", "INSTALL.md", "Setup.md", "QUICKSTART.md"):
            (candidate / filename).write_text("# test\n", encoding="utf-8")
            invalid = run_json(
                [
                    sys.executable,
                    str(SKILL_FORGE / "scripts" / "validate_skill_candidate.py"),
                    str(candidate),
                    "--json",
                ],
                check=False,
            )
            assert_true(
                not invalid["valid"],
                f"validator should reject extraneous doc filename {filename!r}",
            )
            assert_true(
                any("bloat agent context" in error for error in invalid["errors"]),
                f"extraneous-doc error missing for {filename!r}",
            )
            (candidate / filename).unlink()


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
        ("decide-routes-to-evolve-when-similar", check_decide_routes_to_evolve_when_similar),
        ("decide-routes-to-forge-when-novel", check_decide_routes_to_forge_when_novel),
        ("decide-respects-profile-mismatch", check_decide_respects_profile_mismatch),
        ("decide-flags-ambiguous-when-tied", check_decide_flags_ambiguous_when_tied),
        ("forge-pipeline-prefer-evolve-routes", check_forge_pipeline_prefer_evolve_routes_through_decide),
        ("forge-pipeline-default-does-not-route", check_forge_pipeline_default_does_not_route),
        ("extraneous-docs-case-insensitive", check_extraneous_docs_case_insensitive),
        ("frontmatter-metadata-allowlist", check_frontmatter_metadata_allowlist),
        ("workflow-section-required", check_workflow_section_required),
        ("numbered-steps-scoped-to-workflow", check_numbered_steps_must_live_in_workflow),
        ("scaffold-description-anchored", check_scaffold_description_anchored_to_user_triggers),
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
