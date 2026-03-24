from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DraftPrediction, Event, EventDossier, FactScenario, RetrievedExample, ScoreBreakdown
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


@dataclass(frozen=True)
class EditorialProfile:
    base: float
    threshold: float
    category_weights: dict[str, float]
    tag_weights: dict[str, float]
    keyword_weights: dict[str, float]
    penalties: dict[str, float]


GENERIC_PROFILE = EditorialProfile(
    base=0.30,
    threshold=0.36,
    category_weights={
        "macro_release": 0.16,
        "official_release": 0.11,
        "corporate_release": 0.08,
        "sports": -0.04,
    },
    tag_weights={
        "economy": 0.08,
        "business": 0.07,
        "trade": 0.10,
        "macro": 0.10,
        "official_release": 0.05,
        "uk": 0.03,
        "us": 0.03,
        "europe": 0.03,
    },
    keyword_weights={
        "inflation": 0.10,
        "rates": 0.08,
        "trade": 0.10,
        "gdp": 0.10,
        "jobs": 0.10,
        "econom": 0.08,
        "business": 0.06,
        "consumer": 0.05,
    },
    penalties={
        "sports": 0.10,
    },
)


EDITORIAL_PROFILES = {
    "reuters": EditorialProfile(
        base=0.54,
        threshold=0.34,
        category_weights={
            "macro_release": 0.18,
            "official_release": 0.15,
            "corporate_release": 0.10,
        },
        tag_weights={
            "economy": 0.10,
            "business": 0.08,
            "trade": 0.14,
            "macro": 0.13,
            "official_release": 0.06,
            "uk": 0.05,
            "us": 0.05,
            "europe": 0.04,
            "pensions": 0.05,
            "retail": 0.05,
        },
        keyword_weights={
            "inflation": 0.10,
            "trade": 0.12,
            "gdp": 0.10,
            "econom": 0.08,
            "survey": 0.06,
            "business": 0.06,
            "consumer": 0.05,
        },
        penalties={},
    ),
    "bloomberg": EditorialProfile(
        base=0.49,
        threshold=0.36,
        category_weights={
            "macro_release": 0.18,
            "official_release": 0.13,
            "corporate_release": 0.11,
        },
        tag_weights={
            "economy": 0.10,
            "business": 0.08,
            "trade": 0.12,
            "macro": 0.12,
            "official_release": 0.05,
            "us": 0.05,
            "uk": 0.04,
            "europe": 0.04,
            "pensions": 0.03,
        },
        keyword_weights={
            "inflation": 0.10,
            "rates": 0.10,
            "trade": 0.10,
            "econom": 0.08,
            "market": 0.08,
        },
        penalties={},
    ),
    "financial times": EditorialProfile(
        base=0.46,
        threshold=0.38,
        category_weights={
            "macro_release": 0.16,
            "official_release": 0.12,
            "corporate_release": 0.11,
        },
        tag_weights={
            "economy": 0.09,
            "business": 0.09,
            "trade": 0.10,
            "macro": 0.10,
            "official_release": 0.04,
            "uk": 0.05,
            "europe": 0.05,
            "us": 0.03,
            "pensions": 0.04,
        },
        keyword_weights={
            "inflation": 0.09,
            "rates": 0.09,
            "trade": 0.09,
            "econom": 0.08,
            "business": 0.07,
        },
        penalties={},
    ),
    "associated press": EditorialProfile(
        base=0.40,
        threshold=0.38,
        category_weights={
            "macro_release": 0.14,
            "official_release": 0.09,
            "corporate_release": 0.06,
        },
        tag_weights={
            "economy": 0.08,
            "business": 0.05,
            "trade": 0.09,
            "macro": 0.08,
            "us": 0.06,
            "uk": 0.03,
            "official_release": 0.04,
        },
        keyword_weights={
            "inflation": 0.08,
            "trade": 0.08,
            "jobs": 0.08,
            "econom": 0.06,
        },
        penalties={},
    ),
    "ap": EditorialProfile(
        base=0.40,
        threshold=0.38,
        category_weights={
            "macro_release": 0.14,
            "official_release": 0.09,
            "corporate_release": 0.06,
        },
        tag_weights={
            "economy": 0.08,
            "business": 0.05,
            "trade": 0.09,
            "macro": 0.08,
            "us": 0.06,
            "uk": 0.03,
            "official_release": 0.04,
        },
        keyword_weights={
            "inflation": 0.08,
            "trade": 0.08,
            "jobs": 0.08,
            "econom": 0.06,
        },
        penalties={},
    ),
    "meduza": EditorialProfile(
        base=0.18,
        threshold=0.52,
        category_weights={
            "macro_release": 0.18,
            "official_release": 0.02,
            "corporate_release": 0.04,
        },
        tag_weights={
            "economy": 0.14,
            "business": 0.06,
            "trade": 0.18,
            "macro": 0.16,
            "official_release": 0.03,
            "europe": 0.10,
            "us": 0.08,
            "uk": 0.02,
            "russia": 0.28,
            "ukraine": 0.30,
            "sanctions": 0.24,
            "politics": 0.18,
        },
        keyword_weights={
            "trade": 0.12,
            "tariff": 0.12,
            "sanction": 0.14,
            "inflation": 0.10,
            "econom": 0.08,
            "oil": 0.10,
            "gas": 0.10,
            "war": 0.14,
        },
        penalties={
            "pensions": 0.22,
            "retail": 0.05,
        },
    ),
    "медуза": EditorialProfile(
        base=0.18,
        threshold=0.52,
        category_weights={
            "macro_release": 0.18,
            "official_release": 0.02,
            "corporate_release": 0.04,
        },
        tag_weights={
            "economy": 0.14,
            "business": 0.06,
            "trade": 0.18,
            "macro": 0.16,
            "official_release": 0.03,
            "europe": 0.10,
            "us": 0.08,
            "uk": 0.02,
            "russia": 0.28,
            "ukraine": 0.30,
            "sanctions": 0.24,
            "politics": 0.18,
        },
        keyword_weights={
            "trade": 0.12,
            "tariff": 0.12,
            "sanction": 0.14,
            "inflation": 0.10,
            "econom": 0.08,
            "oil": 0.10,
            "gas": 0.10,
            "war": 0.14,
        },
        penalties={
            "pensions": 0.22,
            "retail": 0.05,
        },
    ),
}


