import pandas as pd

from growthpilot.data.clean import clean_transactions


def test_nonintegral_quantity_is_rejected() -> None:
    raw = pd.DataFrame(
        [
            {
                "source_file": "fixture.csv",
                "source_sheet": "csv",
                "source_row_number": 1,
                "invoice_no": "100",
                "stock_code": "SKU-1",
                "description": "Example",
                "quantity": 1.5,
                "invoice_date": "2026-01-01",
                "unit_price": 10,
                "customer_id": "C-1",
                "country": "United Kingdom",
            }
        ]
    )

    result = clean_transactions(raw)

    assert result.purchases.empty
    assert result.rejected.loc[0, "rejection_reasons"] == "nonintegral_quantity"
