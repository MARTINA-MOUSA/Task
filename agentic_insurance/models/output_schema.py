"""Pydantic output schemas for final responses."""

from __future__ import annotations

from typing import Optional, Tuple

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    plan_name: str
    network: str
    price_range: Tuple[int, int]


class AgentOutput(BaseModel):
    user_request: str
    plan: dict
    tools_used: list[str]
    recommendation: Optional[Recommendation] = None
    reasoning: list[str] = Field(default_factory=list)
    confidence: str
    execution_trace: list[str] = Field(default_factory=list)
    fallback_or_risk_note: Optional[str] = None

