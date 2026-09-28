from __future__ import annotations

import re

from growthpilot.agents.schemas import ValidationResult

_STOPWORDS = {
    "about",
    "after",
    "also",
    "because",
    "been",
    "before",
    "between",
    "could",
    "from",
    "have",
    "into",
    "more",
    "most",
    "only",
    "other",
    "should",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "using",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in _STOPWORDS
    }


def _numbers(text: str) -> set[str]:
    values = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text.replace(",", "")))
    expanded = set(values)
    for value in values:
        if value.endswith("%"):
            continue
        try:
            number = float(value)
        except ValueError:
            continue
        if 0 <= number <= 1:
            expanded.add(f"{number * 100:g}%")
    return expanded


class GroundingValidator:
    """Conservative, deterministic evidence check adapted from ContextOps."""

    def validate(self, answer: str, evidence: str) -> ValidationResult:
        lower = answer.lower()
        if any(
            phrase in lower
            for phrase in (
                "not enough growthpilot evidence",
                "insufficient evidence",
                "cannot determine from the available evidence",
                "no relevant knowledge was found",
            )
        ):
            return ValidationResult(
                grounded=True,
                confidence=0.95,
                notes="The answer safely states that available evidence is insufficient.",
            )
        if not evidence.strip():
            return ValidationResult(
                grounded=False,
                confidence=0.15,
                notes="No SQL, customer, model, or playbook evidence supported the answer.",
                unsupported_claims=["Answer has no GrowthPilot evidence."],
            )

        unsupported_numbers = sorted(_numbers(answer) - _numbers(evidence))
        answer_terms = _tokens(answer)
        evidence_terms = _tokens(evidence)
        overlap = answer_terms & evidence_terms
        overlap_ratio = len(overlap) / max(1, min(len(answer_terms), 20))
        grounded = not unsupported_numbers and (len(overlap) >= 2 or overlap_ratio >= 0.16)

        if grounded:
            return ValidationResult(
                grounded=True,
                confidence=min(0.97, 0.72 + min(0.23, overlap_ratio)),
                notes=(
                    "Grounding check passed: factual and numeric claims are supported by "
                    "the selected GrowthPilot tools."
                ),
            )

        reasons: list[str] = []
        if unsupported_numbers:
            reasons.append(f"Unsupported numeric claims: {', '.join(unsupported_numbers)}")
        if len(overlap) < 2 and overlap_ratio < 0.16:
            reasons.append("Answer has weak lexical support in the supplied evidence")
        return ValidationResult(
            grounded=False,
            confidence=0.35,
            notes="; ".join(reasons) or "Grounding check failed.",
            unsupported_claims=reasons,
        )
