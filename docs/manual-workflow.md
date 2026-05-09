# Manual workflow (lower-level scripts)

The Forge Console (`scripts/skill_forge.py`) is the recommended interface for normal use. This document covers the lower-level scripts directly, for automation pipelines or when you need exact control over a single stage.

Every script accepts `--json` and emits machine-readable output suitable for piping into other tools.

## 1. Detect opportunities

```bash
python3 skill-forge/scripts/detect_skill_opportunities.py \
  --source ~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md \
  --source ~/.openclaw/workspace/.learnings/ERRORS.md \
  --json
```

## 2. Generate a candidate skill

```bash
python3 skill-forge/scripts/generate_skill_scaffold.py \
  --skill-name citation-helper \
  --output ./generated \
  --goal "Help Study Agent produce citation-aware academic scaffolds." \
  --triggers "citation, bibliography, references, APA, MLA" \
  --template academic
```

## 3. Validate the candidate

```bash
python3 skill-forge/scripts/validate_skill_candidate.py ./generated/citation-helper
```

## 4. Plan an installation (no mutation)

```bash
python3 skill-forge/scripts/propose_skill_install.py \
  ./generated/citation-helper \
  --json
```

`--apply` is gated by a signed approval token; the script blocks direct apply attempts. See §5.

## 5. Real-world install with signed approval

Plan:

```bash
python3 skill-forge/scripts/propose_skill_install.py \
  ./generated/citation-helper \
  --target-root ~/.openclaw/workspace/skills \
  --method symlink \
  --json
```

Issue an approval token via Telegram:

```bash
python3 skill-forge/scripts/install/telegram_approval.py \
  --skill citation-helper \
  --profile academic \
  --validation-score 100 \
  --validation-grade milestone \
  --evaluation-score 100 \
  --evaluation-passed \
  --target "$HOME/.openclaw/workspace/skills/citation-helper" \
  --method symlink \
  --source-dir "$(pwd)/generated/citation-helper" \
  --json > approval.json
```

Apply with the token:

```bash
APPROVAL_TOKEN="$(python3 -c 'import json; print(json.load(open("approval.json"))["approval_token"])')"

python3 skill-forge/scripts/propose_skill_install.py \
  ./generated/citation-helper \
  --target-root ~/.openclaw/workspace/skills \
  --method symlink \
  --apply \
  --approval-token "$APPROVAL_TOKEN" \
  --json
```

The token is HMAC-bound to the skill name, target path, install method, source path, and a SHA-256 hash of the source directory. Tampering with the candidate after approval invalidates the token.

## 6. Record feedback

```bash
python3 skill-forge/scripts/record_skill_feedback.py \
  --skill citation-helper \
  --agent-name StudyAgent \
  --rating negative \
  --feedback "触发词: literature review. The skill should handle literature review planning better." \
  --json
```

Feedback text is redacted before storage (emails, JWTs, PEM keys, common cloud / Git / Slack token prefixes, IPv4/v6, separator-bearing phone numbers).

## 7. Propose a reviewed update

```bash
python3 skill-forge/scripts/evolve_skill_pipeline.py \
  --skill citation-helper \
  --output ./generated-updates \
  --install telegram \
  --replay hidden \
  --min-replay-improvement 0 \
  --agent-name StudyAgent \
  --json
```

When an installed copy of `citation-helper` exists under `--target-root`, the candidate and the installed baseline are scored against the same redacted replay cases. The pipeline blocks the install when `candidate_score - baseline_score < --min-replay-improvement` (default `0`). Pass `--min-replay-improvement -100` to disable the regression gate while still running the coverage check.

The same signed-token gate from §5 applies: once Telegram approves, the pipeline verifies a fresh approval token bound to the *update candidate* before swapping it in.

## 8. Run replay evaluation manually

Build redacted cases from feedback:

```bash
python3 skill-forge/scripts/replay/collect_replay_cases.py \
  --feedback-file ~/.openclaw/workspace/.learnings/skill-feedback.jsonl \
  --skill citation-helper \
  --json
```

