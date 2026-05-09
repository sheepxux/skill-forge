# Getting help

## Where to ask

| Question type | Where | Expected response |
| --- | --- | --- |
| **"How do I…?"** | [GitHub Discussions → Q&A](https://github.com/sheepxux/skill-forge/discussions) | Best-effort within 48 hours |
| **"This is a bug"** | [GitHub Issues](https://github.com/sheepxux/skill-forge/issues) | Triaged within 48 hours; severity-labeled |
| **"This is a feature idea"** | [GitHub Discussions → Design Discussion](https://github.com/sheepxux/skill-forge/discussions) | Best-effort within 1 week |
| **"I forged something cool"** | [GitHub Discussions → Skill Showcase](https://github.com/sheepxux/skill-forge/discussions) | Maintainer reads + reactions; community comments |
| **Security vulnerability** | See [`SECURITY.md`](SECURITY.md). **Do not file public issues for security bugs.** | Acknowledged within 72 hours; fix or advisory plan within 14 days |

## Triage labels

Issues get one of these labels within the SLA above:

- `bug:critical` — data loss, signed-gate bypass, or production-impacting failure. We aim for a patch release within 7 days.
- `bug:high` — something is broken in a documented flow. We aim for a patch release within 30 days.
- `bug:low` — minor or cosmetic. Batched into the next minor release.
- `question` — moved to Discussions when appropriate.
- `wontfix` — outside scope or contradicts the safety stance (the issue thread will explain why).
- `good-first-issue` — small, well-scoped, real-value tasks for newcomers.

## What you can expect us not to do

- We don't run a hosted version. Skill Forge is a local-first tool by design.
- We don't add LLM-judge dependencies to the default replay scoring (it's offline, deterministic, and that's a feature). An optional LLM-judge mode behind a flag is on the table — open a Design Discussion if you want to explore it.
- We don't accept silent auto-install modes that bypass the signed gate. The whole product is the gate.
- We don't offer paid SLAs or commercial support. For bigger asks, fork the project — that's why it's MIT.

## Before opening an issue

Run `python3 skill-forge/scripts/skill_forge.py doctor --json` and paste the output. Most environment-related issues self-resolve once you can see what `doctor` sees.

If `doctor` is happy and the bug is reproducible, also include:

- The exact command you ran
- The exact JSON output (copy-paste, do not summarize)
- The Skill Forge version (`skill_forge.py version`)
- Your OS and Python version

## Discussions etiquette

- Search before posting. The same question is usually answered.
- Title your post like a sentence ("Why does dry-run install create the target directory?"), not a stub ("dry run").
- Mark the answer that solved your problem (Discussions → Mark as answer) so the next person finds it fast.
