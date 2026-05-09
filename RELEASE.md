# Release Checklist

Run before publishing:

```bash
make package-check
```

If `make` is unavailable, run:

```bash
python3 tests/run_release_checks.py
python3 skill-forge/scripts/security/scan_secrets.py --json
```

GitHub Actions runs the same release checks on `main` pushes and pull requests. Treat a failing workflow as a release blocker.

Manual checks:

- Confirm `skill-forge/VERSION` matches the intended release.
- Confirm `.env.example` contains placeholders only.
- Confirm no generated candidate directories are present.
- Confirm real API keys and Telegram tokens have been rotated if they were ever exposed elsewhere.
- Confirm golden scaffold checks cover `academic`, `product`, `integration`, `script`, and `workflow`.

Release tag:

```bash
git tag v1.1.0
```

Published package slugs:

- ClawHub: `skills-forge`
- Optional companion: `somnia` (released separately)
