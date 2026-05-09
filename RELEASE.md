# Release Checklist

Run before publishing:

```bash
make package-check
```

If `make` is unavailable, run:

```bash
python3 tests/run_release_checks.py
python3 tests/run_benchmarks.py --json
python3 skill-forge/scripts/security/scan_secrets.py --json
```

GitHub Actions runs release checks and deterministic benchmarks on `main` pushes and pull requests. Treat either workflow failing as a release blocker.

Manual checks:

- Confirm `skill-forge/VERSION` matches the intended release.
- Confirm `.env.example` contains placeholders only.
- Confirm no generated candidate directories are present.
- Confirm real API keys and Telegram tokens have been rotated if they were ever exposed elsewhere.
- Confirm golden scaffold checks cover `academic`, `product`, `integration`, `script`, and `workflow`.
- Confirm benchmark results pass validation, hidden-eval, line-count, and runtime budgets.

Release tag:

```bash
git tag v1.4.0
```

Published package slugs:

- ClawHub: `skills-forge`
- Optional companion: `somnia` (released separately)

---

## Version history

- `v0.1.0` — detect, generate, validate, install plan.
- `v0.2.0` — hidden eval, approval flow, feedback evolution, version history.
- `v0.3.0 "Somnia"` — nightly review, LaunchAgent scheduling, module boundaries.
- `v0.4.0 "Replay"` — redacted replay cases, replay scoring, regression gate.
- `v0.4.1 "Somnia Split"` — standalone Somnia skill package, module cleanup.
- `v0.4.2 "Telegram Gate"` — mandatory Telegram approval for install mutations.
- `v0.4.3 "Safety Tightening"` — safe skill slug containment for evolution updates.
- `v0.5.0 "Signed Gate"` — HMAC-signed approval tokens bound to skill identity and source content hash; missing or non-skill sources refused before token issuance and install mutation; dry-run approvals can no longer install or claim Telegram audit; replay regression gate compares candidate against installed baseline; manifest writes are atomic and `flock`-locked; redactor covers IPv4/v6, phone numbers, JWTs, common cloud/Git tokens, Telegram bot tokens, and PEM private keys.
- `v1.0.0 "Forge Console"` — product-level command surface (doctor, demo, forge, evolve, install, uninstall, feedback, replay, release-check, version); release checks cover the console smoke path.
- `v1.0.1 "Forge Console Patch"` — normalize console JSON pass-through for `demo`; remove duplicate console shim; expose install/uninstall bot-token env forwarding; clarify doctor secret source; avoid duplicate source-repo secret scans.
- `v1.1.0 "Skill Quality Engine"` — generated skills use lean SKILL.md bodies, explicit progressive resource loading, execution-mode guidance, stronger frontmatter trigger descriptions, and validation that rejects README/CHANGELOG-style docs that bloat agent context.
- `v1.1.1` — case-insensitive extraneous-docs gate covering `readme.md`, `INSTALL.md`, `Setup.md`, `QUICKSTART.md`, and 10 other variants; release suite asserts the bypass is closed.
- `v1.2.0 "Quality Refinement"` — scaffold descriptions stay anchored to user-supplied triggers (profile defaults only top up when the user under-specifies); workflow section is now a milestone-grade requirement (cap 89 if missing); the numbered-step bonus only counts steps inside the workflow section so Quality-Gates lists no longer compensate; `version`, `license`, and `author` are recognized as legitimate frontmatter keys without capping the score.
- `v1.3.0 "Benchmark Pipeline"` — adds deterministic benchmark cases for academic, product, integration, script, and workflow scaffolds; enforces validation/evaluation/runtime budgets; adds `make benchmark`; wires benchmark results into a dedicated GitHub Actions workflow with uploaded JSON artifacts.
- `v1.4.0 "Evolve First"` — adds opt-in evolve-or-forge routing. New `scripts/decide_skill_action.py` computes a fitness score (profile match as a hard gate; weighted sum of trigger / topic / name overlap; exact-name match short-circuits to 1.0) for each installed skill and returns one of `evolve` / `forge` / `ambiguous`. New Forge Console subcommand `decide` exposes the router directly. `forge_pipeline.py --prefer-evolve` (default off in 1.x) routes an opportunity through `decide` and, when it matches an installed skill, writes a synthetic feedback entry tagged `source=forge-routing` and dispatches `evolve_skill_pipeline.py` instead of forging a new skill. Six new release checks lock the routing contract: `decide-routes-to-evolve-when-similar`, `decide-routes-to-forge-when-novel`, `decide-respects-profile-mismatch`, `decide-flags-ambiguous-when-tied`, `forge-pipeline-prefer-evolve-routes`, `forge-pipeline-default-does-not-route`. The replay non-regression gate downstream catches any mis-routing.
