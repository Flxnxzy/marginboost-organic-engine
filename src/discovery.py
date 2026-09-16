from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import feedparser
import requests
from dateutil import parser as dtparser

from .util import normalize_space, fingerprint


USER_AGENT = "MarginBoostOrganicEngine/1.0 (+https://marginboost.co.za)"


@dataclass
class Item:
    id: str
    source: str
    title: str
    summary: str
    url: str
    published: str | None

    def to_dict(self):
        return asdict(self)


def load_sources(path: str = "config/sources.json") -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    feeds = list(data.get("feeds", []))
    extra = os.getenv("EXTRA_FEEDS", "").strip()
    for i, url in enumerate([x.strip() for x in extra.splitlines() if x.strip()], 1):
        feeds.append({"name": f"extra-{i}", "url": url})
    return feeds


def _fetch_feed(url: str):
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"},
        timeout=20,
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def discover(feeds: Iterable[dict], per_feed: int = 30) -> list[Item]:
    out: list[Item] = []
    for feed in feeds:
        name = normalize_space(feed.get("name", "unknown"))
        url = feed.get("url", "")
        if not url:
            continue
        try:
            parsed = _fetch_feed(url)
        except Exception as exc:
            print(f"[warn] feed failed: {name}: {exc}")
            continue

        for entry in parsed.entries[:per_feed]:
            title = normalize_space(getattr(entry, "title", ""))
            summary = normalize_space(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            link = normalize_space(getattr(entry, "link", ""))
            if not title or not link:
                continue

            published = None
            raw_date = getattr(entry, "published", "") or getattr(entry, "updated", "")
            if raw_date:
                try:
                    published = dtparser.parse(raw_date).isoformat()
                except Exception:
                    published = None

            out.append(Item(
                id=fingerprint(name, title, link),
                source=name,
                title=title,
                summary=summary[:1200],
                url=link,
                published=published,
            ))
    return out
