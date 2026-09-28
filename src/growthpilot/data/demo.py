from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_demo_transactions(output: Path, *, customers: int = 240, seed: int = 42) -> Path:
    """Create a deterministic, realistic-enough synthetic dataset for the product demo.

    This data is explicitly synthetic and must not be used to claim production model quality.
    """
    rng = np.random.default_rng(seed)
    start = datetime(2009, 12, 1)
    end = datetime(2011, 12, 9)
    products = [f"GP{index:04d}" for index in range(1, 81)]
    prices = {code: round(float(rng.lognormal(2.5, 0.65)), 2) for code in products}
    countries = ["United Kingdom", "France", "Germany", "Netherlands", "Spain", "Belgium"]
    rows: list[dict] = []
    invoice = 100000
    for customer_index in range(customers):
        customer_id = str(15000 + customer_index)
        country = rng.choice(countries, p=[0.70, 0.08, 0.08, 0.06, 0.05, 0.03])
        first_day = int(rng.integers(0, 300))
        active_start = start + timedelta(days=first_day)
        churn_group = customer_index % 4 == 0
        earliest_churn = active_start + timedelta(days=180)
        latest_churn = end - timedelta(days=100)
        active_end = (
            earliest_churn
            + timedelta(days=int(rng.integers(0, max((latest_churn - earliest_churn).days, 1))))
            if churn_group and earliest_churn < latest_churn
            else end
        )
        cadence = int(rng.integers(12, 75))
        affinity = rng.choice(products, size=int(rng.integers(6, 18)), replace=False).tolist()
        moment = active_start
        while moment <= active_end:
            progress = (moment - active_start).days / max((active_end - active_start).days, 1)
            effective_cadence = cadence * (1 + 1.4 * progress) if churn_group else cadence
            moment += timedelta(
                days=max(2, int(rng.normal(effective_cadence, effective_cadence * 0.2)))
            )
            if moment > active_end:
                break
            invoice += 1
            basket = rng.choice(
                affinity, size=int(rng.integers(1, min(7, len(affinity)) + 1)), replace=False
            )
            for product in basket:
                quantity = int(rng.integers(1, 9))
                rows.append(
                    {
                        "Invoice": str(invoice),
                        "StockCode": product,
                        "Description": f"Demo product {product}",
                        "Quantity": quantity,
                        "InvoiceDate": moment.strftime("%Y-%m-%d %H:%M:%S"),
                        "Price": prices[product],
                        "Customer ID": customer_id,
                        "Country": country,
                    }
                )
            if rng.random() < 0.035:
                returned = str(rng.choice(basket))
                rows.append(
                    {
                        "Invoice": f"C{invoice}",
                        "StockCode": returned,
                        "Description": f"Demo product {returned}",
                        "Quantity": -1,
                        "InvoiceDate": (moment + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                        "Price": prices[returned],
                        "Customer ID": customer_id,
                        "Country": country,
                    }
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values("InvoiceDate").to_csv(output, index=False)
    return output
