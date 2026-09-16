from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta

import requests

from .util import fingerprint, normalize_space


PDS = "https://bsky.social"
APPVIEW_PROXY = "did:web:api.bsky.app#bsky_appview"

SEARCH_QUERIES = [
    "South Africa outsourcing clients",
    "South African outsourcing clients",
    "South Africa BPO",
    "South African BPO",
    "South Africa Upwork clients",
    "South African Upwork clients",
    "South Africa Fiverr clients",
    "South African freelancer clients",
    "South Africa freelance agency",
    "South African freelance agency",
    "Johannesburg Upwork",
    "Johannesburg freelancer clients",
    "Cape Town Upwork",
    "Cape Town freelancer clients",
    "Durban Upwork",
    "Pretoria Upwork",
    "virtual assistant South Africa clients",
    "remote clients South Africa freelancer",
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

# These are the signals that actually describe the user's target market.
STRONG_BPO_TERMS = (
    "bpo",
    "business process outsourcing",
    "outsourcing",
    "outsource",
    "outsourced",
    "upwork",
    "fiverr",
    "freelancer",
    "freelance",
    "virtual assistant",
    "va agency",
    "white label agency",
    "white-label agency",
)

OPERATOR_TERMS = (
    "client",
    "clients",
    "customer",
    "customers",
    "proposal",
    "delivery",
    "deliver",
    "agency",
    "team",
    "contractor",
    "subcontractor",
    "hire",
    "hiring",
    "margin",
    "profit",
    "pricing",
    "scale",
    "scaling",
    "manage",
    "management",
    "workflow",
    "spreadsheet",
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
    "scale",
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

# V3.2 exposed a false positive from a construction/engineering company.
# These sectors use words like "subcontractor", "project" and "manage", but
# they are not MarginBoost's BPO/freelance-outsourcing buyer.
SECTOR_EXCLUSIONS = (
    "construction",
    "engineering",
    "project site",
    "project sites",
    "mobile workforce",
    "workforce management",
    "safety compliance",
    "civil engineer",
    "civil engineering",
    "building contractor",
    "quantity surveyor",
    "architecture firm",
    "mining operation",
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
    if any(term in t for term in SECTOR_EXCLUSIONS):
        return 0, []

    za = _contains_any(t, ZA_TERMS)
    bpo = _contains_any(t, STRONG_BPO_TERMS)
    operator = _contains_any(t, OPERATOR_TERMS)
    intent = _contains_any(t, HIGH_INTENT_TERMS)

    # Hard target gates:
    # - South African context
    # - genuine BPO/freelance/outsourcing signal
    # - evidence they operate client delivery
    # - evidence of an operational question/pain
    if not za or not bpo or not operator or not intent:
        return 0, []

    score = (
        min(len(za), 2) * 5
        + min(len(bpo), 3) * 5
        + min(len(operator), 4) * 2
        + min(len(intent), 4) * 3
    )

    if "?" in t:
        score += 3
    padded = f" {t} "
    if any(p in padded for p in (" i ", " i'm ", " i've ", " my ", " we ", " we're ", " our ")):
        score += 2

    return score, sorted(set(za + bpo + operator + intent))


def _is_recent(created_at: str, hours: int = 168) -> bool:
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception:
        return False


def _session_token() -> str:
    handle = os.getenv("BLUESKY_HANDLE", "").strip()
    password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        raise RuntimeError("Bluesky credentials are not configured")

    response = requests.post(
        f"{PDS}/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["accessJwt"]


def _search(query: str, token: str, limit: int) -> list[dict]:
    response = requests.get(
        f"{PDS}/xrpc/app.bsky.feed.searchPosts",
        params={"q": query, "limit": limit, "sort": "latest"},
        headers={
            "Authorization": f"Bearer {token}",
            "atproto-proxy": APPVIEW_PROXY,
            "User-Agent": "MarginBoostOrganicEngine/3.3 (+https://marginboost.co.za)",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("posts", [])


def search_candidates(own_handle: str = "", limit_per_query: int = 50) -> tuple[list[BlueskyCandidate], dict]:
    token = _session_token()
    seen = set()
    out: list[BlueskyCandidate] = []
    stats = {
        "queries": len(SEARCH_QUERIES),
        "raw_results": 0,
        "unique_results": 0,
        "recent_results": 0,
        "qualified_candidates": 0,
        "query_errors": 0,
    }

    for query in SEARCH_QUERIES:
        try:
            posts = _search(query, token, limit_per_query)
            stats["raw_results"] += len(posts)
        except Exception as exc:
            stats["query_errors"] += 1
            print(f"[warn] authenticated Bluesky search failed for {query!r}: {exc}")
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
            stats["unique_results"] += 1

            handle = (author.get("handle") or "").lower()
            if own_handle and handle == own_handle.lower():
                continue
            if not _is_recent(created_at, 168):
                continue

            stats["recent_results"] += 1

            score, matches = score_candidate(text)
            if score <= 0:
                continue

            reply = record.get("reply") or {}
            root = reply.get("root") or {}

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
                root_uri=root.get("uri") or uri,
                root_cid=root.get("cid") or cid,
                score=score,
                matches=matches,
            ))

    out.sort(key=lambda x: x.score, reverse=True)
    stats["qualified_candidates"] = len(out)
    return out, stats