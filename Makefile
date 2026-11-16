PY ?= python3

.PHONY: help test demo guard report audio fixtures-check clean
help:
	@echo "make test           run the unit suite (no device, no network)"
	@echo "make demo           run every gate against the recorded fixtures"
	@echo "make guard          prove the gate closes: tightened limits must fail"
	@echo "make report         write out/report.html — one self-contained file"
	@echo "make audio          decode the recorded wav bank and judge it"
	@echo "make fixtures-check prove the fixtures are what the generator produces"

test:
	$(PY) -m unittest discover -s tests -v

demo:
	$(PY) -m qa demo

audio:
	@$(PY) -m qa audio tests/fixtures/audio

report:
	@$(PY) -m qa html out/report.html

guard:
	@$(PY) tools/guard.py

fixtures-check:
	@$(PY) tools/gen_fixtures.py --check
