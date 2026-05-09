PYTHON ?= python3
CONSOLE := skill-forge/scripts/skill_forge.py

.PHONY: version doctor demo release-check benchmark secret-scan package-check

version:
	$(PYTHON) $(CONSOLE) version

doctor:
	$(PYTHON) $(CONSOLE) doctor --json

demo:
	$(PYTHON) $(CONSOLE) demo --json

release-check:
	$(PYTHON) $(CONSOLE) release-check --json

benchmark:
	$(PYTHON) tests/run_benchmarks.py --json

secret-scan:
	$(PYTHON) skill-forge/scripts/security/scan_secrets.py --json

package-check: release-check benchmark secret-scan