Score a single skill directory (coverage check):

```bash
python3 skill-forge/scripts/replay/run_replay_eval.py \
  --skill-dir ./generated-updates/citation-helper \
  --skill citation-helper \
  --json
```

Compare a candidate against an installed baseline (the actual non-regression gate):

```bash
python3 skill-forge/scripts/replay/compare_replay_outputs.py \
  --baseline ~/.openclaw/workspace/skills/citation-helper \
  --candidate ./generated-updates/citation-helper \
  --cases ~/.openclaw/workspace/.learnings/skill-replay-cases.jsonl \
  --skill citation-helper \
  --min-improvement 0 \
  --json
```

Exit code is non-zero when the candidate regresses by more than `--min-improvement`.

## 9. Run nightly review

```bash
python3 skill-forge/scripts/nightly_skill_review.py \
  --scope managed \
  --propose-updates \
  --replay hidden \
  --update-install plan \
  --json
```

## 10. Schedule nightly review on macOS

```bash
python3 skill-forge/scripts/schedule_nightly_review.py \
  --hour 3 \
  --minute 0 \
  --scope managed \
  --propose-updates \
  --update-install plan \
  --apply \
  --json
```

This installs a LaunchAgent that runs at 03:00 local time. Use `--uninstall --apply` with the same script to remove it.

## Rollback and uninstall

Plan-only (no token, no mutation):

```bash
python3 skill-forge/scripts/propose_skill_install.py citation-helper --uninstall --json
python3 skill-forge/scripts/propose_skill_install.py citation-helper --uninstall --restore-backup --json
```

Apply requires the same signed approval token as install. Issue an approval bound to the same skill name, target, and method first:

```bash
python3 skill-forge/scripts/install/telegram_approval.py \
  --skill citation-helper \
  --profile academic \
  --validation-score 100 --validation-grade milestone \
  --evaluation-score 100 --evaluation-passed \
  --target "$HOME/.openclaw/workspace/skills/citation-helper" \
  --method symlink \
  --json > approval.json

APPROVAL_TOKEN="$(python3 -c 'import json; print(json.load(open("approval.json"))["approval_token"])')"

python3 skill-forge/scripts/propose_skill_install.py citation-helper \
  --uninstall --apply --restore-backup \
  --approval-token "$APPROVAL_TOKEN" \
  --json
```

Direct `--apply` without a valid token is rejected with `status=blocked, reason=approval token required (run telegram_approval.py first)`. Forged or expired tokens fail signature / claim verification and are also rejected without mutating any state.

## Config discovery order

`telegram_approval.py` and any script that reads Telegram config look up env in this order; the first present value wins:

1. Explicit `--env-file <path>`
2. `~/.openclaw/telegram.env`
3. `~/.openclaw/skill-forge.env`
4. `~/.openclaw/.env`
5. `~/.openclaw/workspace/telegram.env`
6. `~/.openclaw/workspace/.env`
7. Process environment variables

Aliases supported alongside `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: `OPENCLAW_TELEGRAM_BOT_TOKEN`, `OPENCLAW_TELEGRAM_CHAT_ID`.

The HMAC secret comes from `SKILL_FORGE_APPROVAL_SECRET` if set, otherwise it is derived deterministically from the bot token. Set it explicitly when the bot token is shared across environments and you want a different blast radius for install approvals.

## Approval reply words

The approval bot prefers Telegram replies (`reply_to_message`) over plain-text matches. For non-reply messages, the request ID printed in the approval message must appear in the body to bind the approval to the right request.

| Decision | Accepted single-word replies (case-insensitive) |
| --- | --- |
| Approve | `y`, `yes`, `approve`, `approved`, `同意`, `同意安装`, `安装`, `确认` |
| Reject | `n`, `no`, `reject`, `rejected`, `拒绝`, `拒绝安装`, `取消`, `不同意` |
