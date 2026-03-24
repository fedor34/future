from __future__ import annotations

from datetime import date

from ..models import Event, EventSource
from .base import BaseCollector


class SampleCollector(BaseCollector):
    name = "sample_calendar"

    def collect(self, target_date: date) -> list[Event]:
        if target_date.isoformat() != "2026-04-02":
            return []

        rows = [
            {
                "title": "Economic activity and social change in the UK, real-time indicators: 2 April 2026",
                "time_label": "09:30",
                "timezone": "Europe/London",
                "status": "confirmed",
                "category": "official_release",
                "source_name": "Office for National Statistics",
                "url": "https://www.ons.gov.uk/releasecalendar?page=4&release-type=type-upcoming",
                "tags": ["ons", "economy", "uk", "official_release"],
            },
            {
                "title": "Business insights and impact on the UK economy: 2 April 2026",
                "time_label": "09:30",
                "timezone": "Europe/London",
                "status": "confirmed",
                "category": "official_release",
                "source_name": "Office for National Statistics",
                "url": "https://www.ons.gov.uk/releasecalendar?page=4&release-type=type-upcoming",
                "tags": ["ons", "business", "uk", "official_release"],
            },
            {
                "title": "Funded occupational pension schemes in the UK: April to September 2025",
                "time_label": "09:30",
                "timezone": "Europe/London",
                "status": "confirmed",
                "category": "official_release",
                "source_name": "Office for National Statistics",
                "url": "https://www.ons.gov.uk/releasecalendar?page=4&release-type=type-upcoming",
                "tags": ["ons", "pensions", "uk", "official_release"],
            },
            {
                "title": "U.S. International Trade in Goods and Services",
                "time_label": "08:30",
                "timezone": "America/New_York",
                "status": "confirmed",
                "category": "macro_release",
                "source_name": "U.S. Census Bureau",
                "url": "https://www.census.gov/economic-indicators/calendar-listview.html",
                "tags": ["census", "trade", "us", "macro", "official_release"],
            },
        ]

        events: list[Event] = []
        for row in rows:
            events.append(
                Event(
                    event_id=self.build_event_id(row["source_name"], target_date, row["title"]),
                    title=row["title"],
                    date=target_date,
                    time_label=row["time_label"],
                    timezone=row["timezone"],
                    status=row["status"],
                    category=row["category"],
                    source=EventSource(
                        name=row["source_name"],
                        collector=self.name,
                        url=row["url"],
                    ),
                    tags=row["tags"],
                )
            )
        return events
