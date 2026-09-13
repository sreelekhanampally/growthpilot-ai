import json
from dataclasses import dataclass
from pathlib import Path

from growthpilot.data.clean import clean_transactions
from growthpilot.data.eda import generate_eda
from growthpilot.data.ingest import read_transactions
from growthpilot.data.quality import build_quality_report, enforce_quality


@dataclass(frozen=True)
class Phase1Result:
    input_rows: int
    purchase_rows: int
    return_rows: int
    rejected_rows: int
    quality_report_path: Path
    eda_report_path: Path


def run_phase1(
    input_path: Path,
    *,
    processed_dir: Path,
    report_dir: Path,
    fail_on_quality: bool = True,
) -> Phase1Result:
    """Execute Phase 1 atomically enough to avoid presenting unvalidated clean data."""
    raw = read_transactions(input_path)
    cleaned = clean_transactions(raw)
    quality = build_quality_report(cleaned)
    if fail_on_quality:
        enforce_quality(quality)

    processed_dir.mkdir(parents=True, exist_ok=True)
    cleaned.purchases.to_csv(processed_dir / "transactions_clean.csv", index=False)
    cleaned.returns.to_csv(processed_dir / "transactions_returns.csv", index=False)
    cleaned.rejected.to_csv(processed_dir / "transactions_rejected.csv", index=False)
    quality_path = processed_dir / "data_quality_report.json"
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    generate_eda(cleaned.purchases, cleaned.returns, quality, report_dir)
    return Phase1Result(
        input_rows=cleaned.input_rows,
        purchase_rows=len(cleaned.purchases),
        return_rows=len(cleaned.returns),
        rejected_rows=len(cleaned.rejected),
        quality_report_path=quality_path,
        eda_report_path=report_dir / "EDA_REPORT.md",
    )
