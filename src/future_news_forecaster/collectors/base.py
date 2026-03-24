from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from urllib.parse import urljoin

import requests

from ..models import Event
from ..text import slugify


class BaseCollector(ABC):
    name = "base"

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "future-news-forecaster/0.1 "
                    "(calendar-driven headline forecasting; contact: local-runner)"
                )
            }
        )

    @abstractmethod
    def collect(self, target_date: date) -> list[Event]:
        raise NotImplementedError

    def _get(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _absolute(base_url: str, href: str) -> str:
        return urljoin(base_url, href)

    def build_event_id(self, source_name: str, target_date: date, title: str) -> str:
        return f"{slugify(source_name)}-{target_date.isoformat()}-{slugify(title)}"
