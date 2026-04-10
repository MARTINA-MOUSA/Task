"""Evaluation scenarios for the insurance agent."""

from __future__ import annotations


SCENARIOS = [
    {
        "id": "S1",
        "name": "Balanced Healthcare Riyadh",
        "input": "Recommend the best plan for a healthcare company in Riyadh.",
        "expected_plan": ["Standard", "Premium"],
        "must_contain_reasoning": ["risk", "region", "dependents"],
    },
    {
        "id": "S2",
        "name": "Cost-focused Construction Jeddah",
        "input": "Give me the cheapest acceptable option for a construction customer in Jeddah.",
        "expected_plan": ["Basic", "Standard"],
        "must_contain_reasoning": ["cost", "budget"],
    },
    {
        "id": "S3",
        "name": "Comparison Retail Dammam",
        "input": "Compare Standard and Premium for a retail customer in Dammam.",
        "expected_tool": "comparison_tool",
        "must_contain": ["pros", "cons"],
    },
    {
        "id": "S4",
        "name": "Missing information",
        "input": "Recommend a plan for my company.",
        "expected_behavior": "clarification",
        "must_not_hallucinate": True,
    },
    {
        "id": "S5",
        "name": "Explanation request",
        "input": "Why did you choose Standard over Premium for healthcare customers?",
        "expected_behavior": "trace_explanation",
        "must_contain": ["execution_trace", "reasoning"],
    },
    {
        "id": "H1",
        "name": "Conflicting constraints",
        "input": "Recommend the best coverage option for a construction customer in Jeddah with a low budget.",
        "expected_plan": ["Standard"],
        "must_contain_reasoning": ["conflicting constraints", "tradeoff"],
        "max_confidence": "medium",
    },
    {
        "id": "H2",
        "name": "Unsupported request",
        "input": "What is the weather in Riyadh tomorrow?",
        "expected_behavior": "unsupported_fallback",
        "must_not_hallucinate": True,
    },
    {
        "id": "H3",
        "name": "Ambiguous wording",
        "input": "I need something affordable and strong for my company.",
        "expected_behavior": "clarification",
        "must_not_hallucinate": True,
    },
    {
        "id": "H4",
        "name": "Partial retrieval retry",
        "input": "Recommend the best plan for a healthcare company.",
        "expected_behavior": "clarification",
        "must_contain": ["industry", "region"],
        "expect_retry_trace": True,
    },
    {
        "id": "H5",
        "name": "Invalid comparison target",
        "input": "Compare Gold and Premium for a retail customer in Dammam.",
        "expected_behavior": "fallback_after_tool_issue",
        "must_not_hallucinate": True,
    },
    {
        "id": "H6",
        "name": "Tool failure - unknown industry",
        "input": "Recommend a plan for a mining company in Tabuk.",
        "expected_behavior": "fallback_after_tool_issue",
        "must_not_hallucinate": True,
    },
    {
        "id": "H7",
        "name": "Overconfidence guard - incomplete profile",
        "input": "Recommend the best plan for a healthcare company in Riyadh.",
        "expected_plan": ["Standard", "Premium"],
        "max_confidence": "medium-high",
    },
    {
        "id": "H8",
        "name": "Repeated tool calls without improvement",
        "input": "Recommend a plan for a company.",
        "expected_behavior": "clarification",
        "must_not_hallucinate": True,
    },
]
