# TECHNICAL_REPORT

## Section 1 - System Architecture
The system is implemented as a stateful graph-based workflow orchestrated with LangGraph. A user request enters through `main.py`, which initializes a shared `AgentState` object and invokes the compiled graph. The operational flow is `planner -> retrieval -> scoring -> comparison/fallback -> composer`, with an early planner gate that can route directly to fallback when the request is unsupported or incomplete.

The `planner` is responsible for request understanding and task selection. It extracts structured fields such as industry, region, budget, priority, comparison targets, and query type. It also selects the required tools and writes those decisions into shared state. The graph then uses a conditional check to avoid unnecessary downstream tool calls if clarification or fallback is already required.

The `retrieval` node resolves request attributes against the embedded knowledge base. It now performs a strict lookup first, then retries with relaxed matching when no customer profile is found. Retrieval writes back `match_quality` and `retrieval_reason`, which makes partial matches observable and easier to evaluate.

The `scoring` node applies deterministic business rules to candidate packages. It calculates a score for each plan based on coverage, budget, industry, region, priority, dependents ratio, and price pressure. It also handles conflict cases such as low budget plus best coverage, and it lowers confidence when the top score gap is narrow to reduce overconfidence.

The `comparison` node performs side-by-side comparison when the planner detects comparison intent. It reuses the scoring logic, then produces a recommendation reason and a business-oriented comparison summary. All successful and fallback paths terminate in the `composer`, which converts state into the final structured JSON output without changing the output schema.

The shared state object is central to the design. Each node reads from and writes to the same typed state, which carries request metadata, retrieved data, scoring results, comparison results, reasoning, confidence, error flags, retry count, and execution trace entries. This design keeps the system explicit, inspectable, and testable while avoiding hidden side effects.

Conditional routing logic is handled by graph edges instead of ad hoc branching scattered across the codebase. That makes the workflow easier to debug, safer to extend, and easier to evaluate under both visible and hidden test cases.

## Section 1.1 - Agent/Runtime Design
The runtime follows a graph-based, stateful execution model. The planner interprets the request and selects the required tools, retrieval grounds the request against the embedded knowledge base, scoring applies deterministic business rules, comparison or fallback handles conditional branching, and the composer synthesizes the final structured output. This design keeps orchestration explicit, makes state transitions auditable, and separates decision logic from final answer generation.

## ARCHITECTURE_DIAGRAM
```text
User Request
    |
    v
main.py
    |
    v
graph.py
    |
    v
[planner]
    |
    +-------------------+
    |                   |
    v                   v
[retrieval]        [fallback]
    |                   |
    v                   |
[scoring]               |
    |                   |
    +-------------------+
    |                   |
    v                   v
[comparison]       [composer]
    |                   ^
    +---------+---------+
              |
              v
         JSON Output
```

## Section 2 - Framework Justification
LangGraph is a strong fit because the system is stateful, branching, and partially deterministic. It provides a native graph abstraction, supports conditional edges cleanly, and makes node-level testing straightforward. Those properties match this use case better than a generic agent loop.

CrewAI is more role-oriented and optimized for teams of conversational agents. That pattern is useful when multiple persona-based agents debate or collaborate, but it is not ideal for a workflow where deterministic tools must remain in control of scoring and fallback rules.

AutoGen is primarily conversation-centric. It can support agent collaboration, but the coordination overhead is higher than needed for a compact pipeline with a single shared state and explicit routing. For this project, that would add complexity without clear benefit.

A custom orchestration layer would work, but it would recreate state management, branching, checkpointing, and graph visualization patterns that LangGraph already provides. That would slow development and increase maintenance cost.

Tradeoffs remain. LangGraph introduces a learning curve, and graph-based systems can feel more complex than a linear script for very small projects. The added structure is justified here because the workflow already includes routing, retry behavior, fallback paths, and evaluation requirements.

## Section 3 - Model Selection Justification
The system is configured to use `gpt-5.4` as the only LLM model for both planning and final composition. This keeps deployment simple, reduces configuration drift, and guarantees that both model-driven steps operate on the same capability level.

