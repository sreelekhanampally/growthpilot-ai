import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _money(value: float) -> str:
    return f"£{value:,.2f}"


def generate_eda(
    purchases: pd.DataFrame,
    returns: pd.DataFrame,
    quality_report: dict,
    report_dir: Path,
) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    purchase = purchases.copy()
    purchase["month"] = purchase["invoice_date"].dt.to_period("M").astype(str)

    monthly = (
        purchase.groupby("month", as_index=False)
        .agg(
            revenue=("line_amount", "sum"),
            orders=("invoice_no", "nunique"),
            customers=("customer_id", "nunique"),
        )
        .sort_values("month")
    )
    countries = (
        purchase.groupby("country", as_index=False)
        .agg(
            revenue=("line_amount", "sum"),
            orders=("invoice_no", "nunique"),
            customers=("customer_id", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )
    products = (
        purchase.groupby(["stock_code", "description"], dropna=False, as_index=False)
        .agg(
            revenue=("line_amount", "sum"),
            units=("quantity", "sum"),
            orders=("invoice_no", "nunique"),
        )
        .sort_values("revenue", ascending=False)
        .head(20)
    )

    order_totals = purchase.groupby("invoice_no")["line_amount"].sum()
    summary = {
        "gross_revenue": round(float(purchase["line_amount"].sum()), 2),
        "returned_value": round(float(-returns["line_amount"].sum()), 2),
        "net_revenue": quality_report["net_revenue"],
        "orders": int(purchase["invoice_no"].nunique()),
        "customers": int(purchase["customer_id"].nunique()),
        "products": int(purchase["stock_code"].nunique()),
        "countries": int(purchase["country"].nunique()),
        "average_order_value": (
            round(float(order_totals.mean()), 2) if not order_totals.empty else 0.0
        ),
        "median_order_value": (
            round(float(order_totals.median()), 2) if not order_totals.empty else 0.0
        ),
    }

    monthly.to_csv(report_dir / "monthly_revenue.csv", index=False)
    countries.to_csv(report_dir / "country_summary.csv", index=False)
    products.to_csv(report_dir / "top_products.csv", index=False)
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    _plot_overview(monthly, countries, products, purchase, report_dir / "eda_overview.png")
    _write_markdown(summary, quality_report, countries, products, report_dir / "EDA_REPORT.md")
    return summary


def _plot_overview(
    monthly: pd.DataFrame,
    countries: pd.DataFrame,
    products: pd.DataFrame,
    purchases: pd.DataFrame,
    output: Path,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    color = "#2563EB"

    axes[0, 0].plot(monthly["month"], monthly["revenue"], marker="o", color=color)
    axes[0, 0].set_title("Monthly gross revenue")
    axes[0, 0].tick_params(axis="x", rotation=45)

    top_countries = countries.head(8).sort_values("revenue")
    axes[0, 1].barh(top_countries["country"], top_countries["revenue"], color="#0F766E")
    axes[0, 1].set_title("Top countries by revenue")

    top_products = products.head(8).sort_values("revenue")
    labels = top_products["description"].fillna(top_products["stock_code"]).str.slice(0, 28)
    axes[1, 0].barh(labels, top_products["revenue"], color="#7C3AED")
    axes[1, 0].set_title("Top products by revenue")

    customer_revenue = purchases.groupby("customer_id")["line_amount"].sum()
    axes[1, 1].hist(customer_revenue, bins=min(30, max(1, len(customer_revenue))), color="#D97706")
    axes[1, 1].set_title("Customer revenue distribution")
    axes[1, 1].set_xlabel("Gross revenue per customer")

    fig.suptitle("GrowthPilot Phase 1 — Online Retail Data Overview", fontsize=16, weight="bold")
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _write_markdown(
    summary: dict,
    quality: dict,
    countries: pd.DataFrame,
    products: pd.DataFrame,
    output: Path,
) -> None:
    top_country = countries.iloc[0]["country"] if not countries.empty else "N/A"
    top_product = products.iloc[0]["description"] if not products.empty else "N/A"
    text = f"""# Phase 1 EDA Report

## Executive summary

| Metric | Value |
| --- | ---: |
| Gross purchase revenue | {_money(summary['gross_revenue'])} |
| Returned value | {_money(summary['returned_value'])} |
| Net revenue | {_money(summary['net_revenue'])} |
| Purchase orders | {summary['orders']:,} |
| Identified customers | {summary['customers']:,} |
| Products | {summary['products']:,} |
| Countries | {summary['countries']:,} |
| Average order value | {_money(summary['average_order_value'])} |

## Data quality

- Input rows: {quality['input_rows']:,}
- Accepted purchase rows: {quality['purchase_rows']:,}
- Accepted return rows: {quality['return_rows']:,}
- Rejected rows: {quality['rejected_rows']:,}
- Acceptance rate: {quality['acceptance_rate']:.2%}
- All required quality gates passed: **{quality['all_quality_gates_passed']}**

## Initial observations

- Highest-revenue country in the cleaned purchase data: **{top_country}**.
- Highest-revenue product in the cleaned purchase data: **{top_product}**.
- Revenue values are in the source currency (sterling) and are not FX-normalized.
- These are descriptive observations, not causal findings or model results.

## Generated companion files

- `monthly_revenue.csv`
- `country_summary.csv`
- `top_products.csv`
- `summary.json`
- `eda_overview.png`
"""
    output.write_text(text, encoding="utf-8")
