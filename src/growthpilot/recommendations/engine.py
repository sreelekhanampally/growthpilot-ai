from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class Recommendation:
    product_id: int
    score: float
    reason: str


class HybridRecommender:
    """Item-item collaborative ranker blended with global and segment popularity."""

    def __init__(self, popularity_weight: float = 0.2, segment_weight: float = 0.2):
        self.popularity_weight = popularity_weight
        self.segment_weight = segment_weight
        self.customer_items: dict[int, set[int]] = {}
        self.product_ids: list[int] = []
        self.similarity: np.ndarray | None = None
        self.popularity: dict[int, float] = {}
        self.segment_popularity: dict[str, dict[int, float]] = {}

    def fit(
        self, transactions: pd.DataFrame, segments: pd.DataFrame | None = None
    ) -> HybridRecommender:
        purchases = transactions[
            transactions["order_type"].eq("purchase") & transactions["quantity"].gt(0)
        ].copy()
        interactions = (
            purchases.groupby(["customer_id", "product_id"])["quantity"].sum().reset_index()
        )
        customers = sorted(int(value) for value in interactions["customer_id"].unique())
        self.product_ids = sorted(int(value) for value in interactions["product_id"].unique())
        customer_index = {value: index for index, value in enumerate(customers)}
        product_index = {value: index for index, value in enumerate(self.product_ids)}
        matrix = csr_matrix(
            (
                np.log1p(interactions["quantity"].to_numpy(dtype=float)),
                (
                    interactions["customer_id"].map(customer_index),
                    interactions["product_id"].map(product_index),
                ),
            ),
            shape=(len(customers), len(self.product_ids)),
        )
        self.similarity = cosine_similarity(matrix.T, dense_output=True)
        np.fill_diagonal(self.similarity, 0.0)
        self.customer_items = (
            interactions.groupby("customer_id")["product_id"]
            .apply(lambda values: {int(value) for value in values})
            .to_dict()
        )
        counts = interactions.groupby("product_id")["customer_id"].nunique()
        maximum = max(float(counts.max()), 1.0)
        self.popularity = {
            int(product): float(value / maximum) for product, value in counts.items()
        }
        if segments is not None and not segments.empty:
            joined = interactions.merge(segments[["customer_id", "segment_name"]], on="customer_id")
            for name, group in joined.groupby("segment_name"):
                values = group.groupby("product_id")["customer_id"].nunique()
                scale = max(float(values.max()), 1.0)
                self.segment_popularity[str(name)] = {
                    int(product): float(value / scale) for product, value in values.items()
                }
        return self

    def recommend(
        self, customer_id: int, *, segment_name: str | None = None, k: int = 5
    ) -> list[Recommendation]:
        if self.similarity is None:
            raise RuntimeError("Recommender has not been fitted")
        purchased = self.customer_items.get(int(customer_id), set())
        scores = np.zeros(len(self.product_ids), dtype=float)
        index = {value: position for position, value in enumerate(self.product_ids)}
        if purchased:
            purchased_indices = [index[value] for value in purchased if value in index]
            if purchased_indices:
                scores += self.similarity[:, purchased_indices].max(axis=1)
        for product, value in self.popularity.items():
            scores[index[product]] += self.popularity_weight * value
        if segment_name in self.segment_popularity:
            for product, value in self.segment_popularity[segment_name].items():
                scores[index[product]] += self.segment_weight * value
        for product in purchased:
            if product in index:
                scores[index[product]] = -np.inf
        ranked = np.argsort(scores)[::-1]
        result: list[Recommendation] = []
        for position in ranked:
            if not np.isfinite(scores[position]):
                continue
            product = self.product_ids[int(position)]
            reason = (
                "Similar customers also purchased this product"
                if purchased
                else "Popular with customers like this one"
            )
            result.append(Recommendation(product, round(float(scores[position]), 6), reason))
            if len(result) == k:
                break
        return result

    def evaluate_leave_last_out(self, transactions: pd.DataFrame, k: int = 10) -> dict[str, float]:
        purchases = transactions[transactions["order_type"].eq("purchase")].sort_values(
            ["customer_id", "invoice_date", "invoice_no"]
        )
        last_invoices = purchases.groupby("customer_id")["invoice_no"].last()
        invoice_counts = purchases.groupby("customer_id")["invoice_no"].nunique()
        eligible = invoice_counts[invoice_counts >= 2].index
        tagged = purchases.merge(
            last_invoices.rename("held_out_invoice"),
            left_on="customer_id",
            right_index=True,
        )
        held_out = tagged[tagged["invoice_no"].eq(tagged["held_out_invoice"])]
        held_out_products = held_out.groupby("customer_id")["product_id"].apply(set)
        history = tagged[~tagged["invoice_no"].eq(tagged["held_out_invoice"])]
        evaluator = HybridRecommender(
            popularity_weight=self.popularity_weight,
            segment_weight=self.segment_weight,
        ).fit(history)
        hits, reciprocal_ranks = 0, []
        for customer_id in eligible:
            ranked = [item.product_id for item in evaluator.recommend(int(customer_id), k=k)]
            targets = {int(value) for value in held_out_products.get(customer_id, set())}
            matched = [ranked.index(product) for product in targets if product in ranked]
            if matched:
                hits += 1
                reciprocal_ranks.append(1 / (min(matched) + 1))
            else:
                reciprocal_ranks.append(0.0)
        denominator = max(len(eligible), 1)
        return {
            "hit_rate_at_k": round(hits / denominator, 6),
            "mrr_at_k": round(float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0, 6),
            "evaluated_customers": int(len(eligible)),
            "k": k,
        }

    def save(self, path: Path, metadata: dict[str, Any] | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"recommender": self, "metadata": metadata or {}}, path)

    @staticmethod
    def load(path: Path) -> HybridRecommender:
        return joblib.load(path)["recommender"]
