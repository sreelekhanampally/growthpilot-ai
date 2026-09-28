import pandas as pd

from growthpilot.recommendations.engine import HybridRecommender


def transactions() -> pd.DataFrame:
    rows = []
    date = pd.Timestamp("2025-01-01")
    baskets = {
        1: [[10, 11], [10, 12], [11, 13]],
        2: [[10, 11], [11, 12], [12, 13]],
        3: [[10, 12], [10, 13], [11, 13]],
        4: [[20, 21], [20, 22], [21, 22]],
    }
    for customer, orders in baskets.items():
        for order_index, products in enumerate(orders):
            for product in products:
                rows.append(
                    {
                        "customer_id": customer,
                        "product_id": product,
                        "quantity": 1,
                        "order_type": "purchase",
                        "invoice_no": f"{customer}-{order_index}",
                        "invoice_date": date + pd.Timedelta(days=order_index * 10),
                    }
                )
    return pd.DataFrame(rows)


def test_recommender_excludes_owned_products():
    model = HybridRecommender().fit(transactions())
    recommendations = model.recommend(1, k=3)
    owned = model.customer_items[1]
    assert recommendations
    assert all(item.product_id not in owned for item in recommendations)


def test_recommender_evaluation_has_valid_range():
    model = HybridRecommender().fit(transactions())
    metrics = model.evaluate_leave_last_out(transactions(), k=3)
    assert 0 <= metrics["hit_rate_at_k"] <= 1
    assert metrics["evaluated_customers"] == 4
