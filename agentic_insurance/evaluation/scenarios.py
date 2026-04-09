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
        "input": "Why did you choose that recommendation?",
        "expected_behavior": "trace_explanation",
        "must_contain": ["execution_trace", "reasoning"],
    },
]

