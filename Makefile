.PHONY: install test lint sample download phase1

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

sample:
	growthpilot phase1 --input data/sample/online_retail_sample.csv

download:
	growthpilot download

phase1:
	growthpilot phase1 --input data/raw/online_retail_II.xlsx
