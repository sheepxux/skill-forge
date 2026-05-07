<p align="center">
  <img src="assets/skill-forge-logo.png" alt="Skill Forge logo" width="360">
</p>

# Skill Forge

This repository contains the `skill-forge` OpenClaw-compatible skill. It also supports a sibling companion skill:

- `skill-forge`: generates, validates, installs, and evolves reusable skills.
- `somnia`: optional companion skill for overnight health review and proposal-based skill maintenance.

`skill-forge` is a milestone self-improvement product for OpenClaw-style agents.

Current version: `v0.4.2 "Telegram Gate"`.

It turns repeated capability gaps into reviewed skill candidates. The product deliberately separates learning, generation, validation, and installation so an agent can improve itself without silently polluting its own skill set.

## Quick Start

### 1. Install the skill into OpenClaw

Install from ClawHub:

```bash
clawhub install skills-forge
```

Optional companion:

```bash
clawhub install somnia
```

The ClawHub package is published as `skills-forge` because `skill-forge` is already used by another publisher. ClawHub installs it into a `skills-forge/` folder; the skill metadata name remains `skill-forge`.

ClawHub may show a safety warning because this skill includes Telegram approval calls and local install/rollback scripts. Review the source first; for non-interactive installs, pass `--force` only after review.

For local development, symlink this repository into OpenClaw:

```bash
mkdir -p ~/.openclaw/workspace/skills
ln -sfn "$HOME/Desktop/skill-forge/skill-forge" ~/.openclaw/workspace/skills/skill-forge
```

If you also use Somnia, place its separate folder next to this repository and install the sibling skill:

```bash
ln -sfn "$HOME/Desktop/somnia" ~/.openclaw/workspace/skills/somnia
```

### 2. Configure Telegram approval

Copy the example env file to a private OpenClaw env file:

```bash
cp .env.example ~/.openclaw/skill-forge.env
```

Edit `~/.openclaw/skill-forge.env` and set your own Telegram bot token and chat ID. Do not commit that file.

### 3. Run release checks

```bash
python3 tests/run_release_checks.py
```

### 4. Generate a candidate skill

```bash
python3 skill-forge/scripts/forge_pipeline.py \
  --source skill-forge/examples/sample-feature-requests.md \
  --source skill-forge/examples/sample-errors.md \
  --output ./generated \
  --eval hidden \
  --install plan \
  --agent-name StudyAgent \
  --json
```

### 5. Install only after Telegram approval

```bash
python3 skill-forge/scripts/forge_pipeline.py \
  --source skill-forge/examples/sample-feature-requests.md \
  --source skill-forge/examples/sample-errors.md \
  --output ./generated \
  --eval hidden \
  --install telegram \
  --env-file ~/.openclaw/skill-forge.env \
  --agent-name StudyAgent \
  --json
```

Reply to the Telegram approval message with `同意安装` or `yes`.

## What it does

- Detects repeated capability gaps from `.learnings`, errors, and feature requests.
- Classifies opportunities into template profiles: `academic`, `product`, `integration`, `script`, or `workflow`.
- Generates candidate skills with `SKILL.md`, `agents/openai.yaml`, and profile-specific references or scripts.
- Scores generated candidates with a quality validator that checks both structure and profile-specific behavior.
- Runs hidden smoke evaluation without exposing simulated cases in user-facing output.
- Enforces optional Agent profile authorization before confirmed installation.
- Produces an install plan and requires Telegram approval before installing or replacing a skill.
- Records later usage feedback and proposes reviewed skill updates instead of self-mutating installed skills.
- Runs scheduled nightly health reviews during sleep hours and can propose safe update candidates.
- Builds redacted replay cases from feedback and blocks update candidates that regress on replay evaluation.

## Repository Layout

```text
skill-forge/
├── README.md
├── SECURITY.md
├── LICENSE
├── .env.example
├── tests/
│   └── run_release_checks.py
└── skill-forge/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── scripts/
    │   ├── detect_skill_opportunities.py
    │   ├── evaluate_skill_candidate.py
    │   ├── forge_pipeline.py
    │   ├── generate_skill_scaffold.py
    │   ├── validate_skill_candidate.py
    │   ├── install/
    │   ├── evolve/
    │   ├── replay/
    │   ├── security/
    │   ├── somnia/
    │   └── templates/
    ├── references/
    └── examples/

../somnia/                 # optional companion skill, separate folder/repo
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/
```

The detailed `skill-forge` package layout:

