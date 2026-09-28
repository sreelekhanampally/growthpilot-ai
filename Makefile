.PHONY: install install-full test lint frontend-build demo download phase1 db-upgrade load-db features train serve

install:
	python -m pip install -e ".[dev]"

install-full:
	python -m pip install -e ".[dev,full]"

test:
	pytest

lint:
	ruff check .

frontend-build:
	cd frontend && npm ci && npm run build

demo:
	powershell -ExecutionPolicy Bypass -File scripts/setup_demo.ps1

sample:
	growthpilot phase1 --input data/sample/online_retail_sample.csv

download:
	growthpilot download

phase1:
	growthpilot phase1 --input data/raw/online_retail_II.xlsx

db-upgrade:
	growthpilot db-upgrade

load-db:
	growthpilot load-db

features:
	growthpilot build-features --as-of 2011-12-09T12:50:00

train:
	growthpilot train-all

serve:
	growthpilot serve --reload
