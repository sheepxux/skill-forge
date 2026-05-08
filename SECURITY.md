# Security Policy

## Secrets

Do not commit real API keys, Telegram bot tokens, chat IDs, Notion tokens, or OpenClaw workspace credentials.

Use a private env file such as `~/.openclaw/skill-forge.env` and pass it with `--env-file`, or set environment variables in the shell.

## Before Publishing

Run:

```bash
python3 tests/run_release_checks.py
```

If any secret is reported, remove it before publishing. If the secret was ever pushed to a remote repository or shared publicly, rotate it with the provider.

## Install Safety

Skill install mutations are gated by a signed approval token (HMAC-SHA256). `propose_skill_install.py --apply` requires `--approval-token <token>` and verifies:

- the signature against the secret in `SKILL_FORGE_APPROVAL_SECRET` (or, if unset, a value derived from the Telegram bot token),
- the token has not expired (default TTL 30 minutes),
- the claimed `skill`, `target`, `method`, `source_dir`, and a SHA-256 hash over the candidate directory all match the install being applied.

A dry-run approval (`--telegram-dry-run approve`) issues a token tagged `mode=dry-run`. The install script rejects it by default; only `--allow-dry-run-install` lets it through, and the manifest records `approved_by=dry-run` rather than `telegram`. Pipelines surface this as `install_status=dry-run-blocked` and do not call the install with mutation rights.

Approval tokens are bound to both the source path and the directory's content hash, so swapping the candidate's contents between issuance and apply invalidates the token.

Token issuance and install apply both require the source to be an existing skill directory containing `SKILL.md`. Missing sources and non-skill directories are rejected before any filesystem mutation, even if the token claims otherwise.

## Privacy

Feedback recorded via `record_skill_feedback.py` is redacted before storage. The redactor scrubs emails, JWTs, PEM-encoded private keys, Telegram bot tokens, common cloud / Git / Slack token prefixes (`AKIA`, `AIza`, `ghp_`, `xoxb-`, etc.), IPv4 and IPv6 addresses, and phone numbers with explicit separators. Long high-entropy strings (≥40 characters) are also redacted unless adjacent to path or punctuation characters.

JSONL feedback writes are guarded with `fcntl.LOCK_EX` to prevent torn lines under concurrent writers. Manifest writes are atomic (`os.replace`) and held under the same advisory lock.