The scoring layer is intentionally deterministic Python rather than an LLM. Insurance recommendation logic needs to be predictable, auditable, and easy to test. Deterministic scoring eliminates hallucination risk in the decision layer, makes tradeoffs explicit, and removes token cost from repeated ranking operations.

`gpt-5.4` is appropriate here because prompts are small, the dataset is limited, and context length is not a practical constraint in this workflow.

Using an LLM in every step would increase cost, latency, and unpredictability. It would also make debugging harder because reasoning would be implicit inside model outputs instead of encoded in transparent business rules.

| Approach | Strengths | Weaknesses |
| --- | --- | --- |
| LLM everywhere | Flexible, natural-language rich, quick to prototype | Higher cost, more latency, harder to audit, more hallucination risk |
| Hybrid approach | Predictable scoring, lower cost, easier testing, clearer control flow | More engineering effort, split logic across model and code |

The hybrid design is therefore a deliberate systems decision rather than a compromise of convenience.

## Section 4 - Evaluation Strategy
Evaluation is implemented with a custom evaluation harness rather than an external observability platform. This project required local, reproducible, scenario-based correctness checks more than hosted tracing infrastructure, so a custom harness was the better fit. The harness runs the real workflow end to end, validates the output against benchmark expectations, and saves a structured artifact to `outputs/eval_report.json`.

The evaluation suite now covers both visible and hidden scenarios:
- 5 visible scenarios for balanced recommendation, cost-focused recommendation, comparison mode, missing-information fallback, and explanation mode
- 8 hidden-style scenarios (H1-H8) for conflicting constraints, unsupported requests, ambiguous wording, partial retrieval behavior, invalid comparison targets, tool failure, overconfidence checks, and repeated-call guards

Edge cases for tool failure, model overconfidence, and repeated tool calls are covered as auxiliary unit checks in `_run_auxiliary_checks()` rather than full end-to-end scenarios, since they require direct tool injection to trigger reliably. This design separates integration-level scenario testing from unit-level tool behavior validation, ensuring both layers are independently measurable.

Metrics include:
- overall score and pass rate
- visible score and hidden score
- plan correctness when an expected plan set exists
- reasoning presence
- expected tool usage
- clarification behavior for underspecified requests
- fallback correctness for unsupported or invalid requests
- execution trace presence
- confidence presence
- confidence guard checks for risky scenarios
- duplicate or unnecessary tool-use detection
- retry trace detection
- hallucination detection on `plan_name`

Hallucination detection verifies that the recommended `plan_name`, when present, is one of `Basic`, `Standard`, or `Premium`. Invalid names are recorded in the evaluation report. The report also records `failed_checks_count`, `failed_checks`, retry visibility, and per-scenario notes to make regression debugging easier.

Confidence scoring is validated both indirectly and directly. The scoring engine reduces confidence when data is missing, when business constraints conflict, and when the gap between the top two plans is narrow. Execution trace validation ensures the workflow remains observable after future code changes.

Hidden edge-case coverage includes:
- Model overconfidence:
  Addressed partially. Confidence is assigned through deterministic scoring logic and is reduced under missing-data, conflict, and narrow-gap conditions. However, the current system does not implement a dedicated statistical calibration component.
- Planner chooses unnecessary steps:
  Addressed partially. The planner selects `query_type` and `tools_needed`, and the graph now short-circuits to fallback when needed. The evaluation layer also checks for duplicate/unnecessary tool usage indirectly, but it does not yet score planner optimality as a standalone metric.

## Section 5 - Limitations & Next Steps
The current system does not support real-time pricing. All pricing is embedded in a fixed local dataset, so recommendations are illustrative rather than production-grade.

The dataset is intentionally small. That keeps the project deterministic and easy to evaluate, but it limits coverage across industries, geographies, and plan variants.

The evaluation harness is strong for local correctness testing, but it is not a replacement for production observability. If the system were deployed, the next step would be to add tracing and monitoring through Langfuse, OpenTelemetry, or an equivalent platform.

Recommended next steps:
- add vector search or retrieval augmentation for larger policy and customer corpora
- add multilingual support so Arabic and English requests can be handled consistently
- introduce external pricing and policy connectors with guardrails
- add calibration logic for confidence beyond deterministic heuristics
- expand the evaluation suite with adversarial and regression-focused scenarios
