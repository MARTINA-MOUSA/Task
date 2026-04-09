# Agentic Insurance Recommendation System

LangGraph-based insurance plan recommendation workflow with deterministic business rules and GPT-4.1 used only for planning and final composition.

## What is included

- `main.py` entry point for single requests or evaluation runs
- `graph.py` LangGraph orchestration
- `state.py` typed state definition
- `tools/` deterministic retrieval, scoring, comparison, and fallback logic
- `agents/` OpenAI-powered planner and composer nodes
- `data/knowledge_base.py` embedded customers, packages, and business rules
- `evaluation/` 5-scenario harness and scenarios
- `models/output_schema.py` Pydantic output schema

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Add your OpenAI settings to `.env`:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.4
```

## Run

Single request:

```bash
python main.py "Recommend the best plan for a healthcare company in Riyadh."
```

Evaluation:

```bash
python main.py --evaluate
```

## Design notes

- The planner and composer read their model and API settings from `agentic_insurance/config.py`.
- Retrieval, scoring, comparison, and fallback logic are deterministic Python.
- Every node appends to `execution_trace`.
- Clarification is preferred over guessing when the request is underspecified.

## Sample outputs

### S1 Balanced Healthcare Riyadh

```json
{
  "user_request": "Recommend the best plan for a healthcare company in Riyadh.",
  "plan": {"steps": ["extract supported insurance attributes", "retrieve matching customer and package data", "score candidate packages deterministically"]},
  "tools_used": ["retrieval_tool", "scoring_tool"],
  "recommendation": {"plan_name": "Standard", "network": "B", "price_range": [6000, 7500]},
  "confidence": "medium-high"
}
```

### S2 Cost-focused Construction Jeddah

```json
{
  "user_request": "Give me the cheapest acceptable option for a construction customer in Jeddah.",
  "plan": {"steps": ["extract supported insurance attributes", "retrieve matching customer and package data", "score candidate packages deterministically"]},
  "tools_used": ["retrieval_tool", "scoring_tool"],
  "recommendation": {"plan_name": "Basic", "network": "C", "price_range": [4000, 5000]},
  "confidence": "medium"
}
```

### S3 Comparison Retail Dammam

```json
{
  "user_request": "Compare Standard and Premium for a retail customer in Dammam.",
  "tools_used": ["retrieval_tool", "scoring_tool", "comparison_tool"],
  "recommendation": {"plan_name": "Premium", "network": "A", "price_range": [9000, 12000]},
  "comparison_result": {"recommended": "Premium"}
}
```

### S4 Missing information

```json
{
  "user_request": "Recommend a plan for my company.",
  "recommendation": null,
  "confidence": "low",
  "fallback_or_risk_note": "I need the following before I can recommend safely: industry, region."
}
```

### S5 Explanation request

```json
{
  "user_request": "Why did you choose that recommendation?",
  "recommendation": {"plan_name": "Standard", "network": "B", "price_range": [6000, 7500]},
  "confidence": "low",
  "reasoning": ["Detected query type explanation.", "Extracted industry=unknown, region=unknown, budget=unknown, priority=unknown."],
  "execution_trace": ["planner: started", "retrieval_tool: started", "scoring node: started"]
}
```
