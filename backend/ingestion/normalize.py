from __future__ import annotations

import hashlib
import html
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

DETAIL_KEYS = {
    "fabric type",
    "material",
    "material type",
    "department",
    "fit type",
    "fit",
    "color",
    "pattern",
    "style",
    "neck style",
    "sleeve type",
    "closure type",
    "care instructions",
    "sole material",
    "outer material",
    "country of origin",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        item = clean_text(value)
        return [item] if item else []
    if isinstance(value, (list, tuple)):
        seen: set[str] = set()
        result = []
        for raw in value:
            item = clean_text(raw)
            key = item.casefold()
            if item and key not in seen:
                seen.add(key)
                result.append(item)
        return result
    return []


def normalize_price(value: Any) -> float | None:
    if value in (None, "", "None", "null"):
        return None
    try:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        price = float(Decimal(str(value)))
        if price < 0 or price > 1_000_000:
            return None
        return round(price, 2)
    except (InvalidOperation, ValueError, TypeError):
        return None


def normalize_rating(value: Any) -> float | None:
    try:
        if value is None:
            return None
        rating = float(value)
        return rating if 0 <= rating <= 5 else None
    except (TypeError, ValueError):
        return None


def normalize_rating_number(value: Any) -> int:
    try:
        number = int(value or 0)
        return max(0, number)
    except (TypeError, ValueError):
        return 0


def normalize_images(value: Any) -> tuple[list[dict[str, Any]], str | None, str | None]:
    if not isinstance(value, list):
        return [], None, None
    cleaned: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item = {
            key: clean_text(raw.get(key)) or None
            for key in ("thumb", "large", "variant", "hi_res")
        }
        if any(item.get(k) for k in ("thumb", "large", "hi_res")):
            cleaned.append(item)
    if not cleaned:
        return [], None, None
    main = next((x for x in cleaned if str(x.get("variant") or "").upper() == "MAIN"), cleaned[0])
    primary = main.get("hi_res") or main.get("large") or main.get("thumb")
    thumb = main.get("thumb") or main.get("large") or main.get("hi_res")
    return cleaned, primary, thumb


def normalize_videos(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for raw in value:
        if isinstance(raw, dict):
            item = {k: clean_text(raw.get(k)) or None for k in ("title", "url", "user_id")}
            if item.get("url"):
                result.append(item)
    return result


def normalize_details(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": clean_text(value)} if clean_text(value) else {}
    if not isinstance(value, dict):
        return {}
    output: dict[str, Any] = {}
    for key, raw in value.items():
        k = clean_text(key)
        if not k:
            continue
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            output[k] = clean_text(raw) if isinstance(raw, str) else raw
        elif isinstance(raw, list):
            output[k] = string_list(raw)
        else:
            output[k] = clean_text(raw)
    return output


def select_details(details: dict[str, Any], max_items: int = 16) -> list[str]:
    selected = []
    for key, value in details.items():
        if key.casefold() in DETAIL_KEYS or any(term in key.casefold() for term in ("material", "fabric", "style", "fit", "color", "sleeve")):
            if isinstance(value, list):
                text = ", ".join(str(x) for x in value[:8])
            else:
                text = clean_text(value)
            if text:
                selected.append(f"{key}: {text}")
        if len(selected) >= max_items:
            break
    return selected


def build_search_document(row: dict[str, Any]) -> str:
    sections: list[str] = []
    if row.get("title"):
        sections.append(f"Title: {row['title']}")
    if row.get("categories"):
        sections.append("Category: " + " > ".join(row["categories"][:12]))
    if row.get("features"):
        sections.append("Features: " + ". ".join(row["features"][:20]))
    if row.get("description"):
        sections.append("Description: " + " ".join(row["description"][:12]))
    detail_lines = select_details(row.get("details") or {})
    if detail_lines:
        sections.append("Attributes: " + ". ".join(detail_lines))
    if row.get("store"):
        sections.append(f"Store: {row['store']}")
    document = "\n".join(sections)
    # BGE-M3 can handle long inputs, but bounded product documents improve throughput and consistency.
    return document[:12000]


def normalize_product(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    parent_asin = clean_text(raw.get("parent_asin"))
    title = clean_text(raw.get("title"))
    if not parent_asin:
        return None, ["missing_parent_asin"]
    if not title:
        return None, ["missing_title"]

    features = string_list(raw.get("features"))
    description = string_list(raw.get("description"))
    categories = string_list(raw.get("categories"))
    details = normalize_details(raw.get("details"))
    images, primary_image, thumbnail_image = normalize_images(raw.get("images"))
    price = normalize_price(raw.get("price"))
    rating = normalize_rating(raw.get("average_rating"))
    rating_number = normalize_rating_number(raw.get("rating_number"))

    if price is None:
        warnings.append("missing_price")
    if not images:
        warnings.append("missing_images")
    if not description:
        warnings.append("missing_description")
    if not features:
        warnings.append("missing_features")
    if not categories:
        warnings.append("missing_categories")
    if rating is None:
        warnings.append("missing_rating")

    bought = raw.get("bought_together")
    bought_together = string_list(bought) if bought else None

    row = {
        "parent_asin": parent_asin,
        "main_category": clean_text(raw.get("main_category")) or None,
        "title": title,
        "average_rating": rating,
        "rating_number": rating_number,
        "price": price,
        "features": features,
        "description": description,
        "images": images,
        "videos": normalize_videos(raw.get("videos")),
        "store": clean_text(raw.get("store")) or None,
        "categories": categories,
        "details": details,
        "bought_together": bought_together,
        "primary_image": primary_image,
        "thumbnail_image": thumbnail_image,
        "category_path": " > ".join(categories) if categories else None,
        "search_document_version": 1,
    }
    row["search_document"] = build_search_document(row)
    row["search_document_hash"] = hashlib.sha256(row["search_document"].encode("utf-8")).hexdigest()
    return row, warnings
