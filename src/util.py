from __future__ import annotations

import hashlib
import re
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def fingerprint(*parts: str) -> str:
    joined = "\n".join(normalize_space(p).lower() for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


def tracked_url(
    base_url: str,
    source: str,
    campaign: str = "organic-engine",
    medium: str = "organic",
    content: str | None = None,
) -> str:
    parsed = urlparse(base_url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q.update({
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign,
    })
    if content:
        q["utm_content"] = content
    return urlunparse(parsed._replace(query=urlencode(q)))