from pathlib import Path

import pandas as pd
import pytest

from growthpilot.data.ingest import SchemaError, read_transactions


def test_common_online_retail_aliases_are_normalized(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    pd.DataFrame(
        {
            "InvoiceNo": ["1"],
            "StockCode": ["A"],
            "Description": ["Item"],
            "Quantity": [1],
            "InvoiceDate": ["2020-01-01"],
            "UnitPrice": [2.5],
            "CustomerID": [123.0],
            "Country": ["UK"],
        }
    ).to_csv(source, index=False)

    result = read_transactions(source)
    assert set(["invoice_no", "unit_price", "customer_id"]).issubset(result.columns)
    assert result.loc[0, "source_sheet"] == "csv"


def test_missing_required_column_fails_early(tmp_path: Path) -> None:
    source = tmp_path / "invalid.csv"
    pd.DataFrame({"Invoice": ["1"]}).to_csv(source, index=False)
    with pytest.raises(SchemaError, match="missing required columns"):
        read_transactions(source)
