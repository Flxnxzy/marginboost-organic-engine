from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def load_state(path: str = "data/state.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {"seen": {}, "published": [], "last_run": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data.setdefault("seen", {})
    data.setdefault("published", [])
    data.setdefault("last_run", None)
    return data


def save_state(state: dict, path: str = "data/state.json"):
    Path(path).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prune_state(state: dict, seen_days: int = 45, published_days: int = 90):
    now = datetime.now(timezone.utc)
    seen_cutoff = now - timedelta(days=seen_days)
    pub_cutoff = now - timedelta(days=published_days)

    fresh_seen = {}
    for key, value in state.get("seen", {}).items():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt >= seen_cutoff:
                fresh_seen[key] = value
        except Exception:
            pass
    state["seen"] = fresh_seen

    fresh_pub = []
    for row in state.get("published", []):
        try:
            dt = datetime.fromisoformat(row["at"].replace("Z", "+00:00"))
            if dt >= pub_cutoff:
                fresh_pub.append(row)
        except Exception:
            pass
    state["published"] = fresh_pub


def published_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in state.get("published", []):
        try:
            if datetime.fromisoformat(row["at"].replace("Z", "+00:00")).date() == today:
                count += 1
        except Exception:
            pass
    return count
