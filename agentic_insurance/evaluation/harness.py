"""Evaluation harness for the insurance agent."""

from __future__ import annotations

import json
import pathlib

from agentic_insurance.agents.planner import PlannerNode
from agentic_insurance.evaluation.scenarios import SCENARIOS
from agentic_insurance.graph import _bump_retry_count, build_graph
from agentic_insurance.state import build_initial_state
from agentic_insurance.tools.scoring_tool import scoring_tool

SUPPORTED_PLANS = {"Basic", "Standard", "Premium"}
CONFIDENCE_ORDER = {"low": 1, "medium": 2, "medium-high": 3, "high": 4}


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _run_auxiliary_checks() -> list[dict[str, object]]:
    planner = PlannerNode()
    checks: list[dict[str, object]] = []

    empty_scoring = scoring_tool([], {"industry": "Healthcare", "region": "Riyadh"})
    checks.append(
        {
            "name": "tool_failure_or_empty_result",
            "passed": empty_scoring.get("recommendation") is None
            and empty_scoring.get("confidence") == "low"
            and "empty_candidates" in empty_scoring.get("flags", []),
            "details": {
                "confidence": empty_scoring.get("confidence"),
                "flags": empty_scoring.get("flags", []),
            },
        }
    )

    conflict_scoring = scoring_tool(
        [
            {"plan_name": "Basic", "network": "C", "price_min": 4000, "price_max": 5000, "coverage": "Low", "notes": ""},
            {"plan_name": "Standard", "network": "B", "price_min": 6000, "price_max": 7500, "coverage": "Medium", "notes": ""},
            {"plan_name": "Premium", "network": "A", "price_min": 9000, "price_max": 12000, "coverage": "High", "notes": ""},
        ],
        {
            "industry": "Construction",
            "region": "Jeddah",
            "budget": "Low",
            "priority": "best coverage",
            "dependents_ratio": 0.3,
        },
    )
    checks.append(
        {
            "name": "model_overconfidence_guard",
            "passed": conflict_scoring.get("recommendation", {}).get("plan_name") == "Standard"
            and conflict_scoring.get("confidence") in {"low", "medium"},
            "details": {
                "recommendation": conflict_scoring.get("recommendation"),
                "confidence": conflict_scoring.get("confidence"),
            },
        }
    )

    unsupported_plan = planner._heuristic_plan("What is the weather in Riyadh tomorrow?")
    focused_plan = planner._heuristic_plan("Recommend the best plan for a healthcare company in Riyadh.")
    checks.append(
        {
            "name": "planner_unnecessary_steps_guard",
            "passed": unsupported_plan.tools_needed == []
            and "comparison_tool" not in focused_plan.tools_needed
            and focused_plan.tools_needed == ["retrieval_tool", "scoring_tool"],
            "details": {
                "unsupported_tools": unsupported_plan.tools_needed,
                "focused_tools": focused_plan.tools_needed,
            },
        }
    )

    retry_state = build_initial_state("synthetic retry test")
    fingerprint = ("same", ("Basic",), "medium")
    for _ in range(4):
        _bump_retry_count(retry_state, fingerprint)
    checks.append(
        {
            "name": "repeated_tool_calls_without_improvement_guard",
            "passed": retry_state.get("error") == "Repeated tool calls without progress."
            and retry_state.get("retry_count", 0) >= 3,
            "details": {
                "error": retry_state.get("error"),
                "retry_count": retry_state.get("retry_count"),
            },
        }
    )

    return checks


