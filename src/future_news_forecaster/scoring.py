from __future__ import annotations

import re

from .models import DraftPrediction, Event, EventDossier, FactScenario, ScoreBreakdown
from .text import cosine_overlap


SOURCE_WEIGHT = {
    "Office for National Statistics": 0.92,
    "U.S. Census Bureau": 0.89,
    "sample": 0.72,
}

CATEGORY_TEMPLATE_WEIGHT = {
    "official_release": 0.90,
    "macro_release": 0.86,
    "corporate_release": 0.74,
    "sports": 0.52,
}


def score_event(event: Event, retrieved_example_count: int) -> float:
    source_weight = SOURCE_WEIGHT.get(event.source.name, 0.70)
    template_weight = CATEGORY_TEMPLATE_WEIGHT.get(event.category, 0.55)
    confirmed_bonus = 0.05 if event.status == "confirmed" else 0.0
    time_bonus = 0.03 if event.time_label else 0.0
    retrieval_bonus = min(retrieved_example_count / 10.0, 0.12)
    score = source_weight * 0.45 + template_weight * 0.35 + confirmed_bonus + time_bonus + retrieval_bonus
    return round(min(score, 1.0), 4)


def score_candidate(
    event: Event,
    dossier: EventDossier,
    scenario: FactScenario,
    draft: DraftPrediction,
) -> ScoreBreakdown:
    event_likelihood = event.predictability_score or score_event(event, len(dossier.retrieved_examples))

    template_match = CATEGORY_TEMPLATE_WEIGHT.get(event.category, 0.55)
    style_examples = dossier.retrieved_examples[:3]
    if style_examples:
        style_match = sum(
            cosine_overlap(draft.headline, example.article.title) for example in style_examples
        ) / len(style_examples)
    else:
        style_match = 0.3

    factuality_penalty = 0.0
    reasons: list[str] = []
    if re.search(r"['\"“”]", draft.headline + " " + draft.lead):
        factuality_penalty += 0.08
        reasons.append("Removed trust for direct quotations in a forecast headline.")
    if re.search(r"\d", draft.headline + " " + draft.lead) and "trade" not in " ".join(event.tags):
        factuality_penalty += 0.05
        reasons.append("Penalized unexplained numeric specificity.")
    if scenario.confidence < 0.55:
        factuality_penalty += 0.06
        reasons.append("Scenario confidence is weak for a competition-style submission.")

    total = (
        event_likelihood * 0.40
        + template_match * 0.20
        + max(style_match, 0.0) * 0.25
        + scenario.confidence * 0.15
        - factuality_penalty
    )

    if not reasons:
        reasons.append("Calendar certainty and outlet-style similarity are within acceptable range.")

    return ScoreBreakdown(
        event_likelihood=round(min(event_likelihood, 1.0), 4),
        template_match=round(min(template_match, 1.0), 4),
        style_match=round(min(max(style_match, 0.0), 1.0), 4),
        factuality_penalty=round(min(factuality_penalty, 1.0), 4),
        total=round(max(min(total, 1.0), 0.0), 4),
        reasons=reasons,
    )


def select_portfolio(candidates: list, limit: int) -> list:
    ordered = sorted(candidates, key=lambda item: item.score.total, reverse=True)
    selected = []
    source_caps: dict[str, int] = {}
    for candidate in ordered:
        if len(selected) >= limit:
            break

        source_name = candidate.event.source.name
        count = source_caps.get(source_name, 0)
        if count >= 3:
            continue

        selected.append(candidate)
        source_caps[source_name] = count + 1

    return selected
