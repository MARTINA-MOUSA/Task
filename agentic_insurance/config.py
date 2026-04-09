"""Central configuration for the insurance agent."""

from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

APP_NAME = os.getenv("APP_NAME", "agentic_insurance")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1000"))
