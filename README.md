# Agentic Insurance Recommendation System

## Overview
This project is a graph-based insurance recommendation system that combines LLM-driven request understanding with deterministic business-rule execution. It produces structured JSON recommendations, safe clarification responses, and evaluation reports for a fixed embedded insurance dataset.

## Architecture
```text
User Request
    |
    v
main.py
    |
    v
graph.py (LangGraph orchestration)
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

## Setup
- Python `3.11+`
- Install dependencies:

```bash
pip install langgraph openai pydantic python-dotenv
```

- Add `OPENAI_API_KEY` to `.env` if you want the planner/composer LLM path enabled. The system still has deterministic fallbacks when the key is absent.

Example `.env`:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.4
```

## Usage
- Run an interactive or single request flow:

```bash
python main.py
```

- Run evaluation:

```bash
python harness.py
```

## Output
- Terminal JSON output for single requests
- `outputs/eval_report.json` for evaluation summaries

## Changelog
### v1.1.0 - 2026-04-10
**retrieval_tool.py**
- Added: retry logic with relaxed matching on empty results
- Added: fallback routing on second failure
- Added: execution_trace logging for retry attempts

**scoring_tool.py**
- Added: conflicting constraints detection (low budget + best coverage)
- Added: explicit tradeoff reasoning in output
- Changed: confidence set to `medium` on conflict

**harness.py**
- Added: hallucination detection check on `plan_name`
- Added: hallucination flag in `outputs/eval_report.json`
- Added: persisted evaluation report output under `outputs/`

**Configuration**
- Changed: unified LLM configuration to use `OPENAI_MODEL=gpt-5.4` only

**New Files**
- `TECHNICAL_REPORT.md`: full system documentation
- `README.md`: setup and usage guide
- `harness.py`: root-level evaluation runner

## Evaluation Results
- `overall_score`: `5/5`
- `pass_rate`: `100.0%`
