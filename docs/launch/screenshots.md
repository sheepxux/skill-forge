# Screenshot composition guide

Visual evidence the README and launch posts need:

| Asset | Where to use | Status |
| --- | --- | --- |
| `docs/launch/demo.gif` (terminal recording) | top of README, tweet 1, dev.to header | render via `vhs docs/launch/demo.tape` |
| `docs/launch/telegram-approval.png` | Show HN comment 1, tweet 4 | compose per below |
| `docs/launch/regression-blocked.png` | tweet 5 / blog post | compose per below |
| `docs/launch/architecture.svg` | optional, replaces the ASCII flow in README | export from Excalidraw |

Place rendered files under `docs/launch/`. **Do not commit raw screenshots that contain a real bot token, chat ID, or anyone's real name** — use the test bot or hand-redact in Preview before committing.

---

## 1. Telegram approval screenshot

The point of this screenshot is to make the human-in-the-loop tangible. Best composition: a side-by-side of (a) the macOS terminal showing `forge_pipeline.py` waiting for approval and (b) the Telegram chat showing the approval message + the `同意安装` reply.

### Setup

1. Create a dedicated test bot via `@BotFather` in Telegram. Use it only for screenshots.
2. Create a private 1:1 chat between the test bot and a throwaway personal account, or a fresh test group.
3. Put the test bot token in a temp env file:
   ```bash
   cat > /tmp/skill-forge-screenshot.env <<EOF
   TELEGRAM_BOT_TOKEN=<test bot token>
   TELEGRAM_CHAT_ID=<your test chat id>
   SKILL_FORGE_APPROVAL_SECRET=screenshot-only-secret
   EOF
   ```

### Capture

In one terminal window (size to ~120 cols × 32 rows):

```bash
python3 skill-forge/scripts/skill_forge.py forge \
  --output /tmp/screenshot-output \
  --target-root /tmp/screenshot-target \
  --install telegram \
  --env-file /tmp/skill-forge-screenshot.env \
  --agent-name StudyAgent \
  --json
```

The terminal will print the candidate path, validation, and then sit waiting on `getUpdates`. **At this exact moment**, take a Telegram screenshot of:
- the `Skill Forge 安装审批` message (the bot's prompt)
- your `同意安装` (or `yes`) reply

Then let the terminal finish — it will print `install_status: installed` and the manifest record. Take a second terminal screenshot of the final JSON.

### Compose

Use Preview.app, Pixelmator, or any image editor to:

1. **Crop** Telegram chat to just the approval message + your reply (target aspect ~3:4).
2. **Crop** terminal to the final 8-12 lines showing `install_status`, `approved_by`, `approval_request_id`.
3. **Stack horizontally** (terminal left, Telegram right) on a neutral background. Target output: 1600 × 900 PNG. Pad to 1200 × 630 if you need a tweet-card-ratio variant.
4. **Hand-redact** any real tokens, chat IDs, your phone number, profile photo. Replace with `[REDACTED]` in monospace. The point is the *flow*, not your real data.

Save to `docs/launch/telegram-approval.png`.

---

## 2. Regression-blocked screenshot

Shows what the replay non-regression gate looks like when the candidate would silently make a skill worse.

### Setup

You need an existing installed skill and a deliberately-worse update candidate:

```bash
# Install a baseline (using the screenshot env from above)
python3 skill-forge/scripts/skill_forge.py forge \
  --output /tmp/regression-output \
  --target-root /tmp/regression-target \
  --install telegram \
  --env-file /tmp/skill-forge-screenshot.env \
  --agent-name StudyAgent \
  --json

# Inject feedback with a clear trait expectation
python3 skill-forge/scripts/skill_forge.py feedback \
  --skill citation-helper --rating negative \
  --feedback "Skill should never invent references; cite missing-fields when metadata is incomplete" \
  --json

# Build a regressed candidate by stripping the relevant section
cp -R /tmp/regression-target/citation-helper /tmp/regressed-candidate
sed -i '' '/Never invent/,/missing-fields/d' /tmp/regressed-candidate/SKILL.md

# Run the regression compare directly
python3 skill-forge/scripts/replay/compare_replay_outputs.py \
  --baseline /tmp/regression-target/citation-helper \
  --candidate /tmp/regressed-candidate \
  --cases ~/.openclaw/workspace/.learnings/skill-replay-cases.jsonl \
  --skill citation-helper \
  --min-improvement 0 \
  --json
```

### Capture

Screenshot the JSON output. Highlight (rectangle annotation in Preview):

```json
"baseline_score": 100,
"candidate_score": 50,
"improvement":     -50,
"passed":          false        ← block the install
```

Save to `docs/launch/regression-blocked.png`.

---

## 3. Architecture diagram (optional, but worth it)

The ASCII diagram in README is fine but Excalidraw export is what makes it *look* designed. Source file at `docs/launch/architecture.excalidraw` (commit alongside the SVG so anyone can edit later).

Suggested layout:

```
┌──────────────┐  source-hash  ┌─────────────────────┐  signed token  ┌──────────────────────┐
│  candidate   │ ────────────▶ │ telegram_approval   │ ─────────────▶ │ propose_skill_install │
│  skill dir   │               │  (HMAC + Telegram)  │                │  --apply --token      │
└──────────────┘               └─────────────────────┘                └──────────┬───────────┘
                                                                                 │ verify all claims
                                                                                 ▼
                                                                ┌─────────────────────────┐
                                                                │ flock + atomic manifest │
                                                                │   write + audit row     │
                                                                └─────────────────────────┘
```

Export as SVG (`docs/launch/architecture.svg`), reference it from README in place of the ASCII block.

---

## Style notes

- **Don't add drop shadows or "Mac-style" window chrome** unless you really know what you're doing. They date fast and make screenshots feel like marketing.
- **Use a real terminal font** (Menlo / JetBrains Mono / SF Mono). Avoid system default sans-serif in any code-bearing image.
- **Prefer dark theme** for terminal screenshots; lighter themes wash out at thumbnail size.
- **Annotation color**: one accent (e.g. `#FF5555`) for highlight rectangles. Don't rainbow-coordinate.
- **Keep redaction obvious** (`[REDACTED]` in box) rather than blurry — readers should see "this was scrubbed" not "wait, what does that say".
