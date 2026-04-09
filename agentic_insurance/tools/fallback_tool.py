"""Safe fallback behavior for missing, unsupported, or ambiguous requests."""

from __future__ import annotations

from agentic_insurance.state import AgentState, trace_step


def fallback_tool(state: AgentState) -> dict[str, object]:
    """Generate clarification or a safe unsupported-request response."""

    error = (state.get("error") or "").lower()
    retrieved = state.get("retrieved_data") or {}
    extracted = retrieved.get("extracted", {})
    missing = [field for field in ("industry", "region") if extracted.get(field) in {None, "", "unknown"}]

    if "unsupported" in error or "available data" in error:
        note = "I cannot answer this with available data."
        state["needs_clarification"] = False
        state["clarification_question"] = None
    else:
        if missing:
            note = f"I need the following before I can recommend safely: {', '.join(missing)}."
        else:
            note = "The request is ambiguous. Please specify the company industry, region, and budget."
        state["needs_clarification"] = True
        state["clarification_question"] = note

    state["fallback_or_risk_note"] = note
    state["confidence"] = "low"
    trace_step(state, "fallback_tool: generated safe fallback response")
    return {
        "needs_clarification": state["needs_clarification"],
        "clarification_question": state.get("clarification_question"),
        "fallback_or_risk_note": note,
    }

