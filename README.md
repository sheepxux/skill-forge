<p align="center">
  <img src="assets/skill-forge-logo.png" alt="Skill Forge logo" width="360">
</p>

# Skill Forge

[![Release Checks](https://github.com/sheepxux/skill-forge/actions/workflows/release-checks.yml/badge.svg)](https://github.com/sheepxux/skill-forge/actions/workflows/release-checks.yml)
[![ClawHub package](https://img.shields.io/badge/ClawHub-skills--forge-2ea44f)](https://clawhub.ai/sheepxux/skills-forge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English ｜ [简体中文](README.zh-CN.md)**

**Signed-approval skill pipeline for self-improving LLM agents.** Detect capability gaps from logs, scaffold by profile, validate, and require an HMAC-bound approval token before any install or update mutates state.

Current version: **`v1.4.0 "Evolve First"`**.

---

## Why Skill Forge

Most "self-improving agent" tooling lets the agent silently mutate its own skill set. That works in demos and breaks in production: a single bad skill silently overwrites a good one, no audit trail, no way to roll back, no way to tell whether the new skill is actually better than the one it replaced.

Skill Forge separates **detect → generate → validate → evaluate → install → evolve** into a signed pipeline:

- **Auto-detection** from `.learnings`, error logs, and feature requests so capability gaps surface before they become recurring failures.
- **Profile-aware scaffolding** for `academic` / `product` / `integration` / `script` / `workflow`, with bundled references and per-profile quality gates.
- **Quantitative validator** scores frontmatter, sections, triggers, references, and profile-specific behavior — milestone grade requires real structure, not vibes.
- **Signed approval gate**: every install or replace requires an HMAC-SHA256 token bound to the skill name, target path, install method, source path, and a SHA-256 hash of the source directory. Tamper with the candidate after approval → blocked. Direct `--apply` calls are blocked by design.
- **Replay non-regression check**: when an installed copy already exists, the candidate is scored against the same redacted feedback cases as the baseline; install blocked when the candidate regresses.
- **Evolve-first routing** *(opt-in via `--prefer-evolve`)*: before forging a brand-new skill, ask whether an installed skill should evolve instead — same profile, sufficient trigger / topic / name overlap. Prevents skill-set sprawl ("12 near-duplicate citation skills") while the signed gate + replay regression check still guard the actual mutation.
- **Audit trail** in a `flock`-protected, atomically-written manifest with full version history and rollback.
- **Privacy-first feedback**: redactor strips emails, JWTs, PEM private keys, Telegram bot tokens, common cloud / Git / Slack token prefixes, IPv4/v6, and separator-bearing phone numbers before anything touches disk.
- **Deterministic release benchmark** with validation, hidden-eval, line-count, and runtime budgets so quality gates don't drift between releases.

---

## 30-second demo

After [installing](#install), run the safe plan-only smoke test:

```bash
python3 skill-forge/scripts/skill_forge.py demo --json
```

Expected:

- detects the bundled `citation-helper` example
- classifies it as `academic`
- generates a candidate skill at `./generated-forge-demo/citation-helper`
- validates it as `grade=milestone`
- prints an install plan and exits with `install_status=planned`
- **does not mutate** any installed skills

To install with real Telegram approval:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

python3 skill-forge/scripts/skill_forge.py forge \
  --source skill-forge/examples/sample-feature-requests.md \
  --source skill-forge/examples/sample-errors.md \
  --output ./generated \
  --install telegram \
  --agent-name StudyAgent \
  --json
```

The pipeline sends a Telegram approval message bound to the candidate's content hash, waits for your reply (`yes` / `同意安装`), then verifies the signed token before any file mutation.

---

## Install

From [ClawHub](https://clawhub.ai/sheepxux/skills-forge):

```bash
clawhub install skills-forge
clawhub install somnia            # optional nightly-review companion
```

The ClawHub package slug is `skills-forge` (the `skill-forge` slug is taken by another publisher); the skill metadata name remains `skill-forge`. ClawHub may show a safety warning because this skill includes Telegram approval calls and local install/rollback scripts — review the source first.

For local development, symlink this repository into your OpenClaw workspace:

```bash
mkdir -p ~/.openclaw/workspace/skills
ln -sfn "$PWD/skill-forge" ~/.openclaw/workspace/skills/skill-forge
ln -sfn "$PWD/../somnia"   ~/.openclaw/workspace/skills/somnia      # if you cloned somnia next to this
```

Configure the Telegram approval channel:

```bash
cp .env.example ~/.openclaw/skill-forge.env
# Edit ~/.openclaw/skill-forge.env and set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
```

Verify readiness:

```bash
python3 skill-forge/scripts/skill_forge.py doctor \
  --env-file ~/.openclaw/skill-forge.env --json
```

---

## How the install gate works

```
┌─────────────────────┐
│ skill candidate dir │  ─┐
└─────────────────────┘   │   sha256(dir contents) ─┐
                          │                         │
            ┌─────────────▼──────────────┐          │
            │ telegram_approval.py       │          │
            │  - sends Telegram message  │          │
            │  - waits for reply         │          │
            │  - HMAC-signs token over:  │ ─────────┤
            │      skill, target,        │          │
            │      method, source_dir,   │          │
            │      source_hash, mode,    │          │
            │      issued_at, expires_at │          │
            └─────────────┬──────────────┘          │
                          │ approval_token          │
            ┌─────────────▼──────────────┐          │
            │ propose_skill_install.py   │          │
            │   --apply --approval-token │          │
            │  - verify HMAC             │          │
            │  - verify expiry           │          │
            │  - verify every claim      │ ◄────────┘
            │     (recompute source_hash)│
            └─────────────┬──────────────┘
                          │ all checks pass
                          ▼
              atomic + flock-protected
                  manifest write
```

There is no `--approved-by-telegram` boolean. The token *is* the gate. The HMAC secret comes from `SKILL_FORGE_APPROVAL_SECRET` if set, otherwise it is derived deterministically from the bot token (so any environment that can reach the bot can verify tokens issued there).

A `mode=dry-run` token (issued via `--telegram-dry-run approve`) is refused by `--apply` unless `--allow-dry-run-install` is passed; the audit field then records `approved_by=dry-run`, not `telegram`. Pipelines surface this as `install_status=dry-run-blocked`.

## How evolve-first routing works (opt-in, v1.4.0+)

```
                  ┌────────────────────────────┐
detect ──→  ──→   │ decide_skill_action.py     │
opportunity       │  for each installed skill: │
                  │   - profile match? (gate)  │
                  │   - trigger overlap        │
                  │   - topic overlap          │
                  │   - name overlap           │
                  │   - exact-name short-      │
                  │     circuit → fitness 1.0  │
                  └─────────────┬──────────────┘
                                │
            ┌───────────────────┼────────────────────┐
            ▼                   ▼                    ▼
    fitness ≥ threshold   0.4–threshold          fitness < threshold
    AND clear winner      OR top-2 within          OR no candidates
            │             ambiguous_margin                │
            ▼                   ▼                         ▼
    route to evolve      ambiguous (forge        forge new skill
    + write synthetic    today, surfaces in      (default scaffold flow)
    forge-routing        payload for review)
    feedback entry
```

Pass `--prefer-evolve` to `forge` (or call `decide` directly) to enable. The flag defaults off in v1.x for backward compatibility.

The router prevents skill sprawl when a request is really just a new trigger surface for something already installed. If it routes wrong, the **replay non-regression gate downstream catches it** — the candidate is scored against the same baseline cases and the install is blocked when fitness regresses. Worst case is a wasted scaffold cycle; the manifest never sees a bad install.

## How the replay regression gate works

When `evolve` runs against a skill that's already installed, the candidate **and** the installed baseline are scored against the same redacted replay cases. The install is blocked when:

```
candidate_score - baseline_score < --min-replay-improvement   # default 0
```

Replay scoring is offline keyword/coverage based — fast (milliseconds), deterministic, no API key. It catches the most common regression: someone deleted the section that addressed the user's original complaint. Pass `--min-replay-improvement -100` to disable the regression block while still emitting coverage scores.

---

## How is this different

| Capability | Skill Forge | LangChain Hub | AutoGen skills | OpenAI Apps SDK | Manual prompt files |
| --- | :---: | :---: | :---: | :---: | :---: |
| Auto-detect capability gaps from agent logs | ✅ | ❌ | ❌ | ❌ | ❌ |
| Quantitative quality validator (score + grade) | ✅ | ❌ | ❌ | platform review | ❌ |
| Profile-specific scaffolding (5 profiles) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Install requires signed approval token | ✅ HMAC + source-hash | ❌ | ❌ | platform review | ❌ |
| Candidate tamper invalidates approval | ✅ | ❌ | ❌ | n/a | ❌ |
| Non-regression check vs installed baseline | ✅ | ❌ | ❌ | ❌ | ❌ |
| Audit trail with rollback | ✅ atomic + `flock` | ❌ | ❌ | platform-side | ❌ |
| Redacted feedback storage | ✅ | ❌ | ❌ | platform-side | ❌ |
| Deterministic release benchmark | ✅ | ❌ | ❌ | ❌ | ❌ |
| Runtime / hosting required | none, local Python 3.9+ | hub fetch | local Python | OpenAI-hosted | none |
| License | MIT | MIT | MIT | proprietary | n/a |

Skill Forge is **complementary** to LangChain Hub / AutoGen / your own internal registry. Those are great for *sharing* prompts and modules. Skill Forge is what you put **in front of** any of them when you want reviewed, signed, regression-checked, audit-trailed installs of agent capabilities.

---

## Forge Console reference

`scripts/skill_forge.py` is the single product entry point. Every subcommand accepts `--json`.

| Command | Purpose | Mutation risk |
| --- | --- | --- |
| `doctor`[^doctor] | Check local readiness: package, Python, OpenClaw path, Telegram config, approval secret, ClawHub, CI, git state | none |
| `demo` | Run the bundled `citation-helper` example in plan-only mode | none |
| `forge` | Detect, scaffold, validate, evaluate, and optionally request install approval. Pass `--prefer-evolve` to route through `decide` first | install only with signed approval |
| `decide` | Given an opportunity, decide whether to evolve an installed skill or forge a new one. Returns `evolve` / `forge` / `ambiguous` plus per-candidate fitness | none |
| `evolve` | Propose a reviewed update from feedback + replay regression check | install only with signed approval |
| `install` | Print or apply an install proposal for a candidate skill | apply requires signed approval |
| `uninstall` | Print or apply uninstall / rollback | apply requires signed approval |
| `feedback` | Record redacted feedback for later evolution | writes feedback JSONL |
| `replay` | Score a skill directory against replay cases | none |
| `release-check` | Run release gates and secret scan | none |
| `version` | Print product version | none |

From the source repository, the most-used gates are also wrapped in `make`:

```bash
make doctor          # readiness check
make demo            # plan-only smoke test
make benchmark       # deterministic profile benchmarks
make package-check   # full release-checks + secret scan
```

For low-level scripts (direct invocation of `detect`, `generate_skill_scaffold`, `validate`, `propose_skill_install`, `telegram_approval`, `propose_skill_update`, `record_skill_feedback`, `evolve_skill_pipeline`, `replay/*`, nightly review, scheduling), see [`docs/manual-workflow.md`](docs/manual-workflow.md).

[^doctor]: `doctor` is the standard CLI verb for "diagnose local readiness" — it follows the convention established by `brew doctor`, `flutter doctor`, `npm doctor`, and `gem doctor` so any developer who's used those tools knows exactly what to expect.

---

## Operating modes

**Install modes** (`--install` for `forge` / `evolve`):

| Mode | Behavior |
| --- | --- |
| `plan` *(default)* | Print the install plan only. No mutation. |
| `telegram` | Send a Telegram approval request, then verify the signed token before any state change. |
| `ask` / `auto` | Blocked compatibility aliases. Local approvals cannot mutate skills. |

**Evaluation modes** (`--eval`):

| Mode | Behavior |
| --- | --- |
| `hidden` *(default)* | Run smoke checks; hide internal scenarios from user-facing output. |
| `details` | Developer mode; expose internal check details. |
| `off` | Skip evaluation. |

**Replay modes** (`--replay`):

| Mode | Behavior |
| --- | --- |
| `hidden` *(default for `evolve` and nightly review)* | Run replay checks; hide case details. |
| `off` | Skip replay. |

`--min-replay-improvement <N>` controls the regression gate (default `0` = no regression). Pass `-100` to disable.

---

## Configuration

Telegram approval reads these environment variables (with OpenClaw aliases):

| Purpose | Default env | Aliases |
| --- | --- | --- |
| Bot token | `TELEGRAM_BOT_TOKEN` | `OPENCLAW_TELEGRAM_BOT_TOKEN` |
| Chat ID | `TELEGRAM_CHAT_ID` | `OPENCLAW_TELEGRAM_CHAT_ID` |
| HMAC secret | `SKILL_FORGE_APPROVAL_SECRET` *(optional; falls back to bot-token-derived)* | — |

Discovery order — first present value wins:

1. Explicit `--env-file <path>`
2. `~/.openclaw/telegram.env`
3. `~/.openclaw/skill-forge.env`
4. `~/.openclaw/.env`
5. `~/.openclaw/workspace/telegram.env`
6. `~/.openclaw/workspace/.env`
7. Process environment variables

Approval reply words (case-insensitive, single-word, replies preferred over substring matches):

| Decision | Accepted words |
| --- | --- |
| Approve | `y`, `yes`, `approve`, `approved`, `同意`, `同意安装`, `安装`, `确认` |
| Reject | `n`, `no`, `reject`, `rejected`, `拒绝`, `拒绝安装`, `取消`, `不同意` |

For non-reply messages, the request ID printed in the approval message must appear in the body.

See [`docs/manual-workflow.md#config-discovery-order`](docs/manual-workflow.md) for nightly-review, env-file, and rollback details.

---

## Repository layout

```text
skill-forge/
├── README.md
├── SECURITY.md
├── RELEASE.md
├── LICENSE
├── Makefile
├── .env.example
├── assets/
│   └── skill-forge-logo.png
├── docs/
│   ├── manual-workflow.md
│   └── launch/                    # promotional / launch assets
├── tests/
│   └── run_release_checks.py
└── skill-forge/                   # the actual published skill
    ├── VERSION
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── examples/
    ├── references/
    └── scripts/
        ├── skill_forge.py         # Forge Console
        ├── forge_pipeline.py
        ├── detect_skill_opportunities.py
        ├── generate_skill_scaffold.py
        ├── validate_skill_candidate.py
        ├── evaluate_skill_candidate.py
        ├── lib/                   # approval, install_flow, runtime, telegram_config, policy
        ├── install/               # propose_skill_install + telegram_approval
        ├── evolve/                # propose_skill_update, record_skill_feedback, evolve_skill_pipeline
        ├── replay/                # collect / run / compare / redact / report
        ├── security/scan_secrets.py
        ├── somnia/                # nightly review runtime
        └── templates/profile_packs.py

../somnia/                          # optional companion skill, separate folder/repo
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/                        # thin shims that delegate to skill-forge/.../somnia
```

Backward-compatibility wrappers exist at `skill-forge/scripts/*.py` for every script under `install/`, `evolve/`, `replay/`, and `somnia/`.

---

## Release & contribution

Run the full release suite locally before publishing:

```bash
make package-check
# or:
python3 tests/run_release_checks.py
python3 skill-forge/scripts/security/scan_secrets.py --json
```

Two GitHub Actions workflows guard `main` and pull requests:

- **Release Checks** — runs the full 26+ assertion suite (compile, secret scan, validation, forge plan, console doctor/demo, install gate, signed-token positive path, tamper rejection, dry-run blocking, missing-source rejection, uninstall token gate, replay, somnia review).
- **Benchmarks** — deterministic profile benchmarks with score, line-count, and runtime budgets; uploads JSON artifacts.

See [`SECURITY.md`](SECURITY.md) for the full signed-gate protocol, dry-run rejection semantics, redactor coverage, and lock guarantees. See [`RELEASE.md`](RELEASE.md) for the release checklist.

Contributions are welcome via GitHub Issues and Discussions (announce-style "Skill Showcase" category for sharing skills you've forged). Please run `make package-check` before opening a PR.

---

## Companion skill: Somnia

`somnia` is a thin packaging layer that delegates to Skill Forge's nightly-review runtime via `runpy.run_path`. Use it when an agent should route maintenance work to a dedicated entry point (scheduled health reports, replay regression checks, sleep-hour upgrade proposals). Somnia never installs or replaces skills directly — any mutation goes through Skill Forge's signed-gate path.

Current Somnia version: `v0.6.0 "Quality Aligned"`.

---

## Recent versions

- `v1.4.0 "Evolve First"` — opt-in evolve-or-forge routing via new `decide` command and `forge --prefer-evolve` flag. Prevents skill sprawl by routing opportunities to existing installed skills when profile + trigger / topic / name overlap is high enough. Exact-name match short-circuits to fitness 1.0; profile mismatch is a hard gate. Synthetic feedback entries tagged `source=forge-routing` keep the audit timeline honest.
- `v1.3.0 "Benchmark Pipeline"` — deterministic benchmark cases for all 5 profiles; validation/eval/runtime budgets; `make benchmark`; dedicated GitHub Actions workflow with JSON artifacts.
- `v1.2.0 "Quality Refinement"` — scaffold descriptions stay anchored to user triggers; workflow section is now milestone-grade required; numbered-step bonus only counts inside the workflow section; case-insensitive extraneous-doc detection; `version` / `license` / `author` whitelisted in frontmatter.
- `v1.1.0 "Skill Quality Engine"` — lean `SKILL.md` bodies, progressive resource loading, execution-mode guidance, trigger-rich frontmatter, and validation that rejects context-bloating project docs.
- `v1.0.x "Forge Console"` — unified product CLI covering doctor, demo, forge, evolve, install, uninstall, feedback, replay, release-check, version.
- `v0.5.0 "Signed Gate"` — HMAC-signed approval tokens bound to skill identity and source content hash; replay non-regression gate; atomic + `flock`-locked manifest writes; expanded redactor.

For the full history (v0.1.0 → present), see [`RELEASE.md`](RELEASE.md) and the [GitHub Releases page](https://github.com/sheepxux/skill-forge/releases).

---

## License

MIT. See [`LICENSE`](LICENSE).
