.PHONY: test test-fast test-full test-redteam lint

test:
	python -m pytest -q -m "not slow and not redteam and not evals"

test-fast:
	python -m pytest -q -m "not slow and not redteam and not evals"

test-full:
	python -m pytest -q

test-redteam:
	python -m pytest -q -m redteam

lint:
	python -m ruff check .
