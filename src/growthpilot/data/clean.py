import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

BUSINESS_COLUMNS = [
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
]

OUTPUT_COLUMNS = [
    "source_row_id",
    "source_file",
    "source_sheet",
    "source_row_number",
    *BUSINESS_COLUMNS,
    "is_cancellation",
    "line_amount",
]


@dataclass(frozen=True)
class CleanResult:
    purchases: pd.DataFrame
    returns: pd.DataFrame
    rejected: pd.DataFrame
    input_rows: int


def _clean_text(series: pd.Series) -> pd.Series:
    value = series.astype("string").str.strip()
    return value.mask(value.str.lower().isin(["", "nan", "none", "<na>"]))


def _normalize_customer_id(series: pd.Series) -> pd.Series:
    value = _clean_text(series)
    return value.str.replace(r"\.0$", "", regex=True)


def _source_row_id(row: pd.Series) -> str:
    values = [row["source_file"], row["source_sheet"], row["source_row_number"]]
    values.extend(row.get(column) for column in BUSINESS_COLUMNS)
    serialized = "\x1f".join("<NA>" if pd.isna(value) else str(value) for value in values)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]


def clean_transactions(raw: pd.DataFrame) -> CleanResult:
    frame = raw.copy()
    input_rows = len(frame)

    for column in ["invoice_no", "stock_code", "description", "country"]:
        frame[column] = _clean_text(frame[column])
    frame["customer_id"] = _normalize_customer_id(frame["customer_id"])
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce")
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="coerce")
    frame["is_cancellation"] = frame["invoice_no"].str.upper().str.startswith("C", na=False)
    frame["line_amount"] = frame["quantity"] * frame["unit_price"]
    frame["source_row_id"] = frame.apply(_source_row_id, axis=1)

    reasons: list[list[str]] = [[] for _ in range(len(frame))]

    def flag(mask: pd.Series | np.ndarray, reason: str) -> None:
        for position in np.flatnonzero(np.asarray(mask, dtype=bool)):
            reasons[position].append(reason)

    flag(frame["invoice_no"].isna(), "missing_invoice_no")
    flag(frame["stock_code"].isna(), "missing_stock_code")
    flag(frame["customer_id"].isna(), "missing_customer_id")
    flag(frame["country"].isna(), "missing_country")
    flag(frame["invoice_date"].isna(), "invalid_invoice_date")
    flag(frame["quantity"].isna(), "invalid_quantity")
    flag(frame["quantity"].eq(0), "zero_quantity")
    flag(frame["unit_price"].isna(), "invalid_unit_price")
    flag(frame["unit_price"].lt(0), "negative_unit_price")

    duplicate = frame.duplicated(subset=BUSINESS_COLUMNS, keep="first")
    flag(duplicate, "duplicate_row")
    valid_quantity = frame["quantity"].notna()
    flag(
        valid_quantity & ~frame["is_cancellation"] & frame["quantity"].le(0),
        "purchase_nonpositive_quantity",
    )
    flag(
        valid_quantity & frame["is_cancellation"] & frame["quantity"].ge(0),
        "cancellation_positive_quantity",
    )

    reason_series = pd.Series(
        ["|".join(item) for item in reasons], index=frame.index, dtype="string"
    )
    rejected_mask = reason_series.ne("")
    rejected = frame.loc[rejected_mask, OUTPUT_COLUMNS].copy()
    rejected["rejection_reasons"] = reason_series.loc[rejected_mask]

    accepted = frame.loc[~rejected_mask, OUTPUT_COLUMNS].copy()
    purchases = accepted.loc[~accepted["is_cancellation"]].copy()
    returns = accepted.loc[accepted["is_cancellation"]].copy()

    for output in (purchases, returns, rejected):
        output.reset_index(drop=True, inplace=True)

    return CleanResult(purchases, returns, rejected, input_rows)
