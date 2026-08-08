.PHONY: help sample test verify

PYTHON ?= python3
export PYTHONPATH := src:tests

help:
	@echo "make sample   - regenerate deterministic sample data"
	@echo "make test     - run the full test suite"
	@echo "make verify   - tests + real end-to-end run on sample data"

sample:
	$(PYTHON) scripts/generate_sample_data.py

test:
	$(PYTHON) -m unittest discover -s tests -t tests -v

verify:
	$(PYTHON) scripts/verify.py
