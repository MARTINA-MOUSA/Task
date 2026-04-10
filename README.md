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
### v1.2.0 - 2026-04-10
**planner.py / graph.py**
- Added: planner gating to skip unnecessary downstream steps when fallback is already known
- Added: explicit planner trace messages for selected tools
- Improved: heuristic handling for ambiguous wording, unsupported intents, and invalid comparison targets

**retrieval_tool.py**
- Added: strict-to-relaxed retry logic on empty retrieval
- Added: `match_quality` and `retrieval_reason` metadata
- Added: richer retrieval trace logging for partial or relaxed matches

**scoring_tool.py**
- Added: conflicting constraints handling for low-budget + best-coverage requests
- Added: explicit tradeoff reasoning for cost-focused and coverage-focused scenarios
- Added: narrow-gap confidence moderation to reduce overconfidence
- Added: top-plan score breakdown in reasoning output

**comparison_tool.py**
- Added: business-friendly comparison summary in addition to raw score-gap reasoning

**composer.py**
- Added: reasoning deduplication
- Added: retrieval-quality and comparison-summary synthesis in final responses
- Improved: mode-aware fallback and explanation notes

**harness.py / evaluation**
- Added: hidden edge-case scenarios
- Added: checks for unsupported requests, confidence guards, duplicate tool use, fallback-after-tool-issue, and retry traces
- Added: `visible_score`, `hidden_score`, `failed_checks_count`, and richer per-scenario metrics in `outputs/eval_report.json`
- Added: auxiliary unit checks for tool failure, overconfidence, planner-step discipline, and repeated tool calls without progress

**Configuration**
- Unified LLM configuration to use `OPENAI_MODEL=gpt-5.4` only

**New Files**
- `TECHNICAL_REPORT.md`: full system documentation
- `README.md`: setup and usage guide
- `harness.py`: root-level evaluation runner

