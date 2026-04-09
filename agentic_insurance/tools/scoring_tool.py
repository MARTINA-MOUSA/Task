"""Deterministic package scoring and ranking."""

from __future__ import annotations

from typing import Any

from agentic_insurance.data.knowledge_base import RULES


def _coverage_score(plan_name: str) -> int:
    return {"Basic": 10, "Standard": 22, "Premium": 34}.get(plan_name, 0)


def _budget_score(plan_name: str, budget: str) -> int:
    scores = {
        "Low": {"Basic": 20, "Standard": 12, "Premium": -30},
        "Medium": {"Basic": 10, "Standard": 18, "Premium": 8},
        "High": {"Basic": -4, "Standard": 10, "Premium": 20},
    }
    return scores.get(budget, scores["Medium"]).get(plan_name, 0)


def _industry_score(plan_name: str, industry: str) -> int:
    scores = {
        "Healthcare": {"Basic": -12, "Standard": 18, "Premium": 26},
        "Construction": {"Basic": 6, "Standard": 14, "Premium": 6},
        "Retail": {"Basic": 12, "Standard": 12, "Premium": 4},
    }
    return scores.get(industry, {"Basic": 0, "Standard": 8, "Premium": 8}).get(plan_name, 0)


def _region_score(plan_name: str, region: str) -> int:
    scores = {
        "Riyadh": {"Basic": 4, "Standard": 10, "Premium": 2},
        "Jeddah": {"Basic": 8, "Standard": 8, "Premium": 4},
        "Dammam": {"Basic": 6, "Standard": 12, "Premium": 8},
    }
    return scores.get(region, {"Basic": 0, "Standard": 6, "Premium": 4}).get(plan_name, 0)


def _priority_score(plan_name: str, priority: str) -> int:
    scores = {
        "cheapest": {"Basic": 18, "Standard": 6, "Premium": -16},
        "balanced": {"Basic": 6, "Standard": 18, "Premium": 10},
        "best coverage": {"Basic": -20, "Standard": 12, "Premium": 24},
        "comparison": {"Basic": 0, "Standard": 0, "Premium": 0},
    }
    return scores.get(priority, scores["balanced"]).get(plan_name, 0)


def _dependents_score(plan_name: str, dependents_ratio: float) -> int:
    if dependents_ratio > 0.5:
        return {"Basic": -10, "Standard": 10, "Premium": 6}.get(plan_name, 0)
    if dependents_ratio >= 0.4:
        return {"Basic": -2, "Standard": 6, "Premium": 4}.get(plan_name, 0)
    return {"Basic": 2, "Standard": 4, "Premium": 2}.get(plan_name, 0)


def _price_pressure(plan_name: str, budget: str, priority: str) -> int:
    if budget != "Low":
        return 0
    if priority == "best coverage":
        return {"Basic": 0, "Standard": 8, "Premium": -28}.get(plan_name, 0)
    return {"Basic": 10, "Standard": 2, "Premium": -26}.get(plan_name, 0)


def _score_package(package: dict[str, Any], customer_profile: dict[str, Any]) -> tuple[int, list[str]]:
    plan_name = package["plan_name"]
    industry = customer_profile.get("industry", "")
    region = customer_profile.get("region", "")
    budget = customer_profile.get("budget", "Medium")
    priority = customer_profile.get("priority", "balanced")
    dependents_ratio = float(customer_profile.get("dependents_ratio", 0.0) or 0.0)

    score = 50
    breakdown: list[str] = []

    for label, delta in (
        ("coverage", _coverage_score(plan_name)),
        ("budget", _budget_score(plan_name, budget)),
        ("industry", _industry_score(plan_name, industry)),
        ("region", _region_score(plan_name, region)),
        ("priority", _priority_score(plan_name, priority)),
        ("dependents", _dependents_score(plan_name, dependents_ratio)),
        ("price pressure", _price_pressure(plan_name, budget, priority)),
    ):
        score += delta
        if delta:
            breakdown.append(f"{label}: {delta:+d}")

    if plan_name == "Premium" and budget == "Low" and priority != "best coverage":
        score -= 12
        breakdown.append("low-budget premium penalty: -12")

    if plan_name == "Standard" and budget == "Low" and priority == "best coverage":
        score += 10
        breakdown.append("best-coverage compromise bonus: +10")

    return score, breakdown


