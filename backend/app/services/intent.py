from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field

from app.config import settings
from .llm import provider


@dataclass
class Intent:
    semantic_query: str
    occasion: list[str] = field(default_factory=list)
    season: list[str] = field(default_factory=list)
    weather: list[str] = field(default_factory=list)
    style: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    min_rating: float | None = None
    exclude: list[str] = field(default_factory=list)
    llm_used: bool = False

    def to_dict(self):
        return asdict(self)


VOCAB = {
    "occasion": ["wedding", "beach", "vacation", "office", "work", "party", "gym", "travel", "flight", "date", "interview", "hiking"],
    "season": ["spring", "summer", "autumn", "fall", "winter"],
    "weather": ["hot", "warm", "cold", "rain", "rainy", "snow", "humid"],
    "style": ["casual", "formal", "smart casual", "business casual", "elegant", "sporty", "minimal", "vintage", "streetwear", "relaxed"],
    "materials": ["linen", "cotton", "wool", "silk", "denim", "leather", "polyester", "cashmere", "fleece"],
    "colors": ["black", "white", "blue", "red", "green", "beige", "brown", "pink", "purple", "yellow", "grey", "gray", "navy"],
}


def _contains(term: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", text, flags=re.I) is not None


def deterministic_intent(query: str) -> Intent:
    lower = query.lower().strip()
    values = {k: [v for v in terms if _contains(v, lower)] for k, terms in VOCAB.items()}

    max_price = None
    price_patterns = [
        r"(?:under|below|less than|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)",
        r"\$\s*(\d+(?:\.\d+)?)\s*(?:or less|max)",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, lower)
        if match:
            max_price = float(match.group(1))
            break

    min_price = None
    match = re.search(r"(?:over|above|more than|min(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)", lower)
    if match:
        min_price = float(match.group(1))

    min_rating = None
    match = re.search(r"(?:at least|min(?:imum)?)\s*(\d(?:\.\d)?)\s*(?:star|rating)", lower)
    if match:
        min_rating = min(5.0, float(match.group(1)))

    exclude: list[str] = []
    for match in re.finditer(r"(?:no|not|without|exclude)\s+([a-z][a-z\- ]{1,24})", lower):
        phrase = match.group(1).strip().split(" and ")[0].strip()
        phrase = re.split(r"[,.;]", phrase)[0].strip()
        if phrase:
            exclude.append(phrase)

    return Intent(
        semantic_query=query.strip(),
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        exclude=exclude[:5],
        **values,
    )


def parse_intent(query: str) -> Intent:
    base = deterministic_intent(query)
    if not settings.llm_enabled:
        return base
    try:
        llm = provider()
        if llm is None:
            return base
        raw = llm.parse_intent(query)
        allowed = {
            "occasion", "season", "weather", "style", "materials", "colors", "exclude"
        }
        for key in allowed:
            value = raw.get(key)
            if isinstance(value, list):
                setattr(base, key, [str(x).strip() for x in value if str(x).strip()][:10])
        for key in {"min_price", "max_price", "min_rating"}:
            value = raw.get(key)
            if value is not None:
                setattr(base, key, float(value))
        semantic_query = raw.get("semantic_query")
        if isinstance(semantic_query, str) and semantic_query.strip():
            base.semantic_query = semantic_query.strip()
        base.llm_used = True
    except Exception:
        base.llm_used = False
    return base
