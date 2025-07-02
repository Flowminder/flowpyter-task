# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Makefile for managing flowpyter-task dependencies and virtual environment.
#
# Requires pyenv to be installed, to ensure the correct python version is used for locking dependencies.
# The virtual environment directory can be configured by setting the variable VENVDIR (default is .venv).
#
# targets:
#   lock (default):
#       Compile requirements.txt and dev-requirements.txt from requirements.in and dev-requirements.in
#   requirements.txt:
#       Compile requirements.txt from requirements.in
#   dev-requirements.txt:
#       Compile dev-requirements.txt from dev-requirements.in
#   upgrade:
#       Re-compile requirements.txt and dev-requirements.txt, upgrading all dependencies
#   sync:
#       Sync virtual environment with requirements.txt
#   dev-sync:
#       Sync virtual environment with requirements.txt _and_ dev-requirements.txt, and editable-install flowpyter-task
#   unit-tests:
#       Run unit tests in virtual environment with dev requirements installed
#   integration-tests:
#       Run integration tests in virtual environment with dev requirements installed
#   tests:
#       Run all tests (unit and integration)
#   clean:
#       Remove virtual environment
#   deep-clean:
#       Remove virtual environment and compiled requirements files

VENVDIR ?= .venv
ACTIVATE := . $(VENVDIR)/bin/activate;
PIP_COMPILE := uv pip compile --strip-extras --generate-hashes --allow-unsafe --universal
PIP_SYNC := pip-sync --pip-args "--no-deps"
FLOWPYTER_TASK_BUILD_FILES := setup.py setup.cfg pyproject.toml
# File to keep track of when virtual env was created (not modified when new packages are installed),
# so that virtual env can be recreated when .python-version changes
VENVTARGET := $(VENVDIR)/.created
# Recursive variable because versions should be read when a target is made, not before
VERSION_ENVS = FLOWKIT_VERSION=$(shell cat .flowkit-version) PYTHON_VERSION=$(shell $(VENVDIR)/bin/python --version | cut -d " " -f 2 | cut -d "." -f 1-2)

.PHONY: lock upgrade sync dev-sync test clean deep-clean

lock: requirements.txt dev-requirements.txt

# Create virtual env if it doesn't exist, and install pip-tools
$(VENVTARGET): .python-version
	rm -rf "$(VENVDIR)"
	pyenv install -s $(shell pyenv local)
	eval "$(shell pyenv init --path)"; python -m venv $(VENVDIR)
	$(ACTIVATE) pip install --upgrade pip pip-tools
	touch $(VENVTARGET)

requirements.txt: constraints.txt .flowkit-version $(FLOWPYTER_TASK_BUILD_FILES) | $(VENVTARGET)
ifdef CI
# requirements files should not be rebuilt when running in CI
	$(error requirements.txt is out of date)
else
	$(ACTIVATE) $(VERSION_ENVS) $(PIP_COMPILE) -c constraints.txt --output-file requirements.txt setup.py
endif

dev-requirements.txt: constraints.txt requirements.txt .flowkit-version $(FLOWPYTER_TASK_BUILD_FILES) | $(VENVTARGET)
ifdef CI
# requirements files should not be rebuilt when running in CI
	$(error dev-requirements.txt is out of date)
else
	$(ACTIVATE) $(VERSION_ENVS) $(PIP_COMPILE) -c constraints.txt -c requirements.txt --output-file dev-requirements.txt --extra test --extra dev setup.py
endif

docs/requirements.txt: docs/requirements.in $(FLOWPYTER_TASK_BUILD_FILES) | $(VENVTARGET)
ifdef CI
# requirements files should not be rebuilt when running in CI
	$(error dev-requirements.txt is out of date)
else
	$(ACTIVATE) $(VERSION_ENVS) $(PIP_COMPILE) --output-file docs/requirements.txt docs/requirements.in
endif

upgrade: constraints.txt .flowkit-version $(FLOWPYTER_TASK_BUILD_FILES) | $(VENVTARGET)
	$(ACTIVATE) $(VERSION_ENVS) $(PIP_COMPILE) --upgrade -c constraints.txt --output-file requirements.txt setup.py
	$(ACTIVATE) $(VERSION_ENVS) $(PIP_COMPILE) --upgrade -c constraints.txt -c requirements.txt --output-file dev-requirements.txt --extra test --extra dev setup.py

sync: requirements.txt | $(VENVTARGET)
	$(ACTIVATE) $(PIP_SYNC) requirements.txt

dev-sync: requirements.txt dev-requirements.txt $(FLOWPYTER_TASK_BUILD_FILES) | $(VENVTARGET)
	$(ACTIVATE) $(PIP_SYNC) requirements.txt dev-requirements.txt && pip install --no-deps -e .

test: dev-sync
	$(ACTIVATE) pytest tests

black-check: dev-sync
	$(ACTIVATE) black --check .

black-format: dev-sync
	$(ACTIVATE) black .

clean:
	rm -rf "$(VENVDIR)"

deep-clean: clean
	rm -f requirements.txt dev-requirements.txt
