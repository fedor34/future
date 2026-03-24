from __future__ import annotations

from datetime import date, datetime

from bs4 import BeautifulSoup

from ..models import Event, EventSource
from ..text import normalize_space
from .base import BaseCollector


class ONSCollector(BaseCollector):
    name = "ons_release_calendar"
    default_url = "https://www.ons.gov.uk/releasecalendar?page=4&release-type=type-upcoming"

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

        for index in range(len(lines) - 4):
            if lines[index + 1] != "Release date:":
                continue
            if lines[index + 3] != "|":
                continue

            title = lines[index]
            release_label = lines[index + 2]
            status = lines[index + 4]
            try:
                release_dt = datetime.strptime(release_label, "%d %B %Y %I:%M%p")
            except ValueError:
                continue

            if release_dt.date() != target_date:
                continue

            events.append(
                Event(
                    event_id=self.build_event_id("ons", target_date, title),
                    title=title,
                    date=release_dt.date(),
                    time_label=release_dt.strftime("%H:%M"),
                    timezone="Europe/London",
                    status=status.lower(),
                    category="official_release",
                    source=EventSource(
                        name="Office for National Statistics",
                        collector=self.name,
                        url=link_map.get(title, base_url),
                    ),
                    tags=self._tags_for_title(title),
                    metadata={"release_time_raw": release_label},
                )
            )

        return events

    @staticmethod
    def _tags_for_title(title: str) -> list[str]:
        lower = title.lower()
        tags = ["ons", "official_release", "uk"]
        if "business" in lower:
            tags.append("business")
        if "economic" in lower:
            tags.append("economy")
        if "social change" in lower:
            tags.append("social")
        if "pension" in lower:
            tags.append("pensions")
        return sorted(set(tags))
