"""Typed state and helpers for the LangGraph workflow."""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_request: str
    plan: list[str]
    tools_used: list[str]
    retrieved_data: Optional[dict[str, Any]]
    scoring_result: Optional[dict[str, Any]]
    comparison_result: Optional[dict[str, Any]]
    needs_clarification: bool
    clarification_question: Optional[str]
    recommendation: Optional[dict[str, Any]]
    reasoning: list[str]
    confidence: str
    execution_trace: list[str]
    fallback_or_risk_note: Optional[str]
    error: Optional[str]
    retry_count: int
    final_output: Optional[dict[str, Any]]


def build_initial_state(user_request: str) -> AgentState:
    return AgentState(
        user_request=user_request,
        plan=[],
        tools_used=[],
        retrieved_data={},
        scoring_result=None,
        comparison_result=None,
        needs_clarification=False,
        clarification_question=None,
        recommendation=None,
        reasoning=[],
        confidence="low",
        execution_trace=[],
        fallback_or_risk_note=None,
        error=None,
        retry_count=0,
        final_output=None,
    )


def trace_step(state: AgentState, message: str) -> AgentState:
    state.setdefault("execution_trace", []).append(message)
    return state


def unique_tools(tools: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            deduped.append(tool)
    return deduped
