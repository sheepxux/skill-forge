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

Skill install mutations are Telegram-gated. Direct `--apply` calls are blocked unless they come from a Telegram-approved pipeline.

