from collections import Counter
from dataclasses import asdict, dataclass

import pandas as pd

from growthpilot.data.clean import CleanResult


class QualityGateError(RuntimeError):
    """Raised when a Phase 1 output violates a required invariant."""


@dataclass(frozen=True)
class QualityGate:
    name: str
    passed: bool
    detail: str


def _iso(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def build_quality_report(result: CleanResult) -> dict:
    purchases, returns, rejected = result.purchases, result.returns, result.rejected
    output_rows = len(purchases) + len(returns) + len(rejected)
    all_ids = pd.concat(
        [purchases["source_row_id"], returns["source_row_id"], rejected["source_row_id"]],
        ignore_index=True,
    )

    gates = [
        QualityGate(
            "row_reconciliation",
            output_rows == result.input_rows,
            f"{result.input_rows} input rows vs {output_rows} classified rows",
        ),
        QualityGate(
            "unique_source_rows",
            not all_ids.duplicated().any(),
            f"{int(all_ids.duplicated().sum())} duplicate source row IDs",
        ),
        QualityGate(
            "valid_purchase_quantities",
            bool(purchases["quantity"].gt(0).all()),
            "all purchase quantities must be > 0",
        ),
        QualityGate(
            "valid_return_quantities",
            bool(returns["quantity"].lt(0).all()),
            "all return quantities must be < 0",
        ),
        QualityGate(
            "nonnegative_prices",
            bool(pd.concat([purchases["unit_price"], returns["unit_price"]]).ge(0).all()),
            "all accepted unit prices must be >= 0",
        ),
        QualityGate(
            "known_purchase_customers",
            bool(purchases["customer_id"].notna().all()),
            "all purchase customer IDs must be known",
        ),
        QualityGate(
            "valid_purchase_dates",
            bool(purchases["invoice_date"].notna().all()),
            "all purchase dates must parse",
        ),
    ]

    reason_counts: Counter[str] = Counter()
    for value in rejected.get("rejection_reasons", pd.Series(dtype="string")).dropna():
        reason_counts.update(str(value).split("|"))

    accepted = pd.concat([purchases, returns], ignore_index=True)
    min_date = accepted["invoice_date"].min() if not accepted.empty else None
    max_date = accepted["invoice_date"].max() if not accepted.empty else None
    gross_revenue = float(purchases["line_amount"].sum())
    returned_value = float(-returns["line_amount"].sum())

    return {
        "contract_version": "1.0",
        "input_rows": result.input_rows,
        "purchase_rows": len(purchases),
        "return_rows": len(returns),
        "rejected_rows": len(rejected),
        "accepted_rows": len(accepted),
        "acceptance_rate": (
            round(len(accepted) / result.input_rows, 6) if result.input_rows else 0.0
        ),
        "unique_customers": int(accepted["customer_id"].nunique()) if not accepted.empty else 0,
        "unique_products": int(accepted["stock_code"].nunique()) if not accepted.empty else 0,
        "date_min": _iso(min_date),
        "date_max": _iso(max_date),
        "gross_purchase_revenue": round(gross_revenue, 2),
        "returned_value": round(returned_value, 2),
        "net_revenue": round(gross_revenue - returned_value, 2),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "quality_gates": [asdict(gate) for gate in gates],
        "all_quality_gates_passed": all(gate.passed for gate in gates),
    }


def enforce_quality(report: dict) -> None:
    failures = [gate for gate in report["quality_gates"] if not gate["passed"]]
    if failures:
        detail = "; ".join(f"{gate['name']}: {gate['detail']}" for gate in failures)
        raise QualityGateError(detail)
