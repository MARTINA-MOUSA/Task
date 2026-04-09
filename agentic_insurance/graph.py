"""LangGraph orchestration for the insurance recommendation workflow."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agentic_insurance.agents.composer import ComposerNode
from agentic_insurance.agents.planner import PlannerNode
from agentic_insurance.state import AgentState, trace_step, unique_tools
from agentic_insurance.tools import comparison_tool, fallback_tool, retrieval_tool, scoring_tool


planner_node = PlannerNode()
composer_node = ComposerNode()


def planner(state: AgentState) -> AgentState:
    return planner_node(state)


def retrieval(state: AgentState) -> AgentState:
    trace_step(state, "retrieval node: started")
    if state.get("error"):
        trace_step(state, "retrieval node: skipped because error is already set")
        return state

    planner_data = (state.get("retrieved_data") or {}).get("planner", {})
    query = state["user_request"]
    result = retrieval_tool(query, state)
    state["tools_used"] = unique_tools(state.get("tools_used", []) + ["retrieval_tool"])
    state.setdefault("retrieved_data", {}).update(result)

    fingerprint = (
        result.get("matched_customer_id"),
        tuple(item["plan_name"] for item in result.get("candidate_packages", [])),
        result.get("extracted", {}).get("industry"),
        result.get("extracted", {}).get("region"),
        result.get("query_type"),
    )
    _bump_retry_count(state, fingerprint)
    trace_step(state, f"retrieval node: planner query_type={planner_data.get('extracted', {}).get('query_type', 'unknown')}")
    trace_step(state, "retrieval node: completed")
    return state


def scoring(state: AgentState) -> AgentState:
    trace_step(state, "scoring node: started")
    if state.get("error"):
        trace_step(state, "scoring node: skipped because error is already set")
        return state

    retrieved = state.get("retrieved_data") or {}
    planner_data = retrieved.get("planner", {})
    extracted = planner_data.get("extracted", {})
    customer_profile = dict(retrieved.get("customer_profile") or {})
    request_profile = {
        "industry": extracted.get("industry", "unknown"),
        "region": extracted.get("region", "unknown"),
        "budget": extracted.get("budget", "Medium"),
        "priority": extracted.get("priority", "balanced"),
        "dependents_ratio": customer_profile.get("dependents_ratio", 0.0),
    }
    merged_profile = {**customer_profile, **request_profile}

    candidates = retrieved.get("candidate_packages") or []
    result = scoring_tool(candidates, merged_profile)
    state["scoring_result"] = result
    state["tools_used"] = unique_tools(state.get("tools_used", []) + ["scoring_tool"])
    if result.get("recommendation"):
        state["recommendation"] = result["recommendation"]
    state["reasoning"].extend(result.get("reasoning", []))
    if result.get("risk_note"):
        state["fallback_or_risk_note"] = result["risk_note"]
    state["confidence"] = result.get("confidence", state.get("confidence", "low"))

    fingerprint = (
        state.get("recommendation", {}).get("plan_name") if state.get("recommendation") else None,
        tuple(item["plan_name"] for item in result.get("ranked", [])),
        result.get("confidence"),
    )
    _bump_retry_count(state, fingerprint)
    trace_step(state, f"scoring node: ranked {len(result.get('ranked', []))} plans")
    trace_step(state, "scoring node: completed")
    return state


def comparison(state: AgentState) -> AgentState:
    trace_step(state, "comparison node: started")
    if state.get("error"):
        trace_step(state, "comparison node: skipped because error is already set")
        return state

    retrieved = state.get("retrieved_data") or {}
    planner_data = retrieved.get("planner", {})
    extracted = planner_data.get("extracted", {})
    compare_plans = extracted.get("compare_plans") or []
    if len(compare_plans) < 2:
        ranked = (state.get("scoring_result") or {}).get("ranked", [])
        compare_plans = [item["plan_name"] for item in ranked[:2]]

    if len(compare_plans) < 2:
        state["error"] = "Comparison requires two plans."
        trace_step(state, "comparison node: failed because fewer than two plans were available")
        return state

    profile = dict(retrieved.get("customer_profile") or {})
    profile.update(
        {
            "industry": extracted.get("industry", profile.get("industry", "unknown")),
            "region": extracted.get("region", profile.get("region", "unknown")),
            "budget": extracted.get("budget", profile.get("budget", "Medium")),
            "priority": extracted.get("priority", profile.get("priority", "balanced")),
            "dependents_ratio": profile.get("dependents_ratio", 0.0),
        }
    )
    result = comparison_tool(compare_plans[0], compare_plans[1], profile)
    state["comparison_result"] = result
    state["tools_used"] = unique_tools(state.get("tools_used", []) + ["comparison_tool"])
    if result.get("recommended"):
        state["fallback_or_risk_note"] = result.get("recommendation_reason")
    state["reasoning"].append(result.get("recommendation_reason", "Comparison completed."))
    trace_step(state, f"comparison node: compared {compare_plans[0]} vs {compare_plans[1]}")
    trace_step(state, "comparison node: completed")
    return state


def clarification_check(state: AgentState) -> str:
    if state.get("error"):
        trace_step(state, "clarification check: routing to fallback because error is set")
        return "fallback"
    if state.get("needs_clarification"):
        trace_step(state, "clarification check: routing to fallback because clarification is needed")
        return "fallback"
    if (state.get("retrieved_data") or {}).get("planner", {}).get("extracted", {}).get("query_type") == "comparison":
        return "comparison"
    return "compose"


def post_comparison_check(state: AgentState) -> str:
    if state.get("error"):
        trace_step(state, "post-comparison check: routing to fallback because error is set")
        return "fallback"
    if state.get("needs_clarification"):
        trace_step(state, "post-comparison check: routing to fallback because clarification is needed")
        return "fallback"
    return "compose"


def fallback(state: AgentState) -> AgentState:
    trace_step(state, "fallback node: started")
    fallback_tool(state)
    state["tools_used"] = unique_tools(state.get("tools_used", []))
    state["recommendation"] = None
    trace_step(state, "fallback node: completed")
    return state


def compose(state: AgentState) -> AgentState:
    return composer_node(state)


def _bump_retry_count(state: AgentState, fingerprint: object) -> None:
    retrieved = state.setdefault("retrieved_data", {})
    previous = retrieved.get("_last_fingerprint")
    retry_count = int(retrieved.get("_retry_count", 0))
    if fingerprint == previous:
        retry_count += 1
    else:
        retry_count = 0
    retrieved["_last_fingerprint"] = fingerprint
    retrieved["_retry_count"] = retry_count
    state["retry_count"] = retry_count
    if retry_count >= 3:
        state["error"] = "Repeated tool calls without progress."
        trace_step(state, "graph: stopped after 3 retries without progress")


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner)
    workflow.add_node("retrieval", retrieval)
    workflow.add_node("scoring", scoring)
    workflow.add_node("comparison", comparison)
    workflow.add_node("fallback", fallback)
    workflow.add_node("compose", compose)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "retrieval")
    workflow.add_edge("retrieval", "scoring")
    workflow.add_conditional_edges(
        "scoring",
        clarification_check,
        {
            "fallback": "fallback",
            "comparison": "comparison",
            "compose": "compose",
        },
    )
    workflow.add_conditional_edges(
        "comparison",
        post_comparison_check,
        {
            "fallback": "fallback",
            "compose": "compose",
        },
    )
    workflow.add_edge("fallback", "compose")
    workflow.add_edge("compose", END)
    return workflow.compile(checkpointer=MemorySaver())
