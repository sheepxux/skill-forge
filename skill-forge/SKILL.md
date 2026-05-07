---
name: skill-forge
description: Detect repeated capability gaps, convert recurring user needs into candidate skills, scaffold new OpenClaw-compatible skills, and validate them before installation. Use when an agent repeatedly fails the same task, sees recurring feature requests, notices repetitive manual workflows, or wants to propose a new skill instead of solving the same problem ad hoc.
---

# skill-forge

Use this skill to turn repeated demand into a reviewed skill candidate.

Current version: `v0.4.2 "Telegram Gate"`.

## Core jobs

1. Detect repeated capability gaps from logs, `.learnings`, and feature requests.
2. Decide whether the pattern is stable enough to deserve its own skill.
3. Classify the opportunity as `academic`, `product`, `integration`, `script`, or `workflow`.
4. Generate a candidate skill folder with a usable `SKILL.md`, `agents/openai.yaml`, and profile-specific resources.
5. Validate and score the candidate before proposing installation.
6. Run hidden smoke evaluation and Agent profile authorization before confirmed installation.
7. Record feedback from later usage and propose reviewed updates instead of mutating installed skills directly.
8. Provide the Somnia runtime used by scheduled nightly review to find skills with bugs, weak scores, or update-worthy feedback.
9. Use redacted replay cases to check whether candidates actually cover real feedback-derived tasks.

## Trigger Cues

Use this skill when the user or agent mentions:

- repeated failure
- missing capability
- recurring workflow
- feature request
- make a new skill
- scaffold a skill
- validate a generated skill

## Default Workflow

1. Detect repeated capability gaps from learning files or session-derived notes.
2. Classify the strongest opportunity into a skill profile.
3. Scaffold a candidate skill with profile-specific resources.
4. Validate the candidate and inspect score, warnings, and references.
5. Run hidden smoke evaluation without exposing simulated cases to users.
6. Propose installation, then require Telegram approval before applying it.
7. Record future usage feedback and run an evolution pipeline when enough feedback accumulates.
8. During scheduled reviews, write summary reports and optionally propose updates without exposing hidden evaluation details.
9. Run replay evaluation before approving evolved candidates when replay cases exist.

## Commands

### Detect

Run:

```bash
python3 {baseDir}/scripts/detect_skill_opportunities.py --json
```

Add `--source` paths when a specific workspace or learnings file should be analyzed.

### Choose

Only create a skill when the pattern is:

- recurring
- broad enough to reuse
- structured enough to document
- more stable than a one-off prompt

If the need is too narrow, keep it as a note or workflow rule instead.

### Scaffold

Run:

```bash
python3 {baseDir}/scripts/generate_skill_scaffold.py \
  --skill-name my-skill \
  --output ./generated \
  --goal "What the skill should achieve." \
  --triggers "keyword1, keyword2" \
  --template auto
```

### Validate

Run:

```bash
python3 {baseDir}/scripts/validate_skill_candidate.py ./generated/my-skill
```

### Propose Installation

Run:

```bash
python3 {baseDir}/scripts/propose_skill_install.py ./generated/my-skill
```

Use `--apply` only after the candidate has been reviewed.

### Record Feedback

Run:

```bash
python3 {baseDir}/scripts/record_skill_feedback.py \
  --skill my-skill \
  --agent-name StudyAgent \
  --rating negative \
  --feedback "触发词: literature review. The skill should handle literature review planning better." \
  --json
```

### Propose Evolution

Run:

```bash
python3 {baseDir}/scripts/evolve_skill_pipeline.py \
  --skill my-skill \
  --output ./generated-updates \
  --install plan \
  --replay hidden \
  --agent-name StudyAgent \
  --json
```

### Replay Evaluation

Run:

```bash
python3 {baseDir}/scripts/replay/collect_replay_cases.py \
  --feedback-file ~/.openclaw/workspace/.learnings/skill-feedback.jsonl \
  --skill my-skill \
  --json

python3 {baseDir}/scripts/replay/run_replay_eval.py \
  --skill-dir ./generated-updates/my-skill \
  --skill my-skill \
  --json
```

### Nightly Review

Somnia is now packaged as its own skill for scheduled maintenance. These compatibility commands remain available from Skill Forge:

```bash
python3 {baseDir}/scripts/nightly_skill_review.py \
  --scope managed \
  --propose-updates \
  --replay hidden \
  --update-install plan \
  --json
```

Install a macOS daily sleep-hour schedule, defaulting to 03:00 local time:

```bash
python3 {baseDir}/scripts/schedule_nightly_review.py \
  --hour 3 \
  --minute 0 \
  --scope managed \
  --propose-updates \
  --update-install plan \
  --apply \
  --json
```

