# Contributing to Skill Forge

Thanks for considering a contribution. This project takes its safety story seriously, so the contribution flow is intentionally narrow but predictable.

## Before you open an issue or PR

- **Did you find a bug?** Open a GitHub Issue with the exact command, the JSON output, and the version (`python3 skill-forge/scripts/skill_forge.py version`).
- **Do you have a question?** Use [GitHub Discussions](https://github.com/sheepxux/skill-forge/discussions) — Q&A category. Issues are reserved for actionable defects.
- **Did you find a security vulnerability?** Do **not** open an Issue or Discussion. Follow [`SECURITY.md`](SECURITY.md).
- **Are you proposing a new feature or design change?** Open a Discussion in the *Design Discussion* category first. The signed-gate and replay-gate designs took several iterations; we'd rather think together before code lands.

## Local setup

```bash
git clone https://github.com/sheepxux/skill-forge.git
cd skill-forge

# Optional: copy the example env file for Telegram approval testing
cp .env.example ~/.openclaw/skill-forge.env
```

No `pip install` is required — Skill Forge has zero third-party Python dependencies. Python 3.9+ is the only requirement.

## Run the gates before opening a PR

```bash
make package-check
```

This runs:

1. `python3 -m py_compile` over every script
2. The full release-checks suite (currently 26+ assertions)
3. `scan_secrets.py` over the whole repository

PRs that don't pass `make package-check` will fail CI. If you can't run `make` locally, the equivalent commands are in [`RELEASE.md`](RELEASE.md).

To regenerate the deterministic benchmark results:

```bash
make benchmark
```

## Code style and constraints

- **Python 3.9 compatible.** Don't use 3.10+ syntax (no `match`, no `X | Y` unions outside `from __future__ import annotations`).
- **No third-party dependencies.** The whole point of the local-first design is that `python3` and the standard library are enough. If you genuinely need a new dep, raise it in a Design Discussion first.
- **Every CLI script accepts `--json`** and emits a single top-level JSON object on stdout when in JSON mode. Errors go to stderr; the script exits non-zero on failure.
- **Every script that mutates state requires a signed approval token.** No `--force` overrides, no boolean "approved=true" shortcuts. If you're tempted to add one, that's a sign the design is wrong, not the policy.
- **Backwards compatibility for the Forge Console.** Subcommand names, flags, and JSON output shapes are stable across minor versions. Breaking them requires a major bump.

## Adding a new skill profile

If you want to add a 6th profile (alongside `academic` / `product` / `integration` / `script` / `workflow`):

1. Open a Design Discussion. Profiles are part of the public surface; we prefer to think the contract through together.
2. Add the profile to `skill-forge/scripts/templates/profile_packs.py` with `default_triggers`, `interface`, `workflow`, `output_contract`, `quality_gates`, `references`, and optionally `scripts`.
3. Add a profile-specific check to `skill-forge/scripts/validate_skill_candidate.py` under `PROFILE_KEYWORDS` and the per-profile validation block.
4. Extend `tests/run_release_checks.py` `check_profile_golden_scaffolds` with a golden case that scores ≥ 85.
5. Update `references/skill-quality-rubric.md` if the profile changes scoring expectations.

## Adding a release-check assertion

`tests/run_release_checks.py` is the project's truth source for "does this still work". Bias toward adding a check whenever you fix a real bug — it's cheap and prevents regression.

A check is just a function that calls scripts via `subprocess.run` (or directly imports library helpers), parses the JSON output, and uses `assert_true(condition, message)`. Register it in `main()`'s `checks` list with a short stable name.

## Commit messages

- Imperative mood: "Add X", "Fix Y", "Tighten Z" — not "Added", "Fixes".
- Reference issues with `Fixes #123` when applicable.
- For multi-file changes, write a short body explaining *why*, not *what* (the diff already shows what).

## Code of conduct

Be specific. Be respectful. Assume good faith. If you wouldn't say it in a small in-person meeting, don't say it in an Issue or PR. Maintainers reserve the right to lock conversations that turn unproductive.

## What we're explicitly not looking for

- LLM-judge dependencies in the core path (the offline keyword scoring is a feature, not a placeholder)
- Web framework integrations bundled in the main package (those belong in `examples/integrations/`)
- Telemetry or analytics (the local-first stance is intentional)
- Auto-install / silent-update modes that bypass the signed gate

If your idea touches any of these, we still want to hear it — open a Design Discussion and explain the use case. We're open to changing our minds, just slowly and in writing.

---

Thanks for helping make agent skill management less of a Wild West.
