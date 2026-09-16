from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def load_state(path: str = "data/state.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {"seen": {}, "published": [], "engaged": [], "liked": [], "followed": [], "deleted_replies": [], "last_run": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data.setdefault("seen", {})
    data.setdefault("published", [])
    data.setdefault("engaged", [])
    data.setdefault("liked", [])
    data.setdefault("followed", [])
    data.setdefault("reddit_engaged", [])
    data.setdefault("deleted_replies", [])
    data.setdefault("last_run", None)
    return data


def save_state(state: dict, path: str = "data/state.json"):
    Path(path).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def prune_state(state: dict, seen_days: int = 45, published_days: int = 90, engaged_days: int = 90):
    now = datetime.now(timezone.utc)
    seen_cutoff = now - timedelta(days=seen_days)
    pub_cutoff = now - timedelta(days=published_days)
    engaged_cutoff = now - timedelta(days=engaged_days)

    fresh_seen = {}
    for key, value in state.get("seen", {}).items():
        try:
            if _parse(value) >= seen_cutoff:
                fresh_seen[key] = value
        except Exception:
            pass
    state["seen"] = fresh_seen

    state["published"] = [
        row for row in state.get("published", [])
        if _row_after(row, pub_cutoff)
    ]
    for key in ("engaged", "liked", "followed", "reddit_engaged"):
        state[key] = [
            row for row in state.get(key, [])
            if _row_after(row, engaged_cutoff)
        ]


def _row_after(row: dict, cutoff: datetime) -> bool:
    try:
        return _parse(row["at"]) >= cutoff
    except Exception:
        return False


def published_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in state.get("published", []):
        try:
            if _parse(row["at"]).date() == today:
                count += 1
        except Exception:
            pass
    return count


def engaged_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in state.get("engaged", []):
        try:
            if _parse(row["at"]).date() == today:
                count += 1
        except Exception:
            pass
    return count


def likes_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in state.get("liked", []):
        try:
            if _parse(row["at"]).date() == today:
                count += 1
        except Exception:
            pass
    return count


def follows_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in state.get("followed", []):
        try:
            if _parse(row["at"]).date() == today:
                count += 1
        except Exception:
            pass
    return count


def already_liked(state: dict, candidate_id: str) -> bool:
    return any(row.get("candidate_id") == candidate_id for row in state.get("liked", []))


def already_followed_author(state: dict, author_did: str) -> bool:
    return any(row.get("author_did") == author_did for row in state.get("followed", []))


def author_touched_recently(state: dict, author_did: str, days: int = 7) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for key in ("engaged", "liked", "followed", "reddit_engaged"):
        for row in state.get(key, []):
            if row.get("author_did") != author_did:
                continue
            try:
                if _parse(row["at"]) >= cutoff:
                    return True
            except Exception:
                pass
    return False


def already_engaged(state: dict, candidate_id: str) -> bool:
    return any(row.get("candidate_id") == candidate_id for row in state.get("engaged", []))


def author_engaged_recently(state: dict, author_did: str, days: int = 14) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for row in state.get("engaged", []):
        if row.get("author_did") != author_did:
            continue
        try:
            if _parse(row["at"]) >= cutoff:
                return True
        except Exception:
            pass
    return False