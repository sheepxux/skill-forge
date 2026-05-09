# Show HN draft

## Title (≤80 chars; HN truncates above this)

> Show HN: Skill Forge – Signed-approval gate for self-improving LLM agents

Alternate, slightly less-tech-bro variants:

- `Show HN: Skill Forge – HMAC-gated install pipeline for LLM agent skills`
- `Show HN: Skill Forge – package-management discipline for LLM agent capabilities`

## Body (700-900 words; HN sweet spot)

Hi HN — I built Skill Forge because every "self-improving agent" demo I've seen quietly skips the part where you'd want a human to approve what's about to be installed into the agent's runtime.

Skill Forge sits in front of an OpenClaw-style skill folder and turns the lifecycle into a signed pipeline:

```
detect (from .learnings + error logs)
  ↓
decide (evolve an installed skill, or forge new?)   ← v1.4.0+, opt-in
  ↓
generate (profile-aware scaffold)
  ↓
validate (quantitative score + rubric)
  ↓
evaluate (hidden smoke checks)
  ↓
install   ← gated by signed approval token
  ↓
evolve    ← gated again, plus replay non-regression
```

The three pieces I want feedback on are the install gate, the regression check, and the evolve-first router. All three started as throwaway prototypes and ended up being the whole product.

**Install gate.** Every install or replace requires an HMAC-SHA256 token issued by `telegram_approval.py`. The token's claims are bound to:

- skill name
- target install path
- install method (symlink / copy)
- candidate source path
- a SHA-256 hash of the source directory's contents
- request id, mode (`telegram` / `dry-run`), issued_at, expires_at

`propose_skill_install.py --apply` verifies the signature, the expiry, and every claim against the install it's about to perform. There is no boolean "I-promise-this-was-approved" flag — the token *is* the gate. Tamper with the candidate after approval and the SHA changes, the claim mismatches, and the install is blocked. Dry-run-mode tokens explicitly carry `mode=dry-run` and are refused unless `--allow-dry-run-install` is passed; in that case the audit field becomes `approved_by=dry-run`, not `telegram`. The HMAC secret comes from `SKILL_FORGE_APPROVAL_SECRET` if set, otherwise it's derived deterministically from the bot token (so any environment that can reach the bot can verify tokens issued there).

I started with the usual "approved=True" boolean and felt clever for about an hour before realizing the entire safety story was one CLI flag away from collapsing.

**Replay non-regression.** When an installed copy of the skill already exists, the evolution pipeline scores both the candidate and the installed baseline against the same redacted feedback cases, and blocks the install when `candidate_score - baseline_score < --min-replay-improvement` (default `0`). This is offline keyword/coverage scoring, not an LLM-in-the-loop eval — fast, deterministic, no API key. The replay cases themselves are auto-built from feedback events and aggressively redacted (emails, JWTs, PEM private keys, Telegram bot tokens, common cloud / Git / Slack token prefixes, IPv4/IPv6, separator-bearing phone numbers).

**Evolve-first router (v1.4.0).** The thing that turned this from "interesting safety primitive" into "actually usable in production" was realizing that without sprawl prevention you end up with twelve near-duplicate citation skills after three weeks. So I added `decide_skill_action.py`: given a detected opportunity, score every installed skill on (profile-match, trigger overlap, topic overlap, name overlap), and route to evolve when the top score clears 0.45 with a clear margin over second place. Profile match is a hard gate (cross-profile evolution is almost always wrong). Exact-name match short-circuits to fitness 1.0 — when the user names their request the same as something they've already installed, the answer is obvious. When the router triggers an evolve, it writes a synthetic feedback entry tagged `source=forge-routing` so the audit timeline stays honest about *why* the evolution happened. Default off in 1.x via `--prefer-evolve`; will become default in 2.0 once the threshold has real-world calibration data. The replay non-regression gate above is the safety net — even if the router routes wrong, a degrading evolution gets blocked at install time.

**Other things I'd find boring on someone else's launch but won't pretend aren't useful.** Atomic + flock-protected manifest writes. Proper audit trail with version history and rollback. Profile-specific scaffolds for academic / product / integration / script / workflow with bundled references and per-profile quality gates. A unified Forge Console (`scripts/skill_forge.py`) covering doctor / demo / forge / decide / evolve / install / uninstall / feedback / replay / release-check / version. 32 release-check assertions including positive-path install with a real signed token, tampered-source rejection, dry-run blocking, signed-approval coverage, and the four routing-contract checks (similar→evolve, novel→forge, profile-mismatch→hard-gate, ambiguous→flagged). Deterministic benchmark suite with per-profile score / runtime budgets gated in CI so quality doesn't drift between releases.

**Tech stack:** Python 3.9+, no third-party deps, MIT, ~5k LOC. Runs entirely locally. Telegram is the approval channel because that was the smallest thing that gave me human-in-the-loop without standing up a webserver.

**What it deliberately is not:** another LangChain skill marketplace. Skill Forge is the *gate* you put in front of one — it's complementary to LangChain Hub / AutoGen / your own internal registry.

**Where I'd love sharper feedback:**

1. The HMAC secret derivation. If `SKILL_FORGE_APPROVAL_SECRET` isn't set, the secret falls back to `sha256("skill-forge-approval:" + bot_token)`. That's deliberately deterministic so any environment with the bot token can verify, but it means the bot token's blast radius includes "issue install approvals." Is that the right trade?

2. The replay coverage check is keyword-based (does the candidate's SKILL.md mention the trait expected by the case). It catches obvious regressions and runs in milliseconds, but it's not a true behavioral replay. Is the speed-vs-fidelity trade defensible, or should I add an optional LLM-judge mode?

3. Profile coverage. I shipped 5 profiles (academic / product / integration / script / workflow). Anything obviously missing for your own skill use cases?

4. The evolve-first router's fitness weights (trigger 0.7, topic 0.2, name 0.1) and threshold (0.45) are calibrated on synthetic + my own use, not large-scale data. The exact-name short-circuit feels right but might be too aggressive when users name skills generically. Default-off in 1.x to gather signal; planning to flip default in 2.0. Would love to hear thresholds people land on after a few weeks of use.

Repo: https://github.com/sheepxux/skill-forge
ClawHub: https://clawhub.ai/sheepxux/skills-forge

Happy to answer detailed questions about any of the design decisions, or about why I think most agent-skill registries are going to learn this lesson the hard way.

## Posting tips

- **Best window:** Tue/Wed/Thu, ~06:00–09:00 Pacific. Avoid Friday and weekends; HN traffic dies.
- **Don't pre-vote / pre-promote.** HN shadow-bans accounts that ring up early upvotes from the same network.
- **Be in the thread for the first 4 hours.** Reply to every substantive comment. The early-comment-velocity signal is what gets you to the front page.
- **Have one screenshot or asciinema link in the first comment**, not in the post body — HN's mobile rendering is hostile to images in the OP.
- **If you mention competitors (LangChain etc.), be respectful and specific.** "Different problem, complementary tool" lands better than "X but better."
