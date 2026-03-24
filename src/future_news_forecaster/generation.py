from __future__ import annotations

import os
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from .models import DraftPrediction, Event, EventDossier, FactScenario, RetrievedExample
from .settings import load_environment


class ScenarioEnvelope(BaseModel):
    context_bullets: list[str] = Field(min_length=3, max_length=8)
    scenarios: list["ScenarioItem"] = Field(min_length=3, max_length=4)


class ScenarioItem(BaseModel):
    angle: str
    predicted_facts: list[str] = Field(min_length=2, max_length=5)
    uncertainties: list[str] = Field(min_length=1, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)


class StoryEnvelope(BaseModel):
    headline: str
    lead: str
    rationale: str
    official_note: str


OUTLET_DOMAIN_MAP = {
    "reuters": ["www.reuters.com", "reuters.com"],
    "associated press": ["apnews.com", "www.apnews.com"],
    "ap": ["apnews.com", "www.apnews.com"],
    "financial times": ["www.ft.com", "ft.com"],
    "bloomberg": ["www.bloomberg.com", "bloomberg.com"],
    "wall street journal": ["www.wsj.com", "wsj.com"],
    "new york times": ["www.nytimes.com", "nytimes.com"],
    "meduza": ["meduza.io", "www.meduza.io"],
    "медуза": ["meduza.io", "www.meduza.io"],
}


class BaseGenerator(ABC):
    provider_name = "base"

    def build_dossier(
        self,
        event: Event,
        outlet: str,
        retrieved_examples: list[RetrievedExample],
    ) -> EventDossier:
        bullets = [
            f"Scheduled slot: {event.title}.",
            f"Source: {event.source.name} ({event.time_label or 'time TBD'} {event.timezone or ''}).".strip(),
            f"Event class: {event.category.replace('_', ' ')}.",
        ]
        if event.description:
            bullets.append(event.description)
        if event.tags:
            bullets.append(f"Keywords: {', '.join(event.tags[:6])}.")
        if retrieved_examples:
            bullets.append(
                "Style anchors: "
                + "; ".join(example.article.title for example in retrieved_examples[:3])
                + "."
            )
        return EventDossier(
            event=event,
            outlet=outlet,
            context_bullets=bullets,
            retrieved_examples=retrieved_examples,
        )

    @abstractmethod
    def generate_scenarios(self, dossier: EventDossier) -> list[FactScenario]:
        raise NotImplementedError

    @abstractmethod
    def generate_story(self, dossier: EventDossier, scenario: FactScenario) -> DraftPrediction:
        raise NotImplementedError


