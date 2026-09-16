from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta

from .reddit_client import RedditClient
from .util import fingerprint, normalize_space

SUBREDDITS = ["southafrica", "capetown", "johannesburg"]
QUERIES = ["Upwork", "outsourcing", "BPO", "freelance clients", "subcontracting", "virtual assistant clients"]

ZA_CONTEXT = (
    "south africa", "south african", "johannesburg", "joburg", "cape town",
    "durban", "pretoria", "gauteng", "western cape", "kzn", "rand", "zar",
)
BPO_CONTEXT = (
    "bpo", "outsourc", "upwork", "fiverr", "freelanc",
    "virtual assistant", "agency", "subcontract", "white label", "white-label",
)
OPERATOR_CONTEXT = (
    "client", "clients", "customer", "customers", "proposal", "delivery",
    "contractor", "subcontractor", "margin", "profit", "pricing", "scale",
    "scaling", "manage", "management", "workflow", "spreadsheet", "team",
)
HIGH_INTENT = (
    "how do i", "how do you", "how to", "need help", "any advice",
    "recommend", "what software", "what tool", "struggling", "problem",
    "issue", "manage", "track", "margin", "profit", "outsource",
    "outsourcing", "subcontract", "scale",
)
NEGATIVE = (
    "looking for a job", "need a job", "job seeker", "unemployed",
    "visa", "tourism", "holiday", "invest in south africa", "moving to south africa",
)
SECTOR_EXCLUSIONS = (
    "construction", "engineering", "building contractor",
    "quantity surveyor", "safety compliance", "mining operation",
)

@dataclass
class RedditCandidate:
    id: str
    fullname: str
    reddit_id: str
    subreddit: str
    author: str
    title: str
    body: str
    permalink: str
    created_utc: float
    score: int
    relevance_score: int
    matches: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

def _matches(text: str, terms) -> list[str]:
    return [term for term in terms if term in text]

def score_relevance(title: str, body: str) -> tuple[int, list[str]]:
    text = normalize_space(f"{title} {body}").lower()
    if any(x in text for x in NEGATIVE):
        return 0, []
    if any(x in text for x in SECTOR_EXCLUSIONS):
        return 0, []
    za = _matches(text, ZA_CONTEXT)
    bpo = _matches(text, BPO_CONTEXT)
    operator = _matches(text, OPERATOR_CONTEXT)
    if not bpo:
        return 0, []
    score = min(len(za), 2) * 3 + min(len(bpo), 3) * 5 + min(len(operator), 4) * 2
    return score, sorted(set(za + bpo + operator))

def score_intent(title: str, body: str) -> tuple[int, list[str]]:
    text = normalize_space(f"{title} {body}").lower()
    relevance, matches = score_relevance(title, body)
    if relevance <= 0:
        return 0, []
    operator = _matches(text, OPERATOR_CONTEXT)
    intent = _matches(text, HIGH_INTENT)
    if not operator or not intent:
        return 0, []
    score = relevance + min(len(intent), 4) * 3
    if "?" in text:
        score += 3
    padded = f" {text} "
    if any(x in padded for x in (" i ", " i'm ", " i've ", " my ", " we ", " we're ", " our ")):
        score += 2
    return score, sorted(set(matches + operator + intent))

def _recent(created_utc: float, days: int = 7) -> bool:
    try:
        dt = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(days=days)
    except Exception:
        return False

def discover(client: RedditClient, per_query: int = 25):
    seen = set()
    out = []
    stats = {
        "subreddits": len(SUBREDDITS),
        "queries_per_subreddit": len(QUERIES),
        "requests": 0,
        "raw_results": 0,
        "unique_results": 0,
        "recent_results": 0,
        "relevant_candidates": 0,
        "high_intent_candidates": 0,
        "errors": 0,
    }

    for subreddit in SUBREDDITS:
        for query in QUERIES:
            try:
                payload = client.get_json(
                    f"/r/{subreddit}/search",
                    params={
                        "q": query,
                        "restrict_sr": "on",
                        "sort": "new",
                        "t": "week",
                        "limit": per_query,
                        "raw_json": 1,
                    },
                )
                stats["requests"] += 1
            except Exception as exc:
                stats["errors"] += 1
                print(f"[warn] Reddit search failed r/{subreddit} q={query!r}: {exc}")
                continue

            children = ((payload.get("data") or {}).get("children") or [])
            stats["raw_results"] += len(children)

            for child in children:
                data = child.get("data") or {}
                reddit_id = data.get("id", "")
                fullname = data.get("name", "")
                if not reddit_id or not fullname or fullname in seen:
                    continue
                seen.add(fullname)
                stats["unique_results"] += 1

                created = float(data.get("created_utc", 0) or 0)
                if not _recent(created):
                    continue
                stats["recent_results"] += 1

                title = normalize_space(data.get("title", ""))
                body = normalize_space(data.get("selftext", ""))
                relevance_score, relevance_matches = score_relevance(title, body)
                if relevance_score <= 0:
                    continue
                intent_score, intent_matches = score_intent(title, body)

                out.append(RedditCandidate(
                    id=fingerprint(fullname, reddit_id),
                    fullname=fullname,
                    reddit_id=reddit_id,
                    subreddit=data.get("subreddit", subreddit),
                    author=data.get("author", ""),
                    title=title,
                    body=body,
                    permalink=f"https://www.reddit.com{data.get('permalink', '')}",
                    created_utc=created,
                    score=intent_score,
                    relevance_score=relevance_score,
                    matches=sorted(set(relevance_matches + intent_matches)),
                ))

    out.sort(key=lambda x: (x.score, x.relevance_score), reverse=True)
    stats["relevant_candidates"] = len(out)
    stats["high_intent_candidates"] = sum(1 for c in out if c.score > 0)
    return out, stats
