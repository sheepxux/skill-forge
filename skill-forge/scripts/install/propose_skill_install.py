#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Optional


def manifest_path(target_root: Path) -> Path:
    return target_root / ".skill-forge-installs.json"


def load_manifest(target_root: Path) -> dict:
    path = manifest_path(target_root)
    if not path.exists():
        return {"installs": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(target_root: Path, manifest: dict) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    manifest_path(target_root).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def install_plan(skill_dir: Path, target_root: Path, method: str) -> dict:
    target = target_root / skill_dir.name
    return {
        "skill": skill_dir.name,
        "source": str(skill_dir),
        "target": str(target),
        "method": method,
        "commands": [
            f"mkdir -p {target_root}",
            f"ln -sfn {skill_dir} {target}" if method == "symlink" else f"cp -R {skill_dir} {target}",
        ],
        "notes": [
            "Review the generated skill before installing it.",
            "Add the skill name to specific agent configs only after it passes real tasks.",
            "Existing targets are backed up before replacement.",
        ],
    }


def backup_existing(target: Path, target_root: Path) -> Optional[str]:
    if not target.exists() and not target.is_symlink():
        return None
    backup_root = target_root / ".skill-forge-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"{target.name}-{timestamp()}"
    target.rename(backup)
    return str(backup)


def apply_install(
    skill_dir: Path,
    target_root: Path,
    method: str,
    approved_by_telegram: bool,
    approval_request_id: str,
) -> tuple[Path, Optional[str]]:
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / skill_dir.name
    backup = backup_existing(target, target_root)
    if method == "symlink":
        target.symlink_to(skill_dir, target_is_directory=True)
    else:
        shutil.copytree(skill_dir, target)
    manifest = load_manifest(target_root)
    previous = manifest.setdefault("installs", {}).get(skill_dir.name, {})
    history = list(previous.get("versions", []))
    revision = len(history) + 1
    history.append(
        {
            "revision": revision,
            "source": str(skill_dir),
            "target": str(target),
            "method": method,
            "installed_at": timestamp(),
            "previous_backup": backup,
            "approved_by": "telegram" if approved_by_telegram else None,
            "approval_request_id": approval_request_id or None,
        }
    )
    manifest.setdefault("installs", {})[skill_dir.name] = {
        "skill": skill_dir.name,
        "source": str(skill_dir),
        "target": str(target),
        "method": method,
        "installed_at": timestamp(),
        "previous_backup": backup,
        "approved_by": "telegram" if approved_by_telegram else None,
        "approval_request_id": approval_request_id or None,
        "revision": revision,
        "versions": history,
    }
    save_manifest(target_root, manifest)
    return target, backup


def remove_target(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)


def uninstall_skill(skill_name: str, target_root: Path, restore_backup: bool) -> dict:
    manifest = load_manifest(target_root)
    installs = manifest.setdefault("installs", {})
    record = installs.get(skill_name, {})
    target = Path(record.get("target", str(target_root / skill_name)))
    removed = target.exists() or target.is_symlink()
    if removed:
        remove_target(target)

    restored_backup = None
    backup = record.get("previous_backup")
    if restore_backup and backup:
        backup_path = Path(backup)
        if backup_path.exists() or backup_path.is_symlink():
            backup_path.rename(target)
            restored_backup = str(target)

    installs.pop(skill_name, None)
    save_manifest(target_root, manifest)
    return {
        "skill": skill_name,
        "target": str(target),
        "removed": removed,
        "restored_backup": restored_backup,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or apply an OpenClaw skill install proposal.")
    parser.add_argument("skill_dir", help="Candidate skill directory, or skill name when uninstalling.")
    parser.add_argument(
        "--target-root",
        default=str(Path.home() / ".openclaw" / "workspace" / "skills"),
        help="OpenClaw skills root.",
    )
    parser.add_argument("--method", choices=["symlink", "copy"], default="symlink")
    parser.add_argument("--apply", action="store_true", help="Actually install the skill candidate.")
    parser.add_argument(
        "--approved-by-telegram",
        action="store_true",
        help="Required safety marker for mutations after Telegram approval.",
    )
    parser.add_argument("--approval-request-id", default="", help="Telegram approval request ID for install audit records.")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall a skill by name or path.")
    parser.add_argument("--restore-backup", action="store_true", help="Restore the previous target backup when uninstalling.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    target_root = Path(args.target_root).expanduser().resolve()
    if args.apply and not args.approved_by_telegram:
        payload = {
            "status": "blocked",
            "reason": "telegram approval required before applying install changes",
            "installed": False,
            "target_root": str(target_root),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["reason"])
        return 1

    if args.uninstall:
        skill_name = Path(args.skill_dir).name
        plan = uninstall_skill(skill_name, target_root, args.restore_backup) if args.apply else {
            "skill": skill_name,
            "target": str(target_root / skill_name),
            "uninstall": True,
            "restore_backup": args.restore_backup,
            "installed": False,
        }
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"skill={plan['skill']}")
            print(f"target={plan['target']}")
            print(f"uninstall={plan.get('uninstall', True)}")
            print(f"restore_backup={args.restore_backup}")
        return 0

    skill_dir = Path(args.skill_dir).expanduser().resolve()
    plan = install_plan(skill_dir, target_root, args.method)

    if args.apply:
        target, backup = apply_install(
            skill_dir,
            target_root,
            args.method,
            args.approved_by_telegram,
            args.approval_request_id,
        )
        plan["installed"] = True
        plan["installed_target"] = str(target)
        plan["backup"] = backup
        plan["approved_by"] = "telegram"
        plan["approval_request_id"] = args.approval_request_id or None
    else:
        plan["installed"] = False

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"skill={plan['skill']}")
        print(f"source={plan['source']}")
        print(f"target={plan['target']}")
        print(f"method={plan['method']}")
        print(f"installed={plan['installed']}")
        print("commands:")
        for command in plan["commands"]:
            print(f"- {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