class MockGenerator(BaseGenerator):
    provider_name = "mock"

    def generate_scenarios(self, dossier: EventDossier) -> list[FactScenario]:
        event = dossier.event
        lower = event.title.lower()
        outlet = dossier.outlet

        if "trade" in lower:
            base = [
                (
                    f"{outlet} focuses on a narrower U.S. trade gap for February.",
                    [
                        "The release lands on schedule at 8:30 AM ET.",
                        "Coverage centers on a smaller goods-and-services deficit versus the prior month.",
                        "The lead frames imports as cooling faster than exports.",
                    ],
                    [
                        "The exact size of the monthly swing remains uncertain.",
                        "Exports may partly offset the import-driven move.",
                    ],
                    0.78,
                ),
                (
                    f"{outlet} stresses a still-wide deficit even if the monthly gap improves.",
                    [
                        "The headline keeps the focus on the deficit level rather than the month-on-month change.",
                        "The lead contrasts the new figure with the previous release.",
                    ],
                    ["A softer headline could emerge if the change is only modest."],
                    0.67,
                ),
                (
                    f"{outlet} emphasizes volatility in trade flows rather than a directional call.",
                    [
                        "The story notes uneven import and export movements.",
                        "The lead uses cautious language around February trade conditions.",
                    ],
                    ["This angle is weaker if the official release shows a clean narrowing trend."],
                    0.56,
                ),
            ]
        elif "business insights" in lower:
            base = [
                (
                    f"{outlet} highlights softer UK hiring and persistent cost pressure in the ONS survey.",
                    [
                        "The release is treated as a scheduled business survey rather than breaking news.",
                        "The main media angle is business caution heading into spring.",
                        "The lead ties labour demand to cost and demand conditions.",
                    ],
                    [
                        "The survey may instead foreground pricing or cash-flow stress.",
                        "Hiring language could be replaced with investment or demand language.",
                    ],
                    0.74,
                ),
                (
                    f"{outlet} frames the ONS survey as showing firms remain resilient despite weak demand.",
                    [
                        "The story leans on mixed signals instead of a one-sided deterioration call.",
                        "The lead balances weak demand against signs of operating resilience.",
                    ],
                    ["If the survey is clearly negative, this softer framing will underperform."],
                    0.62,
                ),
                (
                    f"{outlet} focuses on confidence staying subdued while costs keep firms cautious.",
                    [
                        "The headline stays factual and compact.",
                        "The lead points to subdued sentiment in survey language.",
                    ],
                    ["This overlaps heavily with the first scenario and may be less distinctive."],
                    0.58,
                ),
            ]
        elif "economic activity" in lower:
            base = [
                (
                    f"{outlet} says UK real-time indicators point to modest activity with consumers still under pressure.",
                    [
                        "The release is positioned as a pulse check on current activity.",
                        "The lead contrasts soft consumer conditions with steadier aggregate activity.",
                    ],
                    [
                        "The data could skew more positive if mobility and spending indicators improve.",
                        "The headline may pivot to household finances if that becomes the dominant signal.",
                    ],
                    0.73,
                ),
                (
                    f"{outlet} stresses mixed UK indicators as growth remains uneven.",
                    [
                        "The story emphasizes divergence across sectors and households.",
                        "The lead uses mixed-signals language rather than a hard directional call.",
                    ],
                    ["This angle is less sharp if the release strongly favors one theme."],
                    0.64,
                ),
                (
                    f"{outlet} focuses on a fragile recovery signal in the latest UK indicators.",
                    [
                        "The story frames the release as incremental evidence rather than a definitive turning point.",
                        "The lead stays conservative on momentum claims.",
                    ],
                    ["The phrase 'recovery' may be too strong for a cautious official release."],
                    0.55,
                ),
            ]
        else:
            base = [
                (
                    f"{dossier.outlet} ties the scheduled release to a cautious but reportable update.",
                    [
                        "The event is described as calendar-driven and highly likely to be covered.",
                        "The lead keeps to changes versus prior data rather than invented specifics.",
                    ],
                    ["The exact editorial angle depends on the magnitude of the update."],
                    0.60,
                ),
                (
                    f"{dossier.outlet} focuses on continuity and routine release mechanics.",
                    [
                        "The story emphasizes that the publication is expected on schedule.",
                        "The lead avoids strong directional claims.",
                    ],
                    ["This may be too generic if the release contains a clearer signal."],
                    0.51,
                ),
                (
                    f"{dossier.outlet} uses a mixed-signals framing for the event.",
                    [
                        "The article balances positives and negatives.",
                        "The tone stays factual and restrained.",
                    ],
                    ["Mixed framing can underperform if one dimension dominates the release."],
                    0.49,
                ),
            ]

        scenarios = []
        for index, (angle, facts, uncertainties, confidence) in enumerate(base, start=1):
            scenarios.append(
                FactScenario(
                    scenario_id=f"{dossier.event.event_id}-scenario-{index}",
                    angle=angle,
                    predicted_facts=facts,
                    uncertainties=uncertainties,
                    confidence=confidence,
                )
            )
        return scenarios

    def generate_story(self, dossier: EventDossier, scenario: FactScenario) -> DraftPrediction:
        event = dossier.event
        headline = self._headline_for(event, dossier.outlet)
        lead = self._lead_for(event, scenario)
        rationale = (
            f"Built from a scheduled {event.category.replace('_', ' ')} slot, "
            f"{len(dossier.retrieved_examples)} outlet examples, and a conservative scenario-first prompt shape."
        )
        official_note = (
            f"Structured slot: {event.title}. Primary angle: {scenario.angle} "
            f"(confidence {scenario.confidence:.2f})."
        )
        return DraftPrediction(
            outlet=dossier.outlet,
            headline=headline,
            lead=lead,
            rationale=rationale,
            official_note=official_note,
        )

    def _headline_for(self, event: Event, outlet: str) -> str:
        lower = event.title.lower()
        if "trade" in lower:
            return "U.S. trade gap likely narrows in February as imports cool"
        if "business insights" in lower:
            return "UK firms likely stayed cautious on hiring as cost pressure persisted, ONS survey may show"
        if "economic activity" in lower:
            return "UK real-time indicators likely point to modest activity as households stay under pressure"
        if "pension" in lower:
            return "UK pension fund release due Thursday likely keeps focus on asset positioning and funding trends"
        return f"{outlet} likely frames {event.title.lower()} as a scheduled, cautiously directional update"

    def _lead_for(self, event: Event, scenario: FactScenario) -> str:
        first_fact = scenario.predicted_facts[0]
        second_fact = scenario.predicted_facts[1] if len(scenario.predicted_facts) > 1 else scenario.angle
        return (
            f"{event.source.name} is set to publish {event.title} on {event.date.isoformat()} "
            f"at {event.time_label or 'TBD'} {event.timezone or ''}. {first_fact} {second_fact}"
        ).strip()


