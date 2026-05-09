# Skill Forge demo recording — vhs tape file
#
# Install vhs once:
#   brew install vhs
#   # or: go install github.com/charmbracelet/vhs@latest
#
# Render the GIF (run from the repo root):
#   vhs docs/launch/demo.tape
# Output: docs/launch/demo.gif (≈ 800 KB, 30 seconds)
#
# To record a faster, smaller variant for tweets:
#   vhs docs/launch/demo.tape --output docs/launch/demo-small.gif
#   gifsicle -O3 --colors 128 docs/launch/demo.gif -o docs/launch/demo-small.gif
#
# Place the rendered GIF at docs/launch/demo.gif and reference it from README:
#   <p align="center"><img src="docs/launch/demo.gif" alt="Skill Forge demo" width="720"></p>

Output docs/launch/demo.gif

Set FontSize 14
Set Width 1200
Set Height 760
Set Theme "Dracula"
Set TypingSpeed 40ms
Set PlaybackSpeed 1.0
Set Padding 20

# ── Scene 1 — readiness check (5s) ──────────────────────────────────
Type "make doctor"
Sleep 500ms
Enter
Sleep 5s

# ── Scene 2 — plan-only demo (10s) ──────────────────────────────────
Type "clear"
Enter
Sleep 200ms

Type "make demo 2>&1 | python3 -c \"import json,sys; d=json.loads(sys.stdin.read().split('{',1)[0].rsplit('}',0)[0] if False else sys.stdin.read()); print()\" || true"
Sleep 200ms
# Simpler real call: use the console directly so the JSON is parseable.
Ctrl+u
Type "python3 skill-forge/scripts/skill_forge.py demo --json | python3 -c \"import json,sys; d=json.load(sys.stdin); print('install_status:', d['install_status']); print('grade        :', d['validation']['grade']); print('score        :', d['validation']['score']); print('skill_dir    :', d['skill_dir'])\""
Enter
Sleep 8s

# ── Scene 3 — dry-run signed approval is BLOCKED (8s) ───────────────
Type "clear"
Enter
Sleep 200ms

# Show that --telegram-dry-run approve does NOT install, even with approval=true.
Type "SKILL_FORGE_APPROVAL_SECRET=demo python3 skill-forge/scripts/skill_forge.py forge --output ./generated-demo --install telegram --telegram-dry-run approve --agent-name StudyAgent --json | python3 -c \"import json,sys; d=json.load(sys.stdin); print('install_status:', d['install_status']); print('mode         :', (d.get('approval') or {}).get('approval_claims',{}).get('mode')); print('mutated      :', d['install_plan'].get('installed', False))\""
Enter
Sleep 8s

# ── Scene 4 — outro (3s) ────────────────────────────────────────────
Type "clear"
Enter
Type "echo 'Skill Forge — signed-approval skill pipeline'"
Enter
Sleep 500ms
Type "echo 'github.com/sheepxux/skill-forge   |   clawhub install skills-forge'"
Enter
Sleep 3s