```text
skill-forge/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── detect_skill_opportunities.py
│   ├── evaluate_skill_candidate.py
│   ├── forge_pipeline.py
│   ├── generate_skill_scaffold.py
│   ├── validate_skill_candidate.py
│   ├── install/
│   │   ├── propose_skill_install.py
│   │   └── telegram_approval.py
│   ├── evolve/
│   │   ├── evolve_skill_pipeline.py
│   │   ├── propose_skill_update.py
│   │   └── record_skill_feedback.py
│   ├── replay/
│   │   ├── collect_replay_cases.py
│   │   ├── compare_replay_outputs.py
│   │   ├── redact_replay_case.py
│   │   ├── replay_report.py
│   │   └── run_replay_eval.py
│   ├── security/
│   │   └── scan_secrets.py
│   ├── somnia/
│   │   ├── common.py
│   │   ├── nightly_skill_review.py
│   │   ├── reporting.py
│   │   ├── scanner.py
│   │   └── schedule_nightly_review.py
│   └── templates/
│       └── profile_packs.py
├── references/
│   ├── heuristics.md
│   ├── milestone-architecture.md
│   └── skill-quality-rubric.md
└── examples/
    ├── sample-errors.md
    └── sample-feature-requests.md

```

Root-level wrappers remain under `skill-forge/scripts/*.py` for backward compatibility. If the optional sibling `../somnia` skill is present, it delegates to the maintained Skill Forge Somnia runtime so there is one source of truth for scheduled review behavior.

## Fast Demo

Run the full pipeline:

```bash
python3 skill-forge/scripts/forge_pipeline.py \
  --source skill-forge/examples/sample-feature-requests.md \
  --source skill-forge/examples/sample-errors.md \
  --output ./generated-milestone \
  --eval hidden \
  --json
```

Expected behavior:

- detects `citation-helper`
- classifies it as `academic`
- generates `generated-milestone/citation-helper`
- validates it as `grade=milestone`
- prints an install plan for OpenClaw

Ask through Telegram before installing:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

python3 skill-forge/scripts/forge_pipeline.py \
  --source skill-forge/examples/sample-feature-requests.md \
  --source skill-forge/examples/sample-errors.md \
  --output ./generated-milestone \
  --install telegram \
  --agent-name StudyAgent \
  --json
```

## Manual Workflow

### 1. Detect opportunities

```bash
python3 skill-forge/scripts/detect_skill_opportunities.py \
  --source ~/.openclaw/workspace/.learnings/FEATURE_REQUESTS.md \
  --source ~/.openclaw/workspace/.learnings/ERRORS.md \
  --json
```

### 2. Generate a candidate skill

```bash
python3 skill-forge/scripts/generate_skill_scaffold.py \
  --skill-name citation-helper \
  --output ./generated \
  --goal "Help Study Agent produce citation-aware academic scaffolds." \
  --triggers "citation, bibliography, references, APA, MLA" \
  --template academic
```

### 3. Validate the candidate

```bash
python3 skill-forge/scripts/validate_skill_candidate.py \
  ./generated/citation-helper
```

### 4. Propose installation

```bash
python3 skill-forge/scripts/propose_skill_install.py \
  ./generated/citation-helper
```

### 5. Record feedback after use

```bash
python3 skill-forge/scripts/record_skill_feedback.py \
  --skill citation-helper \
  --agent-name StudyAgent \
  --rating negative \
  --feedback "触发词: literature review. The skill should handle literature review planning better." \
  --json
```

### 6. Propose a reviewed update

```bash
python3 skill-forge/scripts/evolve_skill_pipeline.py \
  --skill citation-helper \
  --output ./generated-updates \
  --install telegram \
  --replay hidden \
  --agent-name StudyAgent \
  --json
```

### 7. Run replay evaluation

```bash
python3 skill-forge/scripts/replay/collect_replay_cases.py \
  --feedback-file ~/.openclaw/workspace/.learnings/skill-feedback.jsonl \
  --skill citation-helper \
  --json

python3 skill-forge/scripts/replay/run_replay_eval.py \
  --skill-dir ./generated-updates/citation-helper \
  --skill citation-helper \
  --json
```

### 8. Run nightly review

```bash
python3 skill-forge/scripts/nightly_skill_review.py \
  --scope managed \
  --propose-updates \
  --replay hidden \
  --update-install plan \
  --json
