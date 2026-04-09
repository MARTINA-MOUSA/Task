# TECHNICAL_REPORT

## Section 1 - System Architecture
The system uses a graph-based workflow orchestrated with LangGraph. A user request enters through `main.py`, which initializes a shared `AgentState` object and invokes the graph. The graph runs the following sequence: `planner -> retrieval -> scoring -> comparison/fallback -> composer`.

The `planner` extracts structured request attributes such as industry, region, budget, priority, and query type. The `retrieval` node resolves those attributes against the embedded knowledge base. The `scoring` node ranks insurance packages deterministically. If the request is a package comparison, the graph routes to `comparison`; if information is missing or retrieval fails, it routes to `fallback`. All successful and fallback paths end in `composer`, which emits the final JSON response.

The shared state object is central to the design. Each node reads from and writes to the same typed state, which carries request metadata, retrieved data, scoring results, reasoning, confidence, error flags, and execution trace entries. This keeps the workflow explicit and testable while avoiding hidden side effects.

Conditional routing logic is handled by graph edges rather than ad hoc branching spread across the codebase. This makes flow control easier to inspect, easier to test, and safer to evolve.

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
    v
[retrieval]
    |
    v
[scoring]
    |
    +-------------------+
    |                   |
    v                   v
[comparison]       [fallback]
    |                   |
    +---------+---------+
              |
              v
          [composer]
              |
              v
         JSON Output
```

## Section 2 - Framework Justification
LangGraph is a strong fit because the system is stateful, branching, and partially deterministic. It provides a native graph abstraction, supports conditional edges cleanly, and makes node-level testing straightforward. Those properties match this use case better than a generic agent loop.

CrewAI is more role-oriented and optimized for teams of conversational agents. That pattern is useful when multiple persona-based agents debate or collaborate, but it is not ideal for a workflow where deterministic tools must remain in control of scoring and fallback rules.

AutoGen is primarily conversation-centric. It can support agent collaboration, but the coordination overhead is higher than needed for a compact pipeline with a single shared state and explicit routing. For this project, that would add complexity without clear benefit.

A custom orchestration layer would work, but it would recreate state management, branching, checkpointing, and graph visualization patterns that LangGraph already provides. That would slow development and increase maintenance cost.

Tradeoffs remain. LangGraph introduces a learning curve, and graph-based systems can feel more complex than a linear script for very small projects. The added structure is justified here because the workflow already has branching, fallback behavior, and evaluation requirements.

## Section 3 - Model Selection Justification
The system is configured to use `gpt-5.4` as the only LLM model for both planning and final composition. This keeps deployment simple, reduces configuration drift, and guarantees that both model-driven steps operate on the same capability level.

The scoring node is intentionally deterministic Python rather than an LLM. Insurance recommendation logic needs to be predictable, auditable, and easy to test. Deterministic scoring eliminates hallucination risk in the decision layer, makes tradeoffs explicit, and removes token cost from repeated ranking operations.

Using an LLM in every step would increase cost, latency, and unpredictability. It would also make debugging harder because reasoning would be implicit inside model outputs instead of encoded in transparent business rules.

| Approach | Strengths | Weaknesses |
| --- | --- | --- |
| LLM everywhere | Flexible, natural-language rich, quick to prototype | Higher cost, more latency, harder to audit, more hallucination risk |
| Hybrid approach | Predictable scoring, lower cost, easier testing, clearer control flow | More engineering effort, split logic across model and code |

The hybrid design is therefore a deliberate systems decision rather than a compromise of convenience.

## Section 4 - Evaluation Strategy
Evaluation is based on 5 visible scenarios that cover balanced recommendation, cost-focused recommendation, comparison mode, missing-information fallback, and explanation behavior. Each scenario executes the real workflow end to end.

Metrics include:
- overall score and pass rate
- plan correctness when an expected plan set exists
- reasoning presence
- expected tool usage
- clarification behavior for underspecified requests
- execution trace presence
- confidence presence
- hallucination detection on `plan_name`

Hallucination detection verifies that the recommended `plan_name`, when present, is one of `Basic`, `Standard`, or `Premium`. Invalid names are recorded in the evaluation report. The report is saved to `outputs/eval_report.json`, which provides a structured artifact instead of console output alone.

Confidence scoring is also validated indirectly through scenario checks and directly recorded in the report. Execution trace validation ensures the workflow remains observable after future code changes.

