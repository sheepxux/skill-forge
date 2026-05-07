import sys
from pathlib import Path
from typing import Optional


def install_args(scripts_dir: Path, args, skill_dir: str, apply: bool = False, approval: Optional[dict] = None) -> list[str]:
    command = [
        sys.executable,
        str(scripts_dir / "install" / "propose_skill_install.py"),
        skill_dir,
        "--target-root",
        args.target_root,
        "--method",
        args.install_method,
        "--json",
    ]
    if apply:
        command.append("--apply")
        command.append("--approved-by-telegram")
        if approval and approval.get("request_id"):
            command.extend(["--approval-request-id", str(approval["request_id"])])
    return command


def telegram_approval_args(
    scripts_dir: Path,
    args,
    plan: dict,
    report: dict,
    evaluation: Optional[dict],
    profile: str,
) -> list[str]:
    eval_payload = evaluation or {"passed": True, "score": "not-run"}
    command = [
        sys.executable,
        str(scripts_dir / "install" / "telegram_approval.py"),
        "--skill",
        plan["skill"],
        "--profile",
        profile,
        "--validation-score",
        str(report.get("score", "")),
        "--validation-grade",
        str(report.get("grade", "")),
        "--evaluation-score",
        str(eval_payload.get("score", "")),
        "--target",
        plan["target"],
        "--method",
        plan["method"],
        "--timeout",
        str(args.telegram_timeout),
        "--bot-token-env",
        args.telegram_bot_token_env,
        "--chat-id-env",
        args.telegram_chat_id_env,
        "--dry-run",
        args.telegram_dry_run,
        "--json",
    ]
    if getattr(args, "env_file", ""):
        command.extend(["--env-file", args.env_file])
    if getattr(args, "agent_name", ""):
        command.extend(["--agent-name", args.agent_name])
    if eval_payload.get("passed"):
        command.append("--evaluation-passed")
    return command


def telegram_required_status(install_mode: str) -> Optional[str]:
    if install_mode in {"ask", "auto"}:
        return "telegram approval required; local ask/auto install is disabled"
    return None


def confirm_install(plan: dict, action: str = "Install skill") -> bool:
    prompt = f"{action} '{plan['skill']}' to {plan['target']} using {plan['method']}? [y/N] "
    print(prompt, end="", file=sys.stderr, flush=True)
    return sys.stdin.readline().strip().lower() in {"y", "yes"}


def install_eligibility(
    report: dict,
    evaluation: Optional[dict],
    replay: Optional[dict],
    authorization: dict,
    min_score: int,
) -> tuple[bool, str]:
    if not report.get("valid"):
        return False, "validation failed"
    score = int(report.get("score", 0))
    if score < min_score:
        return False, f"score {score} is below install threshold {min_score}"
    if evaluation and not evaluation.get("passed"):
        return False, "hidden evaluation failed"
    if replay and replay.get("cases_run", 0) > 0 and not replay.get("passed"):
        return False, "replay evaluation failed"
    if not authorization.get("allowed", True):
        return False, authorization.get("reason", "agent authorization failed")
    return True, "eligible"
