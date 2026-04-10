"""LLM-based planner node."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from agentic_insurance.config import OPENAI_API_KEY, OPENAI_MODEL
from agentic_insurance.prompts import PLANNER_SYSTEM_PROMPT
from agentic_insurance.state import AgentState, trace_step

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback when package is unavailable
    OpenAI = None


class PlannerExtracted(BaseModel):
    industry: Literal["Healthcare", "Construction", "Retail", "unknown"] = "unknown"
    region: Literal["Riyadh", "Jeddah", "Dammam", "unknown"] = "unknown"
    budget: Literal["Low", "Medium", "High", "unknown"] = "unknown"
    priority: Literal["cheapest", "balanced", "best coverage", "comparison", "unknown"] = "unknown"
    compare_plans: list[str] = Field(default_factory=list)
    query_type: Literal["recommendation", "comparison", "explanation", "unknown"] = "unknown"


class PlannerPlan(BaseModel):
    extracted: PlannerExtracted
    tools_needed: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    reasoning: list[str] = Field(default_factory=list)


class PlannerNode:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OpenAI is not None else None

    def __call__(self, state: AgentState) -> AgentState:
        trace_step(state, "planner: started")
        try:
            parsed = self._plan(state["user_request"])
        except Exception as exc:
            state["error"] = f"planner failed: {exc}"
            state["needs_clarification"] = True
            state["clarification_question"] = "Could you restate the request with the company industry and region?"
            trace_step(state, f"planner: error -> {state['error']}")
            return state

        if parsed.extracted.query_type == "unknown" and not parsed.needs_clarification:
            state["error"] = "unsupported_request"
            state["needs_clarification"] = False
            state["clarification_question"] = None
            state.setdefault("fallback_or_risk_note", "I cannot answer this with available data.")

        state.setdefault("retrieved_data", {})["planner"] = parsed.model_dump()
        state["plan"] = self._build_plan_steps(parsed.tools_needed)
        state["reasoning"] = parsed.reasoning or [
            f"Extracted industry={parsed.extracted.industry}, region={parsed.extracted.region}, budget={parsed.extracted.budget}, priority={parsed.extracted.priority}.",
        ]
        state["needs_clarification"] = parsed.needs_clarification
        state["clarification_question"] = parsed.clarification_question
        state.setdefault("tools_used", [])
        trace_step(
            state,
            "planner: selected tools "
            + (", ".join(parsed.tools_needed) if parsed.tools_needed else "none"),
        )
        trace_step(state, "planner: completed")
        return state

    def _plan(self, user_request: str) -> PlannerPlan:
        if self.client is None:
            return self._heuristic_plan(user_request)

        try:
            response = self.client.responses.parse(
                model=OPENAI_MODEL,
                input=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_request},
                ],
                text_format=PlannerPlan,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                raise RuntimeError("OpenAI planner returned no structured output")
            return parsed
        except Exception:
            return self._heuristic_plan(user_request)

    def _heuristic_plan(self, user_request: str) -> PlannerPlan:
        lowered = user_request.lower()
        unsupported_intent = any(
            token in lowered
            for token in ("weather", "temperature", "tomorrow", "forecast", "stock price", "traffic")
        )
        supported_signals = any(
            token in lowered
            for token in (
                "healthcare",
                "construction",
                "retail",
                "riyadh",
                "jeddah",
                "dammam",
                "recommend",
                "plan",
                "compare",
                "why",
                "explain",
                "budget",
                "coverage",
                "cheapest",
                "best coverage",
                "affordable",
                "strong",
                "company",
            )
        )

        def _pick(mapping: dict[str, str], fallback: str = "unknown") -> str:
            for needle, value in mapping.items():
                if needle in lowered:
                    return value
            return fallback

        industry = _pick({"healthcare": "Healthcare", "construction": "Construction", "retail": "Retail"})
        region = _pick({"riyadh": "Riyadh", "jeddah": "Jeddah", "dammam": "Dammam"})
        if "cheap" in lowered or "cheapest" in lowered or "low budget" in lowered or "affordable" in lowered:
            budget = "Low"
        elif "best coverage" in lowered or "premium" in lowered or "top coverage" in lowered:
            budget = "High"
        elif any(word in lowered for word in ("balanced", "moderate", "medium")):
            budget = "Medium"
        else:
            budget = "unknown"

        if unsupported_intent:
            query_type = "unknown"
            priority = "unknown"
        elif "compare" in lowered or "vs" in lowered:
            query_type = "comparison"
            priority = "comparison"
        elif "why" in lowered or "explain" in lowered:
            query_type = "explanation"
            priority = "unknown"
        elif "best coverage" in lowered:
            query_type = "recommendation"
            priority = "best coverage"
        elif "cheap" in lowered or "cheapest" in lowered:
            query_type = "recommendation"
            priority = "cheapest"
        elif "balanced" in lowered:
            query_type = "recommendation"
            priority = "balanced"
        elif any(word in lowered for word in ("best", "recommend", "option")):
            query_type = "recommendation"
            priority = "balanced" if budget == "unknown" else "unknown"
        else:
            query_type = "unknown" if not supported_signals else "recommendation"
            priority = "unknown"

        compare_plans = [plan for plan in ("Basic", "Standard", "Premium") if plan.lower() in lowered]
        compare_requires_clarification = query_type == "comparison" and len(compare_plans) < 2
        needs_clarification = query_type != "explanation" and query_type != "unknown" and (
            industry == "unknown" or region == "unknown"
        )
        if compare_requires_clarification:
            needs_clarification = True
        clarification_question = None
        if needs_clarification:
            if compare_requires_clarification:
                clarification_question = "Please specify two valid plan names to compare: Basic, Standard, or Premium."
            else:
                clarification_question = "Could you share the company industry and region so I can recommend safely?"

        tools_needed = ["retrieval_tool"]
        if query_type in {"recommendation", "comparison", "explanation"}:
            tools_needed.append("scoring_tool")
        if query_type == "comparison":
            tools_needed.append("comparison_tool")
        if query_type == "unknown":
            tools_needed = []

        return PlannerPlan(
            extracted=PlannerExtracted(
                industry=industry,
                region=region,
                budget=budget,
                priority=priority,
                compare_plans=compare_plans,
                query_type=query_type,
            ),
            tools_needed=tools_needed,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            reasoning=[
                f"Detected query type {query_type}.",
                f"Extracted industry={industry}, region={region}, budget={budget}, priority={priority}.",
                f"Selected tools: {', '.join(tools_needed) if tools_needed else 'none'}.",
            ],
        )

    def _build_plan_steps(self, tools_needed: list[str]) -> list[str]:
        steps = ["extract supported insurance attributes"]
        if "retrieval_tool" in tools_needed:
            steps.append("retrieve matching customer and package data")
        if "scoring_tool" in tools_needed:
            steps.append("score candidate packages deterministically")
        if "comparison_tool" in tools_needed:
            steps.append("compare the requested plans side by side")
        if not tools_needed:
            steps.append("return a safe fallback response")
        return steps
