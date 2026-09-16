from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

from .util import fingerprint, normalize_space


PUBLIC_API = "https://public.api.bsky.app/xrpc"

SEARCH_QUERIES = [
    '"South Africa" BPO',
    '"South Africa" outsourcing',
    '"South Africa" Upwork',
    '"South Africa" subcontracting',
    '"South Africa" freelancer clients',
    '"Johannesburg" outsourcing',
    '"Johannesburg" Upwork',
    '"Cape Town" outsourcing',
    '"Cape Town" Upwork',
    '"Durban" outsourcing',
    '"Pretoria" outsourcing',
]

ZA_TERMS = (
    "south africa",
    "south african",
    "johannesburg",
    "joburg",
    "cape town",
    "durban",
    "pretoria",
    "gauteng",
    "western cape",
    "kzn",
    "kwazulu-natal",
    "zar",
    " rand",
)

BPO_TERMS = (
    "bpo",
    "business process outsourcing",
    "outsourc",
    "subcontract",
    "white label",
    "white-label",
    "virtual assistant",
    "upwork",
    "fiverr",
    "freelanc",
    "agency",
)

OPERATOR_TERMS = (
    "client",
    "clients",
    "customer",
    "customers",
    "project",
    "delivery",
    "deliver",
    "team",
    "contractor",
    "hire",
    "hiring",
    "proposal",
    "margin",
    "profit",
    "pricing",
    "scale",
    "scaling",
    "manage",
)

HIGH_INTENT_TERMS = (
    "how do i",
    "how do you",
    "how to",
    "need help",
    "any advice",
    "anyone know",
    "looking for",
    "struggling",
    "problem",
    "issue",
    "recommend",
    "what do you use",
    "what software",
    "what tool",
    "manage",
    "track",
    "margin",
    "profit",
    "outsourc",
    "subcontract",
)

NEGATIVE_TERMS = (
    "looking for a job",
    "need a job",
    "job seeker",
    "unemployed",
    "visa",
    "tourism",
    "holiday",
    "invest in south africa",
    "moving to south africa",
)


@dataclass
class BlueskyCandidate:
    id: str
    uri: str
    cid: str
    author_did: str
    author_handle: str
    author_display_name: str
    text: str
    created_at: str
    indexed_at: str
    root_uri: str
    root_cid: str
    score: int
    matches: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _contains_any(text: str, terms) -> list[str]:
    return [term for term in terms if term in text]


def score_candidate(text: str) -> tuple[int, list[str]]:
    t = normalize_space(text).lower()

    if any(term in t for term in NEGATIVE_TERMS):
        return 0, []

    za = _contains_any(t, ZA_TERMS)
    bpo = _contains_any(t, BPO_TERMS)
    operator = _contains_any(t, OPERATOR_TERMS)
    intent = _contains_any(t, HIGH_INTENT_TERMS)

    # Hard qualification:
    # 1) explicitly South African context
    # 2) BPO/freelance/outsourcing context
    # 3) someone actually operating or asking about the workflow
    # 4) a pain/question/operational intent signal
    if not za or not bpo or not operator or not intent:
        return 0, []

    score = (
        min(len(za), 2) * 4
        + min(len(bpo), 3) * 4
        + min(len(operator), 4) * 2
        + min(len(intent), 4) * 3
    )

    # Questions and first-person operational pain deserve priority.
    if "?" in t:
        score += 3
    if any(p in t for p in (" i ", " i'm ", " i've ", " my ", " we ", " we're ", " our ")):
        score += 2

    return score, sorted(set(za + bpo + operator + intent))


def _is_recent(created_at: str, hours: int = 72) -> bool:
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception:
        return False


def search_candidates(own_handle: str = "", limit_per_query: int = 25) -> list[BlueskyCandidate]:
    seen = set()
    out: list[BlueskyCandidate] = []

    for query in SEARCH_QUERIES:
        try:
            response = requests.get(
                f"{PUBLIC_API}/app.bsky.feed.searchPosts",
                params={"q": query, "limit": limit_per_query, "sort": "latest"},
                headers={"User-Agent": "MarginBoostOrganicEngine/3.0 (+https://marginboost.co.za)"},
                timeout=20,
            )
            response.raise_for_status()
            posts = response.json().get("posts", [])
        except Exception as exc:
            print(f"[warn] Bluesky search failed for {query!r}: {exc}")
            continue

        for post in posts:
            uri = post.get("uri", "")
            cid = post.get("cid", "")
            record = post.get("record") or {}
            author = post.get("author") or {}
            text = normalize_space(record.get("text", ""))
            created_at = record.get("createdAt", "") or post.get("indexedAt", "")
            indexed_at = post.get("indexedAt", "")

            if not uri or not cid or not text or uri in seen:
                continue
            seen.add(uri)

            handle = (author.get("handle") or "").lower()
            if own_handle and handle == own_handle.lower():
                continue
            if not _is_recent(created_at, 72):
                continue

            score, matches = score_candidate(text)
            if score <= 0:
                continue

            reply = record.get("reply") or {}
            root = reply.get("root") or {}
            root_uri = root.get("uri") or uri
            root_cid = root.get("cid") or cid

            out.append(BlueskyCandidate(
                id=fingerprint(uri, cid),
                uri=uri,
                cid=cid,
                author_did=author.get("did", ""),
                author_handle=author.get("handle", ""),
                author_display_name=author.get("displayName", ""),
                text=text,
                created_at=created_at,
                indexed_at=indexed_at,
                root_uri=root_uri,
                root_cid=root_cid,
                score=score,
                matches=matches,
            ))

    out.sort(key=lambda x: x.score, reverse=True)
    return out