```

### 9. Schedule nightly review on macOS

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

## Product stance

Recommended operating modes:

- `observe`: detect only
- `draft`: detect and scaffold
- `review`: validate and propose installation

Silent self-installation is intentionally not the default. Generated skills should pass validation and at least one real task before being enabled for an agent.

Feedback-driven evolution follows the same rule. A skill can collect feedback and propose an updated candidate, but it does not directly mutate the installed runtime skill without validation and approval. Feedback text is redacted before storage.

Nightly review follows the same safety model. It can scan installed skills, write health reports, and propose update candidates during sleep hours, but installing those updates still requires Telegram approval.

Somnia is also packaged as its own skill for clearer agent routing. Use `somnia` when the task is about scheduled maintenance, health reports, replay regression checks, or sleep-hour upgrade proposals. Use `skill-forge` when the task is about creating or evolving a specific skill candidate.

The default nightly scope is `managed`, meaning Skill Forge only reviews skills installed through its manifest. Use `--scope feedback` to include skills with feedback records, or `--scope all` for an explicit full inventory audit.

Replay evaluation is offline and privacy-aware by default. It builds redacted cases from feedback, scores whether candidate skill instructions cover expected traits, and returns only summary scores in user-facing flows.

Installation modes:

- `--install plan`: default, only prints the install plan.
- `--install telegram`: sends a Telegram approval request and installs only after approval.
- `--install ask`: blocked compatibility alias; local approvals cannot mutate skills.
- `--install auto`: blocked compatibility alias; silent auto-install is disabled.

Telegram approval uses these environment variables by default:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token.
- `TELEGRAM_CHAT_ID`: approval chat ID.

Config discovery order:

- Explicit `--env-file`.
- `~/.openclaw/telegram.env`.
- `~/.openclaw/skill-forge.env`.
- `~/.openclaw/.env`.
- `~/.openclaw/workspace/telegram.env`.
- `~/.openclaw/workspace/.env`.
- Existing process environment variables.

OpenClaw-style aliases are also supported: `OPENCLAW_TELEGRAM_BOT_TOKEN` and `OPENCLAW_TELEGRAM_CHAT_ID`.

Approval replies accepted by default:

- approve: `同意安装`, `同意`, `yes`, `y`, `approve`
- reject: `拒绝安装`, `拒绝`, `no`, `n`, `reject`

For safety, non-reply approval messages must include the request ID shown in the Telegram approval message.

Evaluation modes:

- `--eval hidden`: default, runs smoke checks and hides internal scenarios.
- `--eval off`: disables smoke evaluation.
- `--eval details`: developer mode, exposes internal check details.

Replay modes:

- `--replay hidden`: default for evolution and nightly review, runs replay checks and hides case details.
- `--replay off`: disables replay evaluation.

Nightly review outputs:

- JSON and Markdown reports under `~/.openclaw/workspace/.learnings/skill-forge-nightly`.
- Optional update candidates under `~/.openclaw/workspace/skill-forge-updates`.
- Optional Telegram summary reports with `--telegram-report`.

For scheduled Telegram reports, put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in an env file such as `~/.openclaw/skill-forge.env`, then pass `--env-file ~/.openclaw/skill-forge.env`.

Rollback and uninstall:

```bash
python3 skill-forge/scripts/propose_skill_install.py citation-helper --uninstall
python3 skill-forge/scripts/propose_skill_install.py citation-helper --uninstall --restore-backup
```

Direct `--apply` is intentionally guarded and requires a Telegram-approved pipeline to pass the internal approval marker.

## Release Checks

Run the full local release check before publishing:

```bash
python3 tests/run_release_checks.py
```

This checks Python compilation, secret scanning, skill validation, Skill Forge generation, Telegram-gated install behavior, and missing Telegram config handling. Somnia review is checked only when the optional sibling `../somnia` folder exists.

Run only the secret scanner:

```bash
python3 skill-forge/scripts/security/scan_secrets.py --json
```

Use `.env.example` as a template for private Telegram config. Do not commit real tokens.

## OpenClaw use

Install from ClawHub for normal use:

```bash
clawhub install skills-forge
clawhub install somnia
```

Copy or symlink the skill folders into your OpenClaw skills workspace if you are developing locally.

Example:

```bash
ln -sfn "$HOME/Desktop/skill-forge/skill-forge" ~/.openclaw/workspace/skills/skill-forge
ln -sfn "$HOME/Desktop/somnia" ~/.openclaw/workspace/skills/somnia
```

## Milestone Criteria

This version is considered a milestone because it has a real closed loop:

- `detect -> generate -> validate -> install-plan`
- hidden evaluation summary without exposing simulated tasks
- Telegram-gated installation flow
- Telegram approval flow
- backup-aware install and uninstall/rollback support
- feedback-driven update proposals
- scheduled nightly skill health review
- replay dataset and regression gate
- install manifest revision history
- optional Agent profile authorization
- profile-specific generation
- semantic quality gates for academic, product, integration, script, and workflow skills
- Python 3.9 compatible scripts
- no external Python dependencies
- GitHub-ready repository structure

## Version Milestones

- `v0.1.0`: detect, generate, validate, install plan
- `v0.2.0`: hidden eval, approval, feedback evolution, version history
- `v0.3.0 "Somnia"`: nightly review, LaunchAgent scheduling, module boundaries
- `v0.4.0 "Replay"`: redacted replay cases, replay scoring, regression gate
- `v0.4.1 "Somnia Split"`: standalone Somnia skill package and module cleanup
- `v0.4.2 "Telegram Gate"`: mandatory Telegram approval for install mutations

## License

MIT
