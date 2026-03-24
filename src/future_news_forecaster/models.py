from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventSource(StrictModel):
    name: str
    collector: str
    url: str | HttpUrl


class Event(StrictModel):
    event_id: str
    title: str
    date: date
    time_label: str | None = None
    timezone: str | None = None
    status: str = "unknown"
    category: str
    source: EventSource
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    predictability_score: float | None = None


class ArchiveArticle(StrictModel):
    article_id: str
    outlet: str
    title: str
    lead: str
    tags: list[str] = Field(default_factory=list)
    published_at: date | None = None
    url: str | None = None


class RetrievedExample(StrictModel):
    article: ArchiveArticle
    score: float


class EventDossier(StrictModel):
    event: Event
    outlet: str
    context_bullets: list[str]
    retrieved_examples: list[RetrievedExample]


class FactScenario(StrictModel):
    scenario_id: str
    angle: str
    predicted_facts: list[str]
    uncertainties: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class DraftPrediction(StrictModel):
    outlet: str
    headline: str
    lead: str
    rationale: str
    official_note: str


class ScoreBreakdown(StrictModel):
    event_likelihood: float = Field(ge=0.0, le=1.0)
    editorial_fit: float = Field(ge=0.0, le=1.0)
    template_match: float = Field(ge=0.0, le=1.0)
    style_match: float = Field(ge=0.0, le=1.0)
    factuality_penalty: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class ForecastCandidate(StrictModel):
    event: Event
    dossier: EventDossier
    scenario: FactScenario
    draft: DraftPrediction
    score: ScoreBreakdown


class FilteredEventDecision(StrictModel):
    event_id: str
    title: str
    source_name: str
    editorial_fit: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class ForecastRun(StrictModel):
    target_date: date
    outlet: str
    provider: str
    model: str | None = None
    created_at: datetime
    collected_events: list[Event]
    candidates: list[ForecastCandidate]
    filtered_events: list[FilteredEventDecision] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
