.PHONY: init smoke hooks-test ledger-replay reproduce contract-check decorative-check glossary-lint headline-check kernel-image exec-image paper

UV ?= uv

init:            ## git identity, hooks path, uv sync
	git config user.name "SharathSPhD"
	git config user.email "qbz506@york.ac.uk"
	git config core.hooksPath .githooks
	chmod +x .githooks/*
	$(UV) sync --all-groups

smoke:           ## TECHNICAL closure without GPU
	$(UV) run python scripts/import_guard.py
	$(UV) run ruff check pravrudhi_kernel src tests scripts
	$(UV) run mypy pravrudhi_kernel/src src
	$(UV) run pytest -q

hooks-test:
	$(UV) run pytest tests/governance -q

contract-check:  ## usage: make contract-check GATE=gates/gate_L0.json
	$(UV) run pravrudhi gate check $(GATE)

paper:
	$(MAKE) -C paper

ledger-replay:   ## rebuild state.json from the ledger and verify the chain and byte-equality
	$(UV) run pravrudhi replay --verify
reproduce:
	@echo "not implemented: L3" >&2; exit 2
decorative-check:  ## decorative-controller check on the last select batch (research/last_select.json)
	$(UV) run python scripts/decorative_check.py --batch research/last_select.json
glossary-lint:
	@echo "not implemented: P2" >&2; exit 2
headline-check:
	@echo "not implemented: L5" >&2; exit 2
kernel-image:
	@echo "not implemented: L3" >&2; exit 2
exec-image:
	@echo "not implemented: L3" >&2; exit 2
