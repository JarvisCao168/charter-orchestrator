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

.PHONY: test demo demo-skill list-skill stress stress-big stress-ci clean

test:
	$(PYTHON) -m pytest tests/ -q

demo:
	$(PYTHON) -m charter.cli demo

# One-shot demo of a single skill's real module chain
demo-skill:
	$(PYTHON) -m charter.demo_skill $(SKILL) $(if $(JSON),--json,)

list-skill:
	$(PYTHON) -m charter.demo_skill --list

# v3.15: ETag CAS multi-writer stress (no lost updates under concurrency)
#   make stress N=4 I=25             - 4 writers x 25 iterations by default
#   make stress N=4 I=25 JSON=1     - machine-readable JSON (for CI artifacts)
#   make stress N=4 I=25 OUT=cas_report.json  - also write JSON to a file
#   make stress TIER=high            - high-pressure preset (16 writers x 100 rounds)
#   make stress TIER=low             - low-pressure preset (2 writers x 10 rounds)
stress:
\t@if [ "$(JSON)" = "1" ]; then \
\t\t$(PYTHON) -c "import sys, json; sys.path.insert(0, '.'); from charter import reference_kv_gateway, stress_multi_writer; srv, url, _ = reference_kv_gateway(); r = stress_multi_writer(n_writers=$(N), iterations=$(I), base_url=url, max_cas_retries=30); r['version']='3.18'; print(json.dumps(r, indent=2)); assert r['ok'], r; srv.shutdown()" ; \
\telse \
\t\t$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from charter import reference_kv_gateway, stress_multi_writer; srv, url, _ = reference_kv_gateway(); r = stress_multi_writer(n_writers=$(N), iterations=$(I), base_url=url, max_cas_retries=30); print(r); assert r['ok'], r; srv.shutdown()" ; \
\tfi
\t@if [ -n "$(OUT)" ]; then \
\t\t$(PYTHON) -c "import sys, json; sys.path.insert(0, '.'); from charter import reference_kv_gateway, stress_multi_writer; srv, url, _ = reference_kv_gateway(); r = stress_multi_writer(n_writers=$(N), iterations=$(I), base_url=url, max_cas_retries=30); r['version']='3.18'; json.dump(r, open('$(OUT)','w'), indent=2); assert r['ok'], r; srv.shutdown()" ; \
\t\techo "CAS stress report written to $(OUT)" ; \
\tfi

N ?= 4
I ?= 25
JSON ?= 0
OUT ?=
TIER ?=

# v3.17: big-pressure CAS preset (16 writers x 100 rounds, conflict-rate stats)
stress-big:
\t$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from charter import reference_kv_gateway, stress_multi_writer; srv, url, _ = reference_kv_gateway(); r = stress_multi_writer(n_writers=16, iterations=100, base_url=url, max_cas_retries=50); print(r); assert r['ok'], r; srv.shutdown()"

# v3.16: CI-ready non-blocking stress step (prints the snippet to paste into .github/workflows/ci.yml)
stress-ci:
\t@echo "Paste this as a non-blocking CI step (continue-on-error: true):"
\t@echo ""
\t@echo "  - name: CAS multi-writer stress (non-blocking)"
\t@echo "    if: \'always()\'"
\t@echo "    continue-on-error: true"
\t@echo "    run: |"
\t@echo "      python -c \"import sys; sys.path.insert(0, '.'); \"
\t@echo "      from charter import reference_kv_gateway, stress_multi_writer; \"
\t@echo "      srv, url, _ = reference_kv_gateway(); \"
\t@echo "      r = stress_multi_writer(n_writers=4, iterations=25, base_url=url, max_cas_retries=30); \"
\t@echo "      print(r); assert r['ok'], r; srv.shutdown()\""

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache charter_orchestrator.egg-info
