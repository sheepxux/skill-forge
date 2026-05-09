# Sign every install: how Skill Forge gates LLM-agent self-improvement

*~900 words. Suitable for personal blog, dev.to, Medium, or as the long-form companion to the Show HN.*

---

The default story for "self-improving LLM agents" goes like this: the agent notices it failed at something, it writes a new prompt or a new tool, and it adds that to its own skill set so it doesn't fail again. Every demo I've seen of this works. Every production deployment of this I've seen goes wrong in exactly one way: the agent silently overwrites a working skill with a worse one, and nobody notices for two weeks.

I built **Skill Forge** because the OpenClaw skill ecosystem I was actually using had this exact problem, and the existing fixes (manual review, "are you sure?" prompts, semver tags) all solve the wrong layer. The right fix is **package-management discipline at the install boundary**: every mutation needs a signed, content-bound approval, and every replace needs a regression check against what it's replacing.

This is a writeup of the two design choices that took the most iteration: the install gate and the regression check.

## Why a flag isn't a gate

The first version of the install path looked like every other "approval" system you've ever seen:

```python
parser.add_argument("--approved-by-telegram", action="store_true",
                    help="Required safety marker for mutations after Telegram approval.")
```

I wrote it, shipped it, and felt great for about an hour before it dawned on me that the entire safety story was a single CLI flag away from collapsing. Anyone — including the agent itself, including a future me who'd forgotten the contract — could call `propose_skill_install.py --apply --approved-by-telegram` and skip Telegram entirely. The audit field would record `approved_by: "telegram"` because the flag said so. The flag *was* the contract.

The fix is a signed approval token whose claims include everything the install needs to verify. In Skill Forge today, `telegram_approval.py` issues an HMAC-SHA256 token whose payload covers:

```json
{
  "request_id": "...",
  "skill": "citation-helper",
  "target": "/Users/.../skills/citation-helper",
  "method": "symlink",
  "source_dir": "/Users/.../generated/citation-helper",
  "source_hash": "sha256 of the candidate dir contents",
  "mode": "telegram",
  "issued_at": 1730_000_000,
  "expires_at": 1730_001_800
}
```

`propose_skill_install.py --apply --approval-token <token>` recomputes the HMAC, checks the expiry, and verifies every claim against the install it's about to perform. There is no "did the user pass `--approved-by-telegram`" check anymore. The token *is* the gate.

The `source_hash` is the part that took the longest to design. The naive version is "hash the candidate directory and put the hash in the token; refuse the install if the on-disk hash doesn't match." That works, but it makes a swap trivial: just edit any file under the candidate, the SHA changes, the install is refused. Which is exactly what you want — a malicious agent can't approve a benign candidate via Telegram and then quietly substitute a poisoned one before `--apply`.

A subtler trade-off: the HMAC secret. If `SKILL_FORGE_APPROVAL_SECRET` isn't set, the secret falls back to `sha256("skill-forge-approval:" + bot_token)`. That's deliberately deterministic so any environment with the bot token can verify tokens issued there, but it means the bot token's blast radius now includes "issue install approvals." For solo developer setups this is fine (you control both); for shared bots, set the explicit secret. I document this honestly because pretending it's not a trade-off is the failure mode I'm trying to prevent for everyone else.

Dry-run tokens explicitly carry `mode=dry-run` and are refused by `--apply` unless `--allow-dry-run-install` is passed; in that case the audit field becomes `approved_by=dry-run`, not `telegram`. The previous version of this flow happily wrote `approved_by=telegram` when `--telegram-dry-run approve` was used, and the release-check suite *asserted* that as expected behavior. Encoding the bypass into the test was an ugly thing to discover after the fact.

## A regression gate that doesn't need an API key

The other thing I kept getting wrong was "did this update actually make the skill better?" Most agent toolchains don't try to answer this; they assume any human-approved update is an improvement. In practice, an "approved" update can easily score worse than the thing it replaces.

Skill Forge runs a deterministic, offline replay scoring pass on both the candidate and the installed baseline against the same redacted feedback cases, then blocks the install when `candidate_score - baseline_score < --min-replay-improvement` (default 0). The cases themselves are auto-built from feedback events (`record_skill_feedback.py` writes them, `collect_replay_cases.py` redacts and groups them).

The "scoring" is keyword/coverage based — does the candidate's SKILL.md mention the trait expected by the case. That's not a true behavioral replay; it can't catch logic regressions. But it runs in milliseconds, requires no API key, and reliably catches the most common regression: someone deleted the section that addressed the user's original complaint. For the higher-fidelity case I'd plug in an LLM-judge mode behind a flag, but I haven't needed it yet.

## What's actually in the box

- A unified Forge Console (`scripts/skill_forge.py`) covering doctor, demo, forge, evolve, install, uninstall, feedback, replay, release-check, version
- Profile-aware scaffolds for academic / product / integration / script / workflow with bundled references and per-profile quality gates
- A quantitative validator that scores frontmatter, sections, triggers, references, and profile-specific behavior; capped at 89 if any single category falls short, capped at "draft" if any error
- A flock-protected, atomically-written manifest with full version history and rollback support
- Aggressive feedback redaction (emails, JWTs, PEM private keys, Telegram bot tokens, AWS/Google/GitHub/Slack token prefixes, IPv4/v6, separator-bearing phone numbers)
- A deterministic benchmark pipeline so quality gates don't drift between releases
- 26+ release-check assertions including positive-path install with a real signed token, tampered-source rejection, dry-run blocking, and missing-source rejection at both token-issuance and install-apply stages

Python 3.9+, no third-party dependencies, MIT.

## Where to find it

- **Repo**: https://github.com/sheepxux/skill-forge
- **ClawHub**: `clawhub install skills-forge`

If you're building agent-skill marketplaces, the install-gate pattern is portable. Steal it freely. The thing I'd most like other registries to copy is the source-hash binding — without it, a signed approval is just a checkmark.

If you have feedback (especially on the HMAC secret-derivation trade-off, the keyword-based replay scoring, or the profile coverage), the GitHub Discussions tab is open.