Use `--telegram-report` with `--env-file ~/.openclaw/skill-forge.env` when scheduled runs should send a summary report to Telegram. The env file should define `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Uninstall or rollback a generated skill:

```bash
python3 {baseDir}/scripts/propose_skill_install.py my-skill --uninstall --apply
python3 {baseDir}/scripts/propose_skill_install.py my-skill --uninstall --restore-backup --apply
```

## Full Pipeline

For one-shot operation:

```bash
python3 {baseDir}/scripts/forge_pipeline.py \
  --source ~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md \
  --source ~/.openclaw/workspace/.learnings/ERRORS.md \
  --output ./generated \
  --eval hidden \
  --json
```

Ask through Telegram before installing:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

python3 {baseDir}/scripts/forge_pipeline.py \
  --source ~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md \
  --source ~/.openclaw/workspace/.learnings/ERRORS.md \
  --output ./generated \
  --install telegram \
  --agent-name StudyAgent \
  --json
```

## Decision rules

- Prefer creating a skill over a new agent when the new capability is narrow.
- Prefer a new agent over a skill when the work needs a distinct role, tools, and long-term memory boundary.
- Prefer `references/` when the skill mainly teaches structure and judgment.
- Prefer `scripts/` when the same code would otherwise be rewritten repeatedly.
- Default to `--install plan`; use `--install telegram` for any mutation.
- Treat `--install ask` and `--install auto` as blocked compatibility aliases.
- Do not call `propose_skill_install.py --apply` directly; apply is guarded for Telegram-approved pipelines.
- Keep `--eval hidden` for user-facing flows so simulated checks and prompts are not exposed.
- Use `--agent-name` before installation when a specific agent will receive the skill.
- Never hard-code Telegram tokens; discover them from OpenClaw/env files or environment variables.
- Redact feedback text before storing it.
- Treat feedback-driven changes as update candidates, not direct edits to installed skills.
- Install evolved skills only after validation, hidden evaluation, authorization, and approval.
- Use replay as a regression gate when feedback-derived cases exist.
- Scheduled nightly review may propose updates, but install changes still require Telegram approval.
- Nightly reports should show only health summaries, not hidden evaluation prompts or simulated checks.
- Default nightly review scope is `managed`; use `--scope all` only for explicit full inventory audits.

## Output Contract

The skill-forge output should include:

- detected opportunity name
- recommended template profile
- generated candidate path
- validation score and grade
- install status
- approval status when Telegram confirmation is used
- nightly review report path when running scheduled review
- install plan
- review warnings, if any

## Quality Gates

Before proposing installation, confirm:

- the skill name is concrete and reusable
- the description has clear trigger conditions
- the generated structure matches the intended job
- the candidate improves a real recurring workflow
- validation score is at least 70
- `grade=milestone` is preferred before sharing externally
- installation threshold is at least 85 unless the user explicitly chooses otherwise
- hidden smoke evaluation passes
- target Agent profile policy allows the generated skill profile
- Telegram approval is available before applying install or uninstall changes
- feedback-derived updates are reviewed as candidates before replacing an installed skill
- replay evaluation passes when replay cases exist
- nightly review reports are written before any update proposal is installed
- scheduled automation uses explicit launchd configuration and can be uninstalled

Read `references/skill-quality-rubric.md` when evaluating a draft.

## Resources

References:
- `references/heuristics.md`
- `references/skill-quality-rubric.md`
- `references/milestone-architecture.md`

Scripts:
- `scripts/detect_skill_opportunities.py`
- `scripts/evaluate_skill_candidate.py`
- `scripts/generate_skill_scaffold.py`
- `scripts/validate_skill_candidate.py`
- `scripts/forge_pipeline.py`
- `scripts/install/propose_skill_install.py`
- `scripts/install/telegram_approval.py`
- `scripts/evolve/evolve_skill_pipeline.py`
- `scripts/evolve/propose_skill_update.py`
- `scripts/evolve/record_skill_feedback.py`
- `scripts/replay/collect_replay_cases.py`
- `scripts/replay/compare_replay_outputs.py`
- `scripts/replay/redact_replay_case.py`
- `scripts/replay/replay_report.py`
- `scripts/replay/run_replay_eval.py`
- `scripts/somnia/nightly_skill_review.py`
- `scripts/somnia/schedule_nightly_review.py`

Compatibility wrappers:
- `scripts/propose_skill_install.py`
- `scripts/telegram_approval.py`
- `scripts/evolve_skill_pipeline.py`
- `scripts/propose_skill_update.py`
- `scripts/record_skill_feedback.py`
- `scripts/nightly_skill_review.py`
- `scripts/schedule_nightly_review.py`
