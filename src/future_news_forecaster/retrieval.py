from __future__ import annotations

import json
from pathlib import Path
import re

from .models import ArchiveArticle, Event, RetrievedExample
from .text import cosine_overlap


class ArchiveStore:
    def __init__(self, articles: list[ArchiveArticle]) -> None:
        self.articles = articles

    @classmethod
    def empty(cls) -> "ArchiveStore":
        return cls([])

    @classmethod
    def from_jsonl(cls, path: Path) -> "ArchiveStore":
        articles: list[ArchiveArticle] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            articles.append(ArchiveArticle.model_validate(payload))
        return cls(articles)

    def search(self, event: Event, outlet: str, limit: int = 5) -> list[RetrievedExample]:
        query = " ".join([event.title, event.description or "", " ".join(event.tags)])
        matches: list[RetrievedExample] = []
        for article in self.articles:
            if article.outlet.lower() != outlet.lower():
                continue
            corpus = " ".join([article.title, article.lead, " ".join(article.tags)])
            score = cosine_overlap(query, corpus)
            if event.category in article.tags:
                score += 0.08
            if any(tag in article.tags for tag in event.tags):
                score += 0.06
            matches.append(RetrievedExample(article=article, score=round(min(score, 1.0), 4)))

        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:limit]


def archive_filename_for_outlet(outlet: str) -> str:
    normalized = outlet.strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^\w-]+", "", normalized, flags=re.UNICODE)
    if not normalized:
        normalized = "outlet"
    return f"{normalized}_sample.jsonl"


def default_archive_path(outlet: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    filename = archive_filename_for_outlet(outlet)
    return root / "data" / "archives" / filename


def load_archive_store(outlet: str, archive_dir: Path) -> tuple[ArchiveStore, list[str]]:
    filename = archive_filename_for_outlet(outlet)
    preferred_path = archive_dir / filename
    fallback_path = default_archive_path(outlet)

    for path in [preferred_path, fallback_path]:
        if path.exists():
            return ArchiveStore.from_jsonl(path), []

    warning = (
        f"No local archive for outlet '{outlet}'. Continuing without style examples. "
        f"Add data/archives/{filename} to improve outlet-specific matching."
    )
    return ArchiveStore.empty(), [warning]
