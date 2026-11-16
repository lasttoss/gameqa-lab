PY ?= python3

.PHONY: help test demo guard fixtures-check clean
help:
	@echo "make test           run the unit suite (no device, no network)"
	@echo "make demo           run every gate against the recorded fixtures"
	@echo "make guard          prove the gate closes: tightened limits must fail"
	@echo "make fixtures-check prove the fixtures are what the generator produces"

test:
	$(PY) -m unittest discover -s tests -v

demo:
	$(PY) -m qa demo

guard:
	@$(PY) tools/guard.py

fixtures-check:
	@$(PY) tools/gen_fixtures.py --check
