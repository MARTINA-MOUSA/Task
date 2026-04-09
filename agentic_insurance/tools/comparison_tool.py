"""Side-by-side comparison for two packages."""

from __future__ import annotations

from typing import Any

from agentic_insurance.data.knowledge_base import PACKAGES
from agentic_insurance.tools.scoring_tool import scoring_tool


def comparison_tool(package_a: str, package_b: str, customer_profile: dict[str, Any]) -> dict[str, Any]:
    """Compare two packages and return a deterministic recommendation."""

    if package_a not in PACKAGES or package_b not in PACKAGES:
        return {
            "error": "Comparison requested a package that is not available in the knowledge base.",
            "recommended": None,
            "pros": {},
            "cons": {},
        }

    candidates = [
        {"plan_name": package_a, **PACKAGES[package_a]},
        {"plan_name": package_b, **PACKAGES[package_b]},
    ]
    scored = scoring_tool(candidates, customer_profile)
    ranked = scored["ranked"]

    left = next(item for item in ranked if item["plan_name"] == package_a)
    right = next(item for item in ranked if item["plan_name"] == package_b)
    recommended = left if left["score"] >= right["score"] else right

    return {
        "comparison_of": [package_a, package_b],
        "left": {
            "plan_name": left["plan_name"],
            "network": left["network"],
            "price_range": left["price_range"],
            "score": left["score"],
            "pros": [
                "Lower price band than Premium" if left["plan_name"] != "Premium" else "Best coverage",
                left["notes"],
            ],
            "cons": [
                "Narrower network" if left["plan_name"] == "Basic" else "Higher cost than Basic",
            ],
        },
        "right": {
            "plan_name": right["plan_name"],
            "network": right["network"],
            "price_range": right["price_range"],
            "score": right["score"],
            "pros": [
                "Broader coverage" if right["plan_name"] != "Basic" else "Lower cost option",
                right["notes"],
            ],
            "cons": [
                "Higher cost" if right["plan_name"] == "Premium" else "Less coverage than Premium",
            ],
        },
        "recommended": recommended["plan_name"],
        "recommendation_reason": (
            f"{recommended['plan_name']} scores higher for this profile by {abs(left['score'] - right['score'])} points."
        ),
        "score_gap": abs(left["score"] - right["score"]),
    }

