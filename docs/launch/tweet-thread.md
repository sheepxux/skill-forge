# Launch tweet thread — Skill Forge v1.4.0

## One-tweet hook (use alone if you don't want a thread)

> Most "self-improving agent" demos quietly skip the part where a human approves what's about to be installed into the agent's runtime — *and* skip the part where you'd want to evolve an existing skill instead of forging the 12th near-duplicate.
>
> Built Skill Forge to fix both. HMAC-signed install gate, evolve-first router, replay non-regression check, full audit trail. MIT.
>
> https://github.com/sheepxux/skill-forge

## Full thread (8 tweets, ~280 chars each)

**1/ hook**

> Most "self-improving agent" tools let the agent silently install its own skills. That's a demo, not a product.
>
> I built Skill Forge: every install or update goes through a signed approval token, bound to the candidate's content hash. Tamper after approval → blocked.
>
> 🧵

**2/ what it does**

> detect (from .learnings + error logs) → decide (evolve or forge?) → generate → validate → install (signed gate) → evolve (replay non-regression)
>
> All local Python 3.9, no third-party deps, MIT.

**3/ the install gate**

> The token's HMAC claims include skill name, target path, install method, source path, and SHA-256 of the source dir.
>
> propose_skill_install.py --apply verifies every claim. There is no "approved=True" boolean — the token is the gate.

**4/ the regression check**

> When an installed copy already exists, the candidate is scored against the same redacted feedback cases as the baseline.
>
> Block when candidate_score - baseline_score < 0.
>
> Offline, deterministic, no API key. Catches "we accidentally made it worse" before it ships.

**5/ evolve-first router (v1.4.0)**

> "Self-improving" without sprawl prevention = 12 near-duplicate citation skills after 3 weeks.
>
> Solution: route every detected gap through `decide` first. Same profile + trigger/topic/name overlap above threshold → evolve the existing skill instead of forging a new one.
>
> Profile mismatch is a hard gate. Replay regression check is the safety net if routing is wrong.

**6/ privacy**

> Feedback gets redacted before it touches disk: emails, JWTs, PEM private keys, Telegram bot tokens, AWS/Google/GitHub/Slack token prefixes, IPv4/v6, separator-bearing phone numbers.
>
> Manifest writes are atomic + flock-protected. Full audit trail with rollback.

**7/ how it's different**

> Not another LangChain skill marketplace. Skill Forge is the *gate* you put in front of one.
>
> Comparison table covering Skill Forge vs LangChain Hub / AutoGen / OpenAI Apps SDK / manual prompt files in the README.

**8/ try it**

> ClawHub: clawhub install skills-forge
> GitHub: https://github.com/sheepxux/skill-forge
>
> 30-second smoke test:
>   make doctor
>   make demo
>
> Feedback on the HMAC secret derivation + evolve-router fitness threshold especially welcome.

## Asset checklist for the thread

- **Tweet 1**: GIF or screenshot of the Telegram approval flow (most thumb-stopping). If you don't have one, a terminal screenshot of `make demo` output with `install_status: planned` highlighted works.
- **Tweet 3**: Snippet of a verified token's claims JSON.
- **Tweet 4**: Screenshot of a regression-blocked install showing baseline=100 / candidate=50 / blocked.
- **Tweet 5**: Screenshot of `decide --json` output showing `decision: evolve / target_skill: citation-helper / fitness: 1.0` with the reasoning block (exact_name_match: true). Visualises the routing decision concretely.
- **Tweet 7**: Screenshot of the README comparison table.
- **Tweet 8**: 10-second asciinema or screen recording of `make demo`.

## Who to @ in the thread

- @simonw (Simon Willison) — historically retweets agent + supply-chain-safety angles
- @soumithchintala — agent infra
- @swyx — pythonista / AI engineer audience
- @hwchase17 (LangChain) — be respectful, don't position as competitor; "complementary, would love feedback on the gate pattern"
- @latentspacepod — agent tooling coverage

## Don't

- Don't post during US sleep hours unless you want the thread to die
- Don't quote-RT yourself for visibility — engagement nuke
- Don't post alongside drama threads (algorithm penalizes mixed context)

Best window: Tue/Wed/Thu ~10:00 ET / 7:00 PT.
