SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= .venv/bin/python
SPEECH_PYTHON ?= .venv-speech/bin/python
VOICE_QA_PYTHON ?= .venv-voice-qa/bin/python
UV ?= uv
SPEECH_TESTS := tests.test_speech_pacing tests.test_voice_consistency tests.test_voice_takes tests.test_science_voice_takes
CORE_TESTS := $(patsubst tests/%.py,tests.%,$(filter-out $(addsuffix .py,$(subst tests.,tests/,$(SPEECH_TESTS))),$(wildcard tests/test_*.py)))

.PHONY: help setup doctor repository-check test-core test-speech test-voice-qa remotion-setup \
 remotion-browser remotion-check speech-setup speech-model speech-doctor

help:
	@echo "MathCoffee framework: setup doctor test-core test-speech repository-check"
	@echo "Optional: remotion-setup remotion-browser remotion-check"
	@echo "Optional: speech-setup speech-model speech-doctor"
	@echo "No installation, synthesis or rendering runs by default."

setup:
	$(UV) sync --locked --no-editable --extra render

doctor:
	bash scripts/doctor.sh

repository-check:
	$(PYTHON) scripts/repository_guard.py

test-core:
	PYTHONPATH="$(CURDIR)/src:$(CURDIR)" $(PYTHON) -m unittest $(CORE_TESTS)

test-speech:
	PYTHONPATH="$(CURDIR)/src:$(CURDIR)" $(SPEECH_PYTHON) -m unittest $(SPEECH_TESTS)

test-voice-qa:
	PYTHONPATH="$(CURDIR)/src:$(CURDIR)" $(VOICE_QA_PYTHON) toolchains/voice_qa/test_metric.py

remotion-setup:
	cd engines/remotion && npm ci --ignore-scripts --no-audit --no-fund --cache .npm-cache --registry https://registry.npmjs.org

remotion-browser:
	cd engines/remotion && npm run browser:ensure

remotion-check:
	cd engines/remotion && npm run typecheck && npm test

speech-setup:
	sh toolchains/speech/setup.sh

speech-model:
	$(SPEECH_PYTHON) toolchains/speech/fetch_model.py

speech-doctor:
	$(SPEECH_PYTHON) toolchains/speech/doctor.py --verify-model
