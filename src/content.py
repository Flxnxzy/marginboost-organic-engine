from __future__ import annotations

import re
from urllib.parse import urlparse

from .util import tracked_url, normalize_space


TEMPLATES = [
    (
        "South African outsourcing operators often lose margin in the handoff between winning client work "
        "and getting it delivered. If you're already using freelancers or subcontractors, the real problem "
        "is usually visibility: cost, delivery, client value and profit in one place.\n\n{cta}"
    ),
    (
        "Winning the client is only half the BPO game. Once delivery is outsourced, you need to know what "
        "the client pays, what fulfilment costs, what is due next and what margin is actually left.\n\n{cta}"
    ),
    (
        "If you're doing Upwork/Fiverr/remote client work and outsourcing parts of the delivery, spreadsheets "
        "get messy fast. A BPO operation needs a clean view of clients, delivery, costs and margin.\n\n{cta}"
    ),
    (
        "A simple way to protect an outsourcing business: track every job as client revenue minus fulfilment "
        "cost before you scale it. More work is not automatically more profit.\n\n{cta}"
    ),
]


def source_slug(source: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    return value[:40] or "organic"


def build_post(item: dict, index: int, marginboost_url: str) -> str:
    title = normalize_space(item.get("title", ""))
    source = source_slug(item.get("source", "organic"))
    link = tracked_url(marginboost_url, source)

    cta = (
        f"MarginBoost is built for South African BPO operators managing outsourced delivery: {link}"
    )

    body = TEMPLATES[index % len(TEMPLATES)].format(cta=cta)

    # Add topic context without copying long source text.
    if title:
        short_title = title[:110].rstrip(" -|:")
        body = f"Topic showing up now: {short_title}\n\n{body}"

    # Keep comfortably below Bluesky's practical text limit by trimming topic context first.
    if len(body) > 290:
        body = TEMPLATES[index % len(TEMPLATES)].format(cta=cta)
    if len(body) > 300:
        body = body[:297].rstrip() + "..."
    return body