def normalize_outlet_name(outlet: str) -> str:
    return re.sub(r"\s+", " ", outlet.strip().lower())


def get_editorial_profile(outlet: str) -> EditorialProfile:
    return EDITORIAL_PROFILES.get(normalize_outlet_name(outlet), GENERIC_PROFILE)


def score_editorial_fit(
    event: Event,
    outlet: str,
    retrieved_examples: list[RetrievedExample],
) -> tuple[float, list[str], float]:
    profile = get_editorial_profile(outlet)
    score = profile.base
    reasons: list[str] = []
    title_blob = f"{event.title} {event.description or ''}".lower()
    applied_keywords: list[str] = []
    applied_tags: list[str] = []
    penalized_tags: list[str] = []

    category_delta = profile.category_weights.get(event.category, 0.0)
    if category_delta:
        score += category_delta
        reasons.append(f"Outlet profile allows {event.category.replace('_', ' ')} coverage.")

    for tag in sorted(set(event.tags)):
        tag_delta = profile.tag_weights.get(tag, 0.0)
        if tag_delta:
            score += tag_delta
            applied_tags.append(tag)

        penalty = profile.penalties.get(tag, 0.0)
        if penalty:
            score -= penalty
            penalized_tags.append(tag)

    for keyword, keyword_delta in profile.keyword_weights.items():
        if keyword in title_blob:
            score += keyword_delta
            applied_keywords.append(keyword)

    if applied_tags:
        reasons.append(f"Topic overlap with outlet interests: {', '.join(applied_tags[:4])}.")
    if applied_keywords:
        reasons.append(f"Headline keywords match outlet priorities: {', '.join(applied_keywords[:3])}.")
    if penalized_tags:
        reasons.append(f"Low-fit topic markers for this outlet: {', '.join(penalized_tags[:3])}.")

    if retrieved_examples:
        archive_tags = {
            tag
            for example in retrieved_examples[:5]
            for tag in example.article.tags
        }
        overlap = sorted(set(event.tags) & archive_tags)
        archive_bonus = min(0.18, 0.05 + len(overlap) * 0.035)
        score += archive_bonus
        if overlap:
            reasons.append(f"Archive coverage supports this topic: {', '.join(overlap[:4])}.")
        else:
            reasons.append("Archive has same-outlet examples, but topic overlap is limited.")
    else:
        reasons.append("No same-outlet archive evidence was found for this topic.")

    threshold = profile.threshold
    if retrieved_examples:
        threshold = max(0.30, threshold - 0.05)

    if normalize_outlet_name(outlet) not in EDITORIAL_PROFILES and not retrieved_examples:
        reasons.append("Outlet has no explicit editorial profile yet; using a generic broad-news fallback.")

    score = round(max(min(score, 1.0), 0.0), 4)
    threshold = round(max(min(threshold, 1.0), 0.0), 4)
    return score, reasons[:4], threshold


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
    editorial_fit = float(event.metadata.get("editorial_fit_score", 0.0))
    editorial_reasons = list(event.metadata.get("editorial_fit_reasons", []))

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
    if editorial_fit < 0.45:
        factuality_penalty += 0.05
        reasons.append("Outlet-topic fit is weak, so this candidate is less likely to be published.")

    total = (
        event_likelihood * 0.27
        + editorial_fit * 0.28
        + template_match * 0.15
        + max(style_match, 0.0) * 0.18
        + scenario.confidence * 0.12
        - factuality_penalty
    )

    combined_reasons = [*editorial_reasons, *reasons]
    if not combined_reasons:
        combined_reasons.append("Calendar certainty, outlet fit and style similarity are within acceptable range.")

    return ScoreBreakdown(
        event_likelihood=round(min(event_likelihood, 1.0), 4),
        editorial_fit=round(min(max(editorial_fit, 0.0), 1.0), 4),
        template_match=round(min(template_match, 1.0), 4),
        style_match=round(min(max(style_match, 0.0), 1.0), 4),
        factuality_penalty=round(min(factuality_penalty, 1.0), 4),
        total=round(max(min(total, 1.0), 0.0), 4),
        reasons=combined_reasons[:6],
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
