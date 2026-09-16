from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .content import build_post
from .discovery import discover, load_sources
from .scoring import score_item
from .bluesky_discovery import search_candidates
from .engagement import build_reply
from .state import (
    load_state,
    save_state,
    prune_state,
    published_today,
    engaged_today,
    already_engaged,
    author_engaged_recently,
)
from .publishers import bluesky, mastodon


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_recent(published: str | None, days: int = 30) -> bool:
    if not published:
        return True
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(days=days)
    except Exception:
        return True


def publish_to_configured(post: str) -> list[dict]:
    results = []

    if bluesky.configured():
        try:
            result = bluesky.publish(post)
            results.append({"publisher": "bluesky", "ok": True, "result": result})
        except Exception as exc:
            results.append({"publisher": "bluesky", "ok": False, "error": str(exc)})

    if mastodon.configured():
        try:
            result = mastodon.publish(post)
            results.append({"publisher": "mastodon", "ok": True, "result": result})
        except Exception as exc:
            results.append({"publisher": "mastodon", "ok": False, "error": str(exc)})

    return results


def run_bluesky_engagement(state: dict, marginboost_url: str) -> dict:
    enabled = env_bool("ENABLE_PUBLIC_REPLIES", True)
    max_per_run = max(0, int(os.getenv("MAX_REPLIES_PER_RUN", "1")))
    max_per_day = max(0, int(os.getenv("MAX_REPLIES_PER_DAY", "2")))
    min_score = max(1, int(os.getenv("MIN_REPLY_SCORE", "20")))
    own_handle = os.getenv("BLUESKY_HANDLE", "")

    report = {
        "enabled": enabled,
        "candidates": 0,
        "qualified": 0,
        "replied": 0,
        "records": [],
    }

    if not enabled or not bluesky.configured():
        return report

    candidates, search_stats = search_candidates(own_handle=own_handle)
    report["candidates"] = len(candidates)
    report["search_stats"] = search_stats

    qualified = [
        c for c in candidates
        if c.score >= min_score
        and not already_engaged(state, c.id)
        and not author_engaged_recently(state, c.author_did, days=14)
    ]
    report["qualified"] = len(qualified)

    remaining_today = max(0, max_per_day - engaged_today(state))
    run_limit = min(max_per_run, remaining_today)

    for candidate in qualified[:run_limit]:
        reply_text = build_reply(candidate.to_dict(), marginboost_url)
        record = {
            "candidate_id": candidate.id,
            "author": candidate.author_handle,
            "author_did": candidate.author_did,
            "source_uri": candidate.uri,
            "score": candidate.score,
            "matches": candidate.matches,
            "source_text": candidate.text[:500],
            "reply_text": reply_text,
            "ok": False,
        }

        try:
            result = bluesky.publish_reply(
                reply_text,
                parent_uri=candidate.uri,
                parent_cid=candidate.cid,
                root_uri=candidate.root_uri,
                root_cid=candidate.root_cid,
            )
            record["ok"] = True
            record["result"] = result
            report["replied"] += 1
            state["engaged"].append({
                "candidate_id": candidate.id,
                "author_did": candidate.author_did,
                "author_handle": candidate.author_handle,
                "source_uri": candidate.uri,
                "reply_uri": result.get("uri"),
                "at": utc_now(),
                "score": candidate.score,
            })
        except Exception as exc:
            record["error"] = str(exc)

        report["records"].append(record)

    return report


def main():
    min_score = int(os.getenv("MIN_SCORE", "8"))
    max_per_run = max(0, int(os.getenv("MAX_POSTS_PER_RUN", "0")))
    max_per_day = max(0, int(os.getenv("MAX_POSTS_PER_DAY", "1")))
    auto_publish = env_bool("AUTO_PUBLISH", True)
    marginboost_url = os.getenv("MARGINBOOST_URL", "https://marginboost.co.za").strip()

    state = load_state()
    prune_state(state)

    # Primary acquisition layer: find live high-intent Bluesky conversations
    # and reply publicly where MarginBoost is actually relevant.
    engagement = run_bluesky_engagement(state, marginboost_url)

    # Secondary research layer: RSS/news/Reddit feeds still discover market
    # language and topics. Standalone posting is disabled by default in V3.
    feeds = load_sources()
    discovered = discover(feeds)

    now = utc_now()
    fresh = []
    skipped_old = 0

    for item in discovered:
        if item.id in state["seen"]:
            continue
        state["seen"][item.id] = now

        if not is_recent(item.published, days=30):
            skipped_old += 1
            continue

        scored = score_item(item.to_dict()).to_dict()
        if scored["score"] >= min_score:
            fresh.append(scored)

    fresh.sort(key=lambda x: x["score"], reverse=True)

    remaining_today = max(0, max_per_day - published_today(state))
    run_limit = min(max_per_run, remaining_today)

    queue = []
    successful_posts = 0

    for index, item in enumerate(fresh[: max(run_limit, 10)]):
        post = build_post(item, index, marginboost_url)
        record = {
            "id": item["id"],
            "source": item["source"],
            "source_url": item["url"],
            "score": item["score"],
            "matches": item["matches"],
            "post": post,
            "publishing": [],
        }

        if auto_publish and successful_posts < run_limit:
            pub = publish_to_configured(post)
            record["publishing"] = pub
            if any(x.get("ok") for x in pub):
                successful_posts += 1
                state["published"].append({
                    "id": item["id"],
                    "at": utc_now(),
                    "source": item["source"],
                    "score": item["score"],
                    "publishers": [x["publisher"] for x in pub if x.get("ok")],
                })

        queue.append(record)

    state["last_run"] = now
    save_state(state)

    Path("data/latest.json").write_text(
        json.dumps(queue[:25], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path("data/latest_engagement.json").write_text(
        json.dumps(engagement, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "rss_discovered": len(discovered),
        "rss_skipped_old": skipped_old,
        "rss_qualified_new": len(fresh),
        "standalone_published": successful_posts,
        "bluesky_search_candidates": engagement["candidates"],
        "bluesky_search_stats": engagement.get("search_stats", {}),
        "bluesky_high_intent_qualified": engagement["qualified"],
        "bluesky_public_replies": engagement["replied"],
        "auto_publish": auto_publish,
        "public_replies_enabled": engagement["enabled"],
        "bluesky_configured": bluesky.configured(),
    }, indent=2))


if __name__ == "__main__":
    main()