import json
from pathlib import Path

import pandas as pd

from growthpilot.data.pipeline import run_phase1

SAMPLE = Path(__file__).parents[1] / "data" / "sample" / "online_retail_sample.csv"


def test_phase1_pipeline_writes_reconciled_outputs(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    reports = tmp_path / "reports"
    result = run_phase1(SAMPLE, processed_dir=processed, report_dir=reports)

    quality = json.loads((processed / "data_quality_report.json").read_text())
    clean = pd.read_csv(processed / "transactions_clean.csv")
    returns = pd.read_csv(processed / "transactions_returns.csv")
    rejected = pd.read_csv(processed / "transactions_rejected.csv")

    assert result.input_rows == len(clean) + len(returns) + len(rejected)
    assert quality["all_quality_gates_passed"] is True
    assert (reports / "EDA_REPORT.md").exists()
    assert (reports / "eda_overview.png").stat().st_size > 0
    assert (reports / "monthly_revenue.csv").exists()
