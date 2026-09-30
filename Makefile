# galaxy-profile — development targets (all run inside .venv)
PY := .venv/bin/python

.PHONY: install test lint demo dev fonts

install:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m compileall -q generator tools tests
	$(PY) -m pytest -q --collect-only > /dev/null

demo:
	$(PY) -m generator.main --demo

dev: demo
	open assets/generated

fonts:
	$(PY) -m pip install -q -r requirements-fonts.txt
	$(PY) tools/build_font_atlas.py
