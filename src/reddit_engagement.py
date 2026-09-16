from __future__ import annotations

import os
from .util import tracked_url

PROMO_RULE_PATTERNS = (
    "no self promotion", "no self-promotion", "no advertising", "no advertisements",
    "no promotion", "no promotional", "no solicitation", "no spam", "no marketing",
)

def _rules_text(payload: dict) -> str:
    rules = payload.get("rules") or []
    chunks = []
    for rule in rules:
        chunks.append(str(rule.get("short_name", "")))
        chunks.append(str(rule.get("description", "")))
        chunks.append(str(rule.get("violation_reason", "")))
    return " ".join(chunks).lower()

def subreddit_allows_promo(payload: dict) -> bool:
    text = _rules_text(payload)
    return not any(pattern in text for pattern in PROMO_RULE_PATTERNS)

def allowed_subreddits() -> set[str]:
    raw = os.getenv("REDDIT_COMMENT_ALLOWLIST", "")
    return {
        part.strip().lower().removeprefix("r/")
        for part in raw.split(",")
        if part.strip()
    }

def build_comment(candidate: dict, marginboost_url: str) -> str:
    text = f"{candidate.get('title', '')} {candidate.get('body', '')}".lower()
    content_id = candidate.get("id", "reddit")[:10]
    link = tracked_url(
        marginboost_url,
        source="reddit",
        medium="organic-comment",
        campaign="high-intent-conversations",
        content=content_id,
    )

    if "margin" in text or "profit" in text or "pricing" in text:
        helpful = (
            "The cleanest way to see whether outsourcing is actually worth it is to track "
            "client revenue and fulfilment cost per job, then calculate margin before the job closes."
        )
    elif "upwork" in text or "fiverr" in text or "freelanc" in text:
        helpful = (
            "Once you start winning client work and handing delivery to someone else, the difficult "
            "part is keeping client value, delivery cost, deadline and owner tied to the same job."
        )
    else:
        helpful = (
            "For outsourced delivery, keeping client revenue, fulfilment cost, owner and deadline "
            "on one job record makes margin leakage much easier to spot."
        )

    return (
        f"{helpful}\n\n"
        f"Disclosure: I run MarginBoost, which is built for this workflow for South African "
        f"BPO/freelance operators: {link}"
    )
