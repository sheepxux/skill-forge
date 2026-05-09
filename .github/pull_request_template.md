## Summary

Describe the change and why it is needed.

## Validation

- [ ] `make package-check`
- [ ] `python3 tests/run_benchmarks.py --json`
- [ ] `python3 skill-forge/scripts/security/scan_secrets.py --json`

## Safety

- [ ] No real tokens, API keys, chat IDs, or private workspace paths were added.
- [ ] Install/update mutations still require signed approval tokens.
- [ ] Replay or benchmark behavior is updated if quality gates changed.

## Compatibility

- [ ] Forge Console command names, flags, and JSON output shapes remain backward-compatible, or the version bump explains the breaking change.
