from __future__ import annotations

import re
import unicodedata
from collections import Counter
from math import sqrt


TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9]+", re.UNICODE)


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return cleaned or "item"


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def cosine_overlap(left: str, right: str) -> float:
    left_tokens = Counter(tokenize(left))
    right_tokens = Counter(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0

    shared = sum(left_tokens[token] * right_tokens[token] for token in left_tokens.keys() & right_tokens.keys())
    left_norm = sqrt(sum(value * value for value in left_tokens.values()))
    right_norm = sqrt(sum(value * value for value in right_tokens.values()))
    if not left_norm or not right_norm:
        return 0.0
    return shared / (left_norm * right_norm)
