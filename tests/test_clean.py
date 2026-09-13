from pathlib import Path

from growthpilot.data.clean import clean_transactions
from growthpilot.data.ingest import read_transactions

SAMPLE = Path(__file__).parents[1] / "data" / "sample" / "online_retail_sample.csv"


def test_cleaning_classifies_every_sample_row() -> None:
    result = clean_transactions(read_transactions(SAMPLE))

    assert result.input_rows == 15
    assert len(result.purchases) == 8
    assert len(result.returns) == 1
    assert len(result.rejected) == 6
    assert result.input_rows == len(result.purchases) + len(result.returns) + len(result.rejected)


def test_rejection_reasons_capture_edge_cases() -> None:
    result = clean_transactions(read_transactions(SAMPLE))
    reasons = set("|".join(result.rejected["rejection_reasons"]).split("|"))
    assert {
        "zero_quantity",
        "missing_customer_id",
        "invalid_invoice_date",
        "negative_unit_price",
        "cancellation_positive_quantity",
        "duplicate_row",
    }.issubset(reasons)


def test_customer_ids_drop_excel_float_suffix() -> None:
    result = clean_transactions(read_transactions(SAMPLE))
    assert "13085" in set(result.purchases["customer_id"])
    assert not result.purchases["customer_id"].str.endswith(".0").any()
