from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "invoice_no",
    "stock_code",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
}

ALIASES = {
    "invoice": "invoice_no",
    "invoiceno": "invoice_no",
    "stockcode": "stock_code",
    "description": "description",
    "quantity": "quantity",
    "invoicedate": "invoice_date",
    "price": "unit_price",
    "unitprice": "unit_price",
    "customerid": "customer_id",
    "country": "country",
}


class SchemaError(ValueError):
    """Raised when an input table does not match the transaction contract."""


def _column_key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _normalize_table(frame: pd.DataFrame, *, source_file: str, source_sheet: str) -> pd.DataFrame:
    rename = {column: ALIASES.get(_column_key(column), _column_key(column)) for column in frame}
    normalized = frame.rename(columns=rename)
    missing = sorted(REQUIRED_COLUMNS - set(normalized.columns))
    if missing:
        raise SchemaError(f"{source_sheet}: missing required columns: {', '.join(missing)}")
    if "description" not in normalized:
        normalized["description"] = pd.NA

    canonical = [
        "invoice_no",
        "stock_code",
        "description",
        "quantity",
        "invoice_date",
        "unit_price",
        "customer_id",
        "country",
    ]
    normalized = normalized.loc[:, canonical].copy()
    normalized.insert(0, "source_row_number", range(1, len(normalized) + 1))
    normalized.insert(0, "source_sheet", source_sheet)
    normalized.insert(0, "source_file", source_file)
    return normalized


def read_transactions(path: Path) -> pd.DataFrame:
    """Read every table in a supported source file into one canonical raw frame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        raw = pd.read_csv(path, dtype=object)
        frames = [_normalize_table(raw, source_file=path.name, source_sheet="csv")]
    elif suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, dtype=object)
        if not sheets:
            raise SchemaError("Workbook contains no sheets")
        frames = [
            _normalize_table(frame, source_file=path.name, source_sheet=str(sheet))
            for sheet, frame in sheets.items()
        ]
    else:
        raise SchemaError(f"Unsupported input format: {suffix or '<none>'}")

    return pd.concat(frames, ignore_index=True)
