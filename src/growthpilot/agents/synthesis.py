from __future__ import annotations

import re
from typing import Any

from growthpilot.rag.retrieval import RetrievedChunk

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "give",
    "how",
    "in",
    "is",
    "me",
    "of",
    "our",
    "should",
    "the",
    "to",
    "we",
    "what",
    "with",
}


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(text) if token.lower() not in _STOPWORDS}


def _external_id(customer: dict[str, Any]) -> str:
    return str(customer.get("external_customer_id") or customer.get("id") or "unknown")


def _product_label(recommendation: dict[str, Any]) -> str:
    description = str(recommendation.get("description") or "").strip()
    stock_code = str(recommendation.get("stock_code") or "").strip()
    if description and stock_code:
        return f"{description} ({stock_code})"
    return description or stock_code or f"Product {recommendation.get('product_id', 'unknown')}"


def _driver_names(customer: dict[str, Any]) -> list[str]:
    explanation = customer.get("churn_explanation") or {}
    drivers = explanation.get("top_global_drivers") or []
    names: list[str] = []
    for driver in drivers[:3]:
        name = driver.get("feature") if isinstance(driver, dict) else driver
        if name:
            names.append(str(name).replace("_", " "))
    return names


def customer_answer(question: str, customer: dict[str, Any]) -> str:
    """Create a question-specific, grounded Customer 360 answer.

    Customer identifiers used to force every question through one generic template. This
    dispatcher keeps the safe Customer 360 route while answering the actual sub-intent.
    """

    normalized = question.lower()
    identifier = _external_id(customer)
    recommendations = list(customer.get("recommendations") or [])

    if any(term in normalized for term in ("recommend", "product", "cross-sell", "cross sell")):
        if not recommendations:
            return f"No product recommendations are available for Customer {identifier}."
        lines = []
        for recommendation in recommendations[:3]:
            reason = str(recommendation.get("reason") or "Recommended by the hybrid ranker")
            lines.append(f"• {_product_label(recommendation)} — {reason}.")
        return f"Top product recommendations for Customer {identifier}:\n" + "\n".join(lines)

    next_action = customer.get("next_action") or {}
    if any(
        term in normalized
        for term in (
            "do next",
            "next action",
            "sales team do",
            "contact customer",
            "why contact",
        )
    ):
        title = str(next_action.get("title") or "Review the customer profile")
        rationale = str(next_action.get("rationale") or "No action rationale is available.")
        answer = f"Next action for Customer {identifier}: {title}. {rationale}"
        product_id = next_action.get("recommended_product_id")
        product = next(
            (item for item in recommendations if item.get("product_id") == product_id),
            recommendations[0] if recommendations else None,
        )
        if product:
            answer += f" Use {_product_label(product)} as the featured product."
        return answer

    if any(term in normalized for term in ("why", "at risk", "at-risk", "churn", "risk")):
        probability = float(customer.get("churn_probability") or 0)
        features = customer.get("features") or {}
        signals: list[str] = []
        if features.get("recency_days") is not None:
            signals.append(f"{features['recency_days']} days since the last purchase")
        if features.get("frequency_orders") is not None:
            signals.append(f"{features['frequency_orders']} lifetime orders")
        if features.get("average_order_value") is not None:
            signals.append(f"an average order value of {features['average_order_value']}")
        answer = f"Customer {identifier} has a {probability:.0%} predicted churn risk."
        if signals:
            answer += " Profile signals: " + ", ".join(signals) + "."
        drivers = _driver_names(customer)
        if drivers:
            answer += " The churn model's leading global drivers are " + ", ".join(drivers) + "."
        if next_action.get("title"):
            answer += f" Recommended response: {next_action['title']}."
        return answer

    return (
        f"Customer {identifier} is in the "
        f"{customer.get('segment_name', 'Unclassified')} segment with "
        f"{float(customer.get('churn_probability') or 0):.0%} churn risk and "
        f"{float(customer.get('propensity_probability') or 0):.0%} purchase propensity. "
        f"Recommended action: {next_action.get('title', 'Review the customer profile')}."
    )


def _sentences(chunks: list[RetrievedChunk]) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        # Chunking collapses whitespace, so remove the known Markdown heading when present.
        content = re.sub(
            r"^\s*#*\s*GrowthPilot retention and growth playbook\s*",
            "",
            chunk.content,
            flags=re.IGNORECASE,
        )
        for sentence in _SENTENCE.split(" ".join(content.split())):
            cleaned = sentence.strip(" -\n\t")
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                sentences.append(cleaned)
    return sentences


def _first_matching(sentences: list[str], terms: tuple[str, ...]) -> str | None:
    return next(
        (sentence for sentence in sentences if any(term in sentence.lower() for term in terms)),
        None,
    )


def _best_practices(sentences: list[str]) -> list[str]:
    groups = (
        ("prioritize", "high-value"),
        ("loyal customers", "cross-sell"),
        ("dormant", "reactivation"),
        ("every action", "record an outcome"),
        ("review conversion", "incremental value"),
    )
    selected = [_first_matching(sentences, group) for group in groups]
    return [sentence for sentence in selected if sentence]


def knowledge_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Extract only the playbook passages that answer the question."""

    if not chunks:
        return "No relevant knowledge was found in the approved GrowthPilot playbook."
    sentences = _sentences(chunks)
    if not sentences:
        return "No relevant knowledge was found in the approved GrowthPilot playbook."

    normalized = question.lower()
    if "best practice" in normalized:
        selected = _best_practices(sentences)
    else:
        focus_terms: set[str] = set()
        limit = 3
        if "loyal" in normalized or "champion" in normalized:
            focus_terms.update(
                {
                    "loyal",
                    "champions",
                    "cross-sell",
                    "propensity",
                    "recognition",
                    "early access",
                    "primary recommendation",
                    "alternative",
                }
            )
        if "reactivat" in normalized or "dormant" in normalized:
            focus_terms.update({"reactivation", "dormant", "low-cost", "unanswered"})
            limit = 2
        if "avoid" in normalized or "not offer" in normalized:
            focus_terms.update({"avoid", "blanket", "aggressive"})
            limit = 2
        if any(term in normalized for term in ("high risk", "high-risk", "churn")):
            focus_terms.update({"high-value", "churn", "personal", "loyalty", "blanket"})
        query_terms = _tokens(normalized) | focus_terms

        ranked: list[tuple[float, int, str]] = []
        for index, sentence in enumerate(sentences):
            lower = sentence.lower()
            sentence_terms = _tokens(lower)
            overlap = len(query_terms & sentence_terms)
            phrase_bonus = sum(2 for term in focus_terms if term in lower)
            ranked.append((overlap + phrase_bonus, index, sentence))
        positive = sorted(
            (item for item in ranked if item[0] > 0),
            key=lambda item: (-item[0], item[1]),
        )
        selected = [item[2] for item in positive[:limit]]
        if not selected:
            selected = sentences[:2]

    if not selected:
        return "No relevant knowledge was found in the approved GrowthPilot playbook."
    return "Approved playbook guidance: " + " ".join(selected)
