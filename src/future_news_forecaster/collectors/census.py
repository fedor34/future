from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..models import Event, EventSource
from ..text import normalize_space
from .base import BaseCollector


LINE_RE = re.compile(
    r"^(?P<title>.+?) "
    r"(?P<date>[A-Z][a-z]+ \d{1,2}, \d{4}) "
    r"(?:(?P<status>Suspended) )?"
    r"(?P<time>\d{1,2}:\d{2} [AP]M) "
    r"(?P<period>.+?) "
    r"(?P<release_code>A\d+) "
    r"(?P<period_code>A\d+)$"
)


class CensusCollector(BaseCollector):
    name = "census_release_schedule"
    default_url = "https://www.census.gov/economic-indicators/calendar-listview.html"

    def __init__(self, url: str | None = None, timeout: int = 20) -> None:
        super().__init__(timeout=timeout)
        self.url = url or self.default_url

    def collect(self, target_date: date) -> list[Event]:
        html = self._get(self.url)
        return self.parse(html=html, target_date=target_date, base_url=self.url)

    def parse(self, html: str, target_date: date, base_url: str) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup

        link_map = {
            normalize_space(anchor.get_text(" ", strip=True)): self._absolute(base_url, anchor["href"])
            for anchor in main.find_all("a", href=True)
            if normalize_space(anchor.get_text(" ", strip=True))
        }

        lines = [normalize_space(line) for line in main.get_text("\n").splitlines() if normalize_space(line)]
        events: list[Event] = []

        for line in lines:
            match = LINE_RE.match(line)
            if not match:
                continue

            release_dt = datetime.strptime(
                f"{match.group('date')} {match.group('time')}",
                "%B %d, %Y %I:%M %p",
            )
            if release_dt.date() != target_date:
                continue

            title = match.group("title")
            status = (match.group("status") or "confirmed").lower()

            events.append(
                Event(
                    event_id=self.build_event_id("census", target_date, title),
                    title=title,
                    date=release_dt.date(),
                    time_label=release_dt.strftime("%H:%M"),
                    timezone="America/New_York",
                    status=status,
                    category="macro_release",
                    source=EventSource(
                        name="U.S. Census Bureau",
                        collector=self.name,
                        url=link_map.get(title, base_url),
                    ),
                    description=f"Reference period: {match.group('period')}",
                    tags=self._tags_for_title(title),
                    metadata={
                        "reference_period": match.group("period"),
                        "release_code": match.group("release_code"),
                        "period_code": match.group("period_code"),
                    },
                )
            )

        return events

    @staticmethod
    def _tags_for_title(title: str) -> list[str]:
        lower = title.lower()
        tags = ["census", "official_release", "us"]
        if "trade" in lower:
            tags.extend(["trade", "macro"])
        if "retail" in lower:
            tags.extend(["retail", "macro"])
        if "housing" in lower or "residential" in lower:
            tags.extend(["housing", "macro"])
        return sorted(set(tags))