class OpenAIGenerator(BaseGenerator):
    provider_name = "openai"

    def __init__(self, model: str, web_search_enabled: bool = True) -> None:
        from openai import OpenAI

        self.model = model
        self.web_search_enabled = web_search_enabled
        self.provider_name = "openai+web" if web_search_enabled else "openai"
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def generate_scenarios(self, dossier: EventDossier) -> list[FactScenario]:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You design competition-grade news forecasts from scheduled calendar events. "
                        "Produce only restrained, high-likelihood scenarios. "
                        "If web search is available, use it to verify the official release framing "
                        "and recent outlet coverage before finalizing scenarios."
                    ),
                },
                {"role": "user", "content": self._scenario_prompt(dossier)},
            ],
            text_format=ScenarioEnvelope,
            **self._response_options(dossier),
        )
        parsed = response.output_parsed
        dossier.context_bullets = parsed.context_bullets
        return [
            FactScenario(
                scenario_id=f"{dossier.event.event_id}-scenario-{index}",
                angle=item.angle,
                predicted_facts=item.predicted_facts,
                uncertainties=item.uncertainties,
                confidence=item.confidence,
            )
            for index, item in enumerate(parsed.scenarios, start=1)
        ]

    def generate_story(self, dossier: EventDossier, scenario: FactScenario) -> DraftPrediction:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Write a forecast headline and lead in a restrained agency-news style. "
                        "Do not invent quotes or unsupported numbers. "
                        "If web search is available, use it only to verify official release details "
                        "or recent outlet phrasing relevant to the event."
                    ),
                },
                {"role": "user", "content": self._story_prompt(dossier, scenario)},
            ],
            text_format=StoryEnvelope,
            **self._response_options(dossier),
        )
        parsed = response.output_parsed
        return DraftPrediction(
            outlet=dossier.outlet,
            headline=parsed.headline,
            lead=parsed.lead,
            rationale=parsed.rationale,
            official_note=parsed.official_note,
        )

    @staticmethod
    def _scenario_prompt(dossier: EventDossier) -> str:
        examples = "\n".join(
            f"- {example.article.title}: {example.article.lead}" for example in dossier.retrieved_examples[:5]
        )
        bullets = "\n".join(f"- {bullet}" for bullet in dossier.context_bullets)
        return (
            f"Target outlet: {dossier.outlet}\n"
            f"Event: {dossier.event.title}\n"
            f"Date: {dossier.event.date.isoformat()} {dossier.event.time_label or ''} {dossier.event.timezone or ''}\n"
            f"Category: {dossier.event.category}\n"
            f"Context:\n{bullets}\n\n"
            f"Archive examples:\n{examples}\n\n"
            "Return 3 conservative scenarios with confidence scores. "
            "Favor scheduled-release framing over surprise framing. "
            "If web search is available, prefer the official event source and the target outlet domain."
        )

    @staticmethod
    def _story_prompt(dossier: EventDossier, scenario: FactScenario) -> str:
        examples = "\n".join(
            f"- {example.article.title}" for example in dossier.retrieved_examples[:5]
        )
        facts = "\n".join(f"- {fact}" for fact in scenario.predicted_facts)
        uncertainties = "\n".join(f"- {item}" for item in scenario.uncertainties)
        return (
            f"Outlet: {dossier.outlet}\n"
            f"Event: {dossier.event.title}\n"
            f"Scenario angle: {scenario.angle}\n"
            f"Predicted facts:\n{facts}\n"
            f"Uncertainties:\n{uncertainties}\n"
            f"Style anchors:\n{examples}\n\n"
            "Write one headline and one first paragraph. Keep it factual, compact, and competition-safe. "
            "If web search is available, use it only to validate phrasing and current factual framing."
        )

    def _response_options(self, dossier: EventDossier) -> dict[str, object]:
        if not self.web_search_enabled:
            return {}

        tool: dict[str, object] = {"type": "web_search"}
        allowed_domains = self._allowed_domains(dossier)
        if allowed_domains:
            tool["filters"] = {"allowed_domains": allowed_domains}

        return {
            "tools": [tool],
            "tool_choice": "auto",
            "reasoning": {"effort": "low"},
            "include": ["web_search_call.action.sources"],
        }

    def _allowed_domains(self, dossier: EventDossier) -> list[str]:
        outlet_domains = OUTLET_DOMAIN_MAP.get(dossier.outlet.lower(), [])
        if not outlet_domains:
            return []

        domains: set[str] = set()

        source_host = urlparse(str(dossier.event.source.url)).netloc.lower()
        if source_host:
            domains.add(source_host)
            if source_host.startswith("www."):
                domains.add(source_host[4:])
            else:
                domains.add(f"www.{source_host}")

        for outlet_domain in outlet_domains:
            domains.add(outlet_domain.lower())

        return sorted(domain for domain in domains if domain)


def build_generator(provider: str, model: str, web_search_enabled: bool = True) -> BaseGenerator:
    load_environment()
    if provider == "mock":
        return MockGenerator()
    if provider == "openai":
        return OpenAIGenerator(model=model, web_search_enabled=web_search_enabled)
    if provider == "auto" and os.environ.get("OPENAI_API_KEY"):
        try:
            return OpenAIGenerator(model=model, web_search_enabled=web_search_enabled)
        except Exception:
            return MockGenerator()
    return MockGenerator()
