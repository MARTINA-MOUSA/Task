"""Deterministic retrieval for customer profiles and candidate packages."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from agentic_insurance.data.knowledge_base import CUSTOMERS, PACKAGES, RULES
from agentic_insurance.state import AgentState, trace_step


INDUSTRY_MAP = {
    "healthcare": "Healthcare",
    "construction": "Construction",
    "retail": "Retail",
}

REGION_MAP = {
    "riyadh": "Riyadh",
    "jeddah": "Jeddah",
    "dammam": "Dammam",
}

BUDGET_MAP = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

PRIORITY_MAP = {
    "cheapest": "cheapest",
    "cheap": "cheapest",
    "balanced": "balanced",
    "best coverage": "best coverage",
    "coverage": "best coverage",
    "comparison": "comparison",
    "compare": "comparison",
}


def _find_keyword(text: str, mapping: dict[str, str]) -> str | None:
    for key, value in mapping.items():
        if key in text:
            return value
    return None


def _closest_customer(industry: str | None, region: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if industry and region:
        for customer_id, profile in CUSTOMERS.items():
            if profile["industry"] == industry and profile["region"] == region:
                return customer_id, deepcopy(profile)
    if industry:
        for customer_id, profile in CUSTOMERS.items():
            if profile["industry"] == industry:
                return customer_id, deepcopy(profile)
    if region:
        for customer_id, profile in CUSTOMERS.items():
            if profile["region"] == region:
                return customer_id, deepcopy(profile)
    return None, None


def _strict_customer_match(industry: str | None, region: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if not industry or not region or "unknown" in {industry, region}:
        return None, None
    for customer_id, profile in CUSTOMERS.items():
        if profile["industry"] == industry and profile["region"] == region:
            return customer_id, deepcopy(profile)
    return None, None


def _candidate_packages(budget: str | None) -> list[dict[str, Any]]:
    allowed = RULES["budget_limits"].get(budget or "Medium", list(PACKAGES))
    return [{"plan_name": name, **deepcopy(PACKAGES[name])} for name in allowed if name in PACKAGES]


def _build_payload(
    query: str,
    extracted: dict[str, Any],
    *,
    relaxed: bool,
) -> dict[str, Any]:
    lowered = query.lower().strip()
    industry = extracted.get("industry")
    region = extracted.get("region")
    budget = extracted.get("budget")
    priority = extracted.get("priority")

    if not industry or industry == "unknown":
        industry = _find_keyword(lowered, INDUSTRY_MAP)
    if not region or region == "unknown":
        region = _find_keyword(lowered, REGION_MAP)
    if not budget or budget == "unknown":
        budget = _find_keyword(lowered, BUDGET_MAP)
    if not priority or priority == "unknown":
        priority = _find_keyword(lowered, PRIORITY_MAP)

    if budget is None:
        budget = "Medium"

    compare_targets = extracted.get("compare_plans") or []
    if not compare_targets:
        found_plans = [name for name in PACKAGES if name.lower() in lowered]
        compare_targets = found_plans[:2]

    query_type = extracted.get("query_type") or (
        "comparison"
        if "compare" in lowered
        else "explanation"
        if "why" in lowered or "explain" in lowered
        else "recommendation"
    )

    if relaxed:
        customer_id, customer_profile = _closest_customer(industry, region)
    else:
        customer_id, customer_profile = _strict_customer_match(industry, region)
    candidate_packages = _candidate_packages(budget)

    if query_type == "explanation":
        customer_profile = customer_profile or {}
        candidate_packages = [{"plan_name": name, **deepcopy(data)} for name, data in PACKAGES.items()]

    return {
        "query": query,
        "query_type": query_type,
        "extracted": {
            "industry": industry or "unknown",
            "region": region or "unknown",
            "budget": budget or "unknown",
            "priority": priority or "unknown",
            "compare_plans": compare_targets,
        },
        "matched_customer_id": customer_id,
        "customer_profile": customer_profile or {},
        "candidate_packages": candidate_packages,
        "rules": deepcopy(RULES),
        "supported_industries": list(INDUSTRY_MAP.values()),
        "supported_regions": list(REGION_MAP.values()),
        "supported_budgets": list(RULES["budget_limits"]),
    }


def _is_empty_payload(payload: dict[str, Any]) -> bool:
    return not payload.get("customer_profile") and payload.get("query_type") != "explanation"


def retrieval_tool(query: str, state: AgentState) -> dict[str, Any]:
    """Search the embedded dataset for supported customer and package data."""

    trace_step(state, "retrieval_tool: started")
    planner = (state.get("retrieved_data") or {}).get("planner", {})
    extracted = planner.get("extracted", {})
    payload = _build_payload(query, extracted, relaxed=False)

    if _is_empty_payload(payload):
        trace_step(state, "retrieval attempt 1 failed, retrying...")
        payload = _build_payload(query, extracted, relaxed=True)
        if _is_empty_payload(payload):
            state["error"] = "retrieval failed: no matching data found after relaxed matching"
            state.setdefault("retrieved_data", {}).update(payload)
            trace_step(state, "retrieval attempt 2 failed, routing to fallback")
            return payload

    state.setdefault("retrieved_data", {}).update(payload)
    if payload.get("customer_profile"):
        trace_step(
            state,
            "retrieval_tool: matched customer "
            f"{payload['matched_customer_id']} for "
            f"{payload['customer_profile']['industry']} in {payload['customer_profile']['region']}",
        )
    else:
        trace_step(state, "retrieval_tool: no customer profile matched, using candidate package set only")
    trace_step(state, f"retrieval_tool: returned {len(payload.get('candidate_packages', []))} candidate packages")
    return payload