def run_evaluation() -> None:
    """Run all scenarios and print a pass/fail summary."""

    app = build_graph()
    total = len(SCENARIOS)
    passed = 0
    results: list[dict[str, object]] = []
    visible_total = sum(1 for scenario in SCENARIOS if scenario["id"].startswith("S"))
    visible_passed = 0
    hidden_total = total - visible_total
    hidden_passed = 0

    for index, scenario in enumerate(SCENARIOS, start=1):
        config = {"configurable": {"thread_id": f"eval-{index}"}}
        result = app.invoke(build_initial_state(scenario["input"]), config=config)
        execution_trace = result.get("execution_trace", [])

        if isinstance(result.get("recommendation"), dict):
            plan_name = result["recommendation"].get("plan_name")
        else:
            plan_name = None
        comparison_result = result.get("comparison_result") or {}
        comparison_plan_names: list[str] = []
        if comparison_result.get("comparison_of"):
            comparison_plan_names.extend([str(item) for item in comparison_result.get("comparison_of", [])])
        if comparison_result.get("left", {}).get("plan_name"):
            comparison_plan_names.append(str(comparison_result["left"]["plan_name"]))
        if comparison_result.get("right", {}).get("plan_name"):
            comparison_plan_names.append(str(comparison_result["right"]["plan_name"]))
        if comparison_result.get("recommended"):
            comparison_plan_names.append(str(comparison_result["recommended"]))
        comparison_hallucination = any(plan not in SUPPORTED_PLANS for plan in comparison_plan_names)
        hallucination = (plan_name is not None and plan_name not in SUPPORTED_PLANS) or comparison_hallucination
        confidence = str(result.get("confidence") or "").lower()
        tools_used = result.get("tools_used", [])
        has_retry_trace = any("retrying" in step.lower() for step in execution_trace)
        failed_checks: list[str] = []

        checks: list[tuple[str, bool]] = []
        if "expected_plan" in scenario:
            checks.append(("plan", plan_name in scenario["expected_plan"]))
        if "must_contain_reasoning" in scenario:
            reasoning = " ".join(result.get("reasoning", []))
            checks.append(("reasoning", _contains_any(reasoning, scenario["must_contain_reasoning"])))
        if scenario.get("expected_tool"):
            checks.append((scenario["expected_tool"], scenario["expected_tool"] in result.get("tools_used", [])))
        if scenario.get("must_contain"):
            result_text = json.dumps(result, default=str)
            checks.append(("content", _contains_any(result_text, scenario["must_contain"])))
        if scenario.get("expected_behavior") == "clarification":
            checks.append(("clarification", bool(result.get("needs_clarification")) or bool(result.get("clarification_question"))))
        if scenario.get("expected_behavior") == "trace_explanation":
            checks.append(("trace", len(execution_trace) > 0 and len(result.get("reasoning", [])) > 0))
        if scenario.get("expected_behavior") == "unsupported_fallback":
            checks.append(("unsupported_fallback", plan_name is None and "available data" in str(result.get("fallback_or_risk_note", "")).lower()))
        if scenario.get("expected_behavior") == "fallback_after_tool_issue":
            checks.append(("fallback_after_tool_issue", bool(result.get("fallback_or_risk_note")) or plan_name is None))

        if scenario.get("must_not_hallucinate"):
            no_hallucination = result.get("recommendation") is None or not result["recommendation"].get("plan_name")
            checks.append(("no_hallucination", no_hallucination))

        if "max_confidence" in scenario:
            checks.append(
                (
                    "confidence_guard",
                    CONFIDENCE_ORDER.get(confidence, 0) <= CONFIDENCE_ORDER.get(str(scenario["max_confidence"]).lower(), 0),
                )
            )
        if "expect_retry_trace" in scenario:
            checks.append(("retry_trace", has_retry_trace == bool(scenario["expect_retry_trace"])))
        checks.append(("no_unnecessary_duplicate_tools", len(tools_used) == len(set(tools_used))))
        checks.append(("hallucination_free", not hallucination))
        checks.append(("trace_present", len(execution_trace) > 0))
        checks.append(("confidence_present", bool(result.get("confidence"))))

        failed_checks = [name for name, flag in checks if not flag]
        scenario_passed = all(flag for _, flag in checks)
        passed += int(scenario_passed)
        if scenario["id"].startswith("S"):
            visible_passed += int(scenario_passed)
        else:
            hidden_passed += int(scenario_passed)
        results.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "passed": scenario_passed,
                "recommendation": plan_name,
                "confidence": result.get("confidence"),
                "tools_used": tools_used,
                "checks": {name: flag for name, flag in checks},
                "failed_checks_count": len(failed_checks),
                "failed_checks": failed_checks,
                "retry_trace_seen": has_retry_trace,
                "hallucination": hallucination,
                "hallucinated_plan": plan_name if hallucination else None,
                "comparison_plan_names": comparison_plan_names,
                "note": result.get("fallback_or_risk_note"),
            }
        )

        print(f"[{scenario['id']}] {scenario['name']}: {'PASS' if scenario_passed else 'FAIL'}")
        print(f"  recommendation: {plan_name or 'none'}")
        print(f"  confidence: {result.get('confidence')}")
        print(f"  tools_used: {', '.join(tools_used)}")
        print(f"  checks: {', '.join(f'{name}={flag}' for name, flag in checks)}")
        if hallucination:
            print(f"  hallucination: invalid plan_name={plan_name}")
        if failed_checks:
            print(f"  failed_checks: {', '.join(failed_checks)}")
        if result.get("fallback_or_risk_note"):
            print(f"  note: {result['fallback_or_risk_note']}")
        print()

    score = round(passed / total * 100, 1) if total else 0.0
    print(f"Overall score: {passed}/{total} ({score}%)")
    auxiliary_checks = _run_auxiliary_checks()
    auxiliary_passed = sum(1 for check in auxiliary_checks if check["passed"])
    print(f"Auxiliary checks: {auxiliary_passed}/{len(auxiliary_checks)}")

    report = {
        "overall_score": f"{passed}/{total}",
        "pass_rate": round((passed / total) * 100, 1) if total > 0 else 0,
        "visible_score": f"{visible_passed}/{visible_total}",
        "hidden_score": f"{hidden_passed}/{hidden_total}" if hidden_total > 0 else "0/0",
        "auxiliary_checks_score": f"{auxiliary_passed}/{len(auxiliary_checks)}",
        "auxiliary_checks": auxiliary_checks,
        "scenarios": results,
    }
    output_path = pathlib.Path("outputs") / "eval_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    print(f"\nEval report saved -> {output_path}")


if __name__ == "__main__":
    run_evaluation()
