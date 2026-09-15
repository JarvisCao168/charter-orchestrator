# Charter Orchestrator - developer Makefile (v3.3)
#
# Targets:
#   make test          - run the full suite (3.9/3.11/3.12 CI uses pytest directly)
#   make demo          - run the governed 10-stage demo
#   make demo-skill    - run a named skill's real module chain
#                        SKILL=<skill_id>   (e.g. make demo-skill SKILL=obs_09)
#                        SKILL=... JSON=1   (machine-readable output)
#   make list-skill    - list skills that have a bespoke end-to-end demo

PYTHON ?= python
SKILL  ?= obs_09

.PHONY: test demo demo-skill list-skill clean

test:
	$(PYTHON) -m pytest tests/ -q

demo:
	$(PYTHON) -m charter.cli demo

# One-shot demo of a single skill's real module chain
demo-skill:
	$(PYTHON) -m charter.demo_skill $(SKILL) $(if $(JSON),--json,)

list-skill:
	$(PYTHON) -m charter.demo_skill --list

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache charter_orchestrator.egg-info
