"""Normalize and deserialize collected image references.

This module handles metadata only; it does not claim URLs are permanent assets.
"""
from __future__ import annotations

import json
from typing import Any


def normalize_image_list(value: Any, *, limit: int = 20) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for image in value:
        url = image if isinstance(image, str) else image.get("url") if isinstance(image, dict) else None
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        result.append({"url": url})
        if len(result) >= limit:
            break
    return result


def decode_image_list(field: Any) -> list[dict[str, str]]:
    """Handle Feishu Bitable text cells returned as strings or rich-text spans."""
    if isinstance(field, list):
        raw = "".join(str(part.get("text") or "") for part in field if isinstance(part, dict))
    elif isinstance(field, dict):
        raw = str(field.get("text") or "")
    elif isinstance(field, str):
        raw = field
    else:
        return []
    try:
        return normalize_image_list(json.loads(raw))
    except (ValueError, TypeError):
        return []
