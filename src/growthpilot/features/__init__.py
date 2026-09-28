"""Leakage-safe customer feature generation."""

from growthpilot.features.contract import DEFAULT_FEATURE_VERSION
from growthpilot.features.service import build_and_store_features

__all__ = ["DEFAULT_FEATURE_VERSION", "build_and_store_features"]
