"""Evaluation harness for the insurance agent."""

from __future__ import annotations

import json
import pathlib

from agentic_insurance.evaluation.scenarios import SCENARIOS
from agentic_insurance.graph import build_graph
from agentic_insurance.state import build_initial_state

SUPPORTED_PLANS = {"Basic", "Standard", "Premium"}


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def run_evaluation() -> None:
    """Run all scenarios and print a pass/fail summary."""

    app = build_graph()
    total = len(SCENARIOS)
    passed = 0
    results: list[dict[str, object]] = []

    for index, scenario in enumerate(SCENARIOS, start=1):
        config = {"configurable": {"thread_id": f"eval-{index}"}}
        result = app.invoke(build_initial_state(scenario["input"]), config=config)

        if isinstance(result.get("recommendation"), dict):
            plan_name = result["recommendation"].get("plan_name")
        else:
            plan_name = None
        hallucination = plan_name is not None and plan_name not in SUPPORTED_PLANS

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
            checks.append(("trace", len(result.get("execution_trace", [])) > 0 and len(result.get("reasoning", [])) > 0))

        if scenario.get("must_not_hallucinate"):
            no_hallucination = result.get("recommendation") is None or not result["recommendation"].get("plan_name")
            checks.append(("no_hallucination", no_hallucination))

        checks.append(("hallucination_free", not hallucination))
        checks.append(("trace_present", len(result.get("execution_trace", [])) > 0))
        checks.append(("confidence_present", bool(result.get("confidence"))))

        scenario_passed = all(flag for _, flag in checks)
        passed += int(scenario_passed)
        results.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "passed": scenario_passed,
                "recommendation": plan_name,
                "confidence": result.get("confidence"),
                "tools_used": result.get("tools_used", []),
                "checks": {name: flag for name, flag in checks},
                "hallucination": hallucination,
                "hallucinated_plan": plan_name if hallucination else None,
                "note": result.get("fallback_or_risk_note"),
            }
        )

        print(f"[{scenario['id']}] {scenario['name']}: {'PASS' if scenario_passed else 'FAIL'}")
        print(f"  recommendation: {plan_name or 'none'}")
        print(f"  confidence: {result.get('confidence')}")
        print(f"  tools_used: {', '.join(result.get('tools_used', []))}")
        print(f"  checks: {', '.join(f'{name}={flag}' for name, flag in checks)}")
        if hallucination:
            print(f"  hallucination: invalid plan_name={plan_name}")
        if result.get("fallback_or_risk_note"):
            print(f"  note: {result['fallback_or_risk_note']}")
        print()

    score = round(passed / total * 100, 1) if total else 0.0
    print(f"Overall score: {passed}/{total} ({score}%)")

    report = {
        "overall_score": f"{passed}/{total}",
        "pass_rate": round((passed / total) * 100, 1) if total > 0 else 0,
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