def _confidence_for_gap(best: int, second: int | None, has_missing_data: bool) -> str:
    gap = (best - second) if second is not None else best
    if has_missing_data:
        return "low"
    if best >= 125 and gap >= 12:
        return "high"
    if best >= 105 and gap >= 8:
        return "medium-high"
    if best >= 85:
        return "medium"
    return "low"


def scoring_tool(candidates: list[dict[str, Any]], customer_profile: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic rules to rank candidate packages."""

    if not candidates:
        return {
            "ranked": [],
            "recommendation": None,
            "reasoning": ["No candidate packages were available for scoring."],
            "confidence": "low",
            "risk_note": "I cannot score this request because no matching packages were retrieved.",
            "flags": ["empty_candidates"],
        }

    ranked: list[dict[str, Any]] = []
    for package in candidates:
        score, breakdown = _score_package(package, customer_profile)
        ranked.append(
            {
                "plan_name": package["plan_name"],
                "network": package["network"],
                "price_range": (package["price_min"], package["price_max"]),
                "coverage": package["coverage"],
                "notes": package["notes"],
                "score": score,
                "score_breakdown": breakdown,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    top = ranked[0]
    second = ranked[1]["score"] if len(ranked) > 1 else None

    budget = customer_profile.get("budget", "Medium")
    priority = customer_profile.get("priority", "balanced")
    dependents_ratio = float(customer_profile.get("dependents_ratio", 0.0) or 0.0)
    conflicting_constraints = budget == "Low" and priority == "best coverage"
    risk_flags: list[str] = []
    reasoning: list[str] = []

    industry = customer_profile.get("industry", "unknown")
    region = customer_profile.get("region", "unknown")
    reasoning.append(f"Matched profile: industry={industry}, region={region}, budget={budget}.")
    reasoning.append(f"Ranked {len(ranked)} plans using deterministic business rules.")

    if conflicting_constraints:
        risk_flags.append("budget_priority_conflict")
        reasoning.append("Conflicting constraints detected: low budget overrides best coverage preference")
    if dependents_ratio > 0.5:
        risk_flags.append("dependents_cost_pressure")
        reasoning.append(
            "A dependents ratio above 0.5 increases cost pressure and pushes the recommendation toward controlled benefit design."
        )

    if budget == "Low":
        allowed = RULES["budget_limits"]["Low"]
        ranked = [item for item in ranked if item["plan_name"] in allowed]
        if ranked:
            top = ranked[0]
            second = ranked[1]["score"] if len(ranked) > 1 else None

    if conflicting_constraints:
        standard_option = next((item for item in ranked if item["plan_name"] == "Standard"), None)
        if standard_option is not None:
            top = standard_option
            ranked = [standard_option] + [item for item in ranked if item["plan_name"] != "Standard"]
        confidence = "medium"
    else:
        confidence = _confidence_for_gap(
            top["score"],
            second,
            has_missing_data=customer_profile.get("industry") == "unknown" or customer_profile.get("region") == "unknown",
        )

    if risk_flags and confidence == "high":
        confidence = "medium"

    risk_note = None
    if "budget_priority_conflict" in risk_flags:
        risk_note = "Low budget conflicts with best-coverage intent, so Standard is the safest compromise."
    elif "dependents_cost_pressure" in risk_flags:
        risk_note = "Dependents pressure raises the value of broader but still cost-aware coverage."

    recommendation = {
        "plan_name": top["plan_name"],
        "network": top["network"],
        "price_range": top["price_range"],
    }

    return {
        "ranked": ranked,
        "recommendation": recommendation,
        "reasoning": reasoning + [f"Top score: {top['score']} for {top['plan_name']}."],
        "confidence": confidence,
        "risk_note": risk_note,
        "flags": risk_flags,
    }
