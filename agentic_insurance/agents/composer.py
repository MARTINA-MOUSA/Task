"""Final response composer node."""

from __future__ import annotations

import json
from copy import deepcopy

from agentic_insurance.models.output_schema import AgentOutput, Recommendation
from agentic_insurance.config import OPENAI_API_KEY, OPENAI_MODEL
from agentic_insurance.prompts import COMPOSER_SYSTEM_PROMPT
from agentic_insurance.state import AgentState, trace_step, unique_tools

try:  
    from openai import OpenAI
except ImportError:  
    OpenAI = None


class ComposerNode:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OpenAI is not None else None

    def __call__(self, state: AgentState) -> AgentState:
        trace_step(state, "composer: started")
        try:
            output = self._compose(state)
        except Exception as exc:
            state["error"] = f"composer failed: {exc}"
            output = self._deterministic_output(state)

        state["recommendation"] = output.recommendation.model_dump() if output.recommendation else None
        state["confidence"] = output.confidence
        state["fallback_or_risk_note"] = output.fallback_or_risk_note
        state["reasoning"] = output.reasoning
        state["tools_used"] = output.tools_used
        state["plan"] = (
            output.plan.get("steps", state.get("plan", []))
            if isinstance(output.plan, dict)
            else state.get("plan", [])
        )
        trace_step(state, "composer: completed")
        state["final_output"] = output.model_copy(
            update={"execution_trace": state.get("execution_trace", [])}
        ).model_dump()
        return state

    def _compose(self, state: AgentState) -> AgentOutput:
        if self.client is None or state.get("needs_clarification") or state.get("error"):
            return self._deterministic_output(state)

        prompt_state = self._json_safe_state(state)
        response = self.client.responses.parse(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": COMPOSER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_state, ensure_ascii=False),
                },
            ],
            text_format=AgentOutput,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise RuntimeError("OpenAI composer returned no structured output")
        return parsed

    def _deterministic_output(self, state: AgentState) -> AgentOutput:
        retrieved = state.get("retrieved_data") or {}
        scoring = state.get("scoring_result") or {}
        comparison = state.get("comparison_result") or {}
        query_type = ((retrieved.get("planner") or {}).get("extracted") or {}).get("query_type", "recommendation")
        recommendation = state.get("recommendation")
        if recommendation is None and scoring.get("recommendation"):
            recommendation = scoring["recommendation"]
        if recommendation is None and comparison.get("recommended"):
            recommended_name = comparison["recommended"]
            candidate = next((item for item in scoring.get("ranked", []) if item["plan_name"] == recommended_name), None)
            if candidate:
                recommendation = {
                    "plan_name": candidate["plan_name"],
                    "network": candidate["network"],
                    "price_range": candidate["price_range"],
                }

        if state.get("needs_clarification") and state.get("clarification_question"):
            reasoning = list(state.get("reasoning", [])) or [state["clarification_question"]]
            return AgentOutput(
                user_request=state["user_request"],
                plan={"steps": self._final_plan_steps(state)},
                tools_used=unique_tools(state.get("tools_used", [])),
                recommendation=None,
                reasoning=reasoning,
                confidence="low",
                execution_trace=state.get("execution_trace", []),
                fallback_or_risk_note=state.get("clarification_question"),
            )

        if state.get("error") and "unsupported" in (state["error"].lower()):
            return AgentOutput(
                user_request=state["user_request"],
                plan={"steps": self._final_plan_steps(state)},
                tools_used=unique_tools(state.get("tools_used", [])),
                recommendation=None,
                reasoning=["The request is outside the supported dataset."],
                confidence="low",
                execution_trace=state.get("execution_trace", []),
                fallback_or_risk_note="I cannot answer this with available data.",
            )

        reasoning = list(state.get("reasoning", []))
        if retrieved.get("match_quality"):
            reasoning.append(
                f"Retrieval quality: {retrieved.get('match_quality')} ({retrieved.get('retrieval_reason', 'no retrieval note')})."
            )
        if retrieved.get("customer_profile"):
            customer = retrieved["customer_profile"]
            reasoning.append(
                f"Customer profile: {customer.get('industry', 'unknown')} in {customer.get('region', 'unknown')}."
            )
        if scoring.get("recommendation_reason"):
            reasoning.append(scoring["recommendation_reason"])
        if comparison.get("business_summary"):
            reasoning.append(comparison["business_summary"])
        if comparison.get("recommendation_reason"):
            reasoning.append(comparison["recommendation_reason"])

        if not reasoning:
            reasoning = [
                "The recommendation was derived from deterministic package scoring.",
                "Industry risk, region cost pressure, budget fit, and dependents pressure were considered.",
            ]
        reasoning = self._dedupe_reasoning(reasoning)

        if query_type == "comparison":
            fallback_note = comparison.get("business_summary") or state.get("fallback_or_risk_note") or scoring.get("risk_note")
        elif state.get("needs_clarification"):
            fallback_note = state.get("clarification_question")
        elif query_type == "explanation":
            fallback_note = state.get("fallback_or_risk_note") or "Explanation generated from the latest deterministic scoring state."
        else:
            fallback_note = state.get("fallback_or_risk_note") or scoring.get("risk_note")

        return AgentOutput(
            user_request=state["user_request"],
            plan={"steps": self._final_plan_steps(state)},
            tools_used=unique_tools(state.get("tools_used", [])),
            recommendation=Recommendation.model_validate(recommendation) if recommendation else None,
            reasoning=reasoning,
            confidence=state.get("confidence", "medium"),
            execution_trace=state.get("execution_trace", []),
            fallback_or_risk_note=fallback_note,
        )

    def _json_safe_state(self, state: AgentState) -> dict:
        safe = deepcopy(dict(state))
        if safe.get("recommendation") and isinstance(safe["recommendation"].get("price_range"), tuple):
            safe["recommendation"]["price_range"] = list(safe["recommendation"]["price_range"])
        if safe.get("scoring_result"):
            scoring = deepcopy(safe["scoring_result"])
            for item in scoring.get("ranked", []):
                if isinstance(item.get("price_range"), tuple):
                    item["price_range"] = list(item["price_range"])
            safe["scoring_result"] = scoring
        return safe

    def _dedupe_reasoning(self, reasoning: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in reasoning:
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def _final_plan_steps(self, state: AgentState) -> list[str]:
        steps = ["extract supported insurance attributes"]
        if "retrieval_tool" in state.get("tools_used", []) or state.get("retrieved_data"):
            steps.append("retrieve matching customer and package data")
        if "scoring_tool" in state.get("tools_used", []) and state.get("scoring_result"):
            steps.append("score candidate packages deterministically")
        if "comparison_tool" in state.get("tools_used", []) and state.get("comparison_result"):
            steps.append("compare the requested plans side by side")
        if state.get("needs_clarification") or state.get("error"):
            steps.append("return a safe fallback response")
        return steps
