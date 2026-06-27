# v2 orchestration — thin wrappers over uv + pytest so the end-to-end commands are
# discoverable and identical across sessions. Phase targets (eval/train/export) are
# added as their modules are filled in at each phase startup.
#
# Conventions:
#   - .venv-ft is the single venv (cu124 torch + pymavlink).
#   - uv is user-local at ~/.local/bin/uv. `lock` regenerates the pinned set.

UV := $(HOME)/.local/bin/uv
PY := .venv-ft/bin/python

.PHONY: help test lock sync dev env-ft

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test:  ## Run the contract + manifest test suite
	$(PY) -m pytest

env-ft:  ## Create .venv-ft if missing (does not install)
	test -d .venv-ft || python -m venv .venv-ft

sync:  ## Reproduce the exact GPU env from the lock (uv pip sync)
	$(UV) pip sync --python $(PY) requirements-ft.lock.txt

dev:  ## Install dev/test tooling on top of .venv-ft
	$(UV) pip install --python $(PY) pytest==9.1.0

lock:  ## Regenerate requirements-ft.lock.txt from the live .venv-ft
	@echo "# regenerate after editing requirements-ft.txt + applying changes"
	$(UV) pip freeze --python $(PY) > /tmp/ft_freeze_new.txt
	@echo "review /tmp/ft_freeze_new.txt, then merge pins into requirements-ft.lock.txt"
