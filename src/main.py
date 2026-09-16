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
    likes_today,
    follows_today,
    already_engaged,
    already_liked,
    already_followed_author,
    author_touched_recently,
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


def cleanup_revoked_replies(state: dict) -> dict:
    uris = [
        x.strip()
        for x in os.getenv("DELETE_REPLY_URIS", "").split(",")
        if x.strip()
    ]
    state.setdefault("deleted_replies", [])
    done = set(state["deleted_replies"])

    report = {"requested": len(uris), "deleted": 0, "errors": []}

    for uri in uris:
        if uri in done:
            continue
        try:
            bluesky.delete_post(uri)
            state["deleted_replies"].append(uri)
            report["deleted"] += 1
        except Exception as exc:
            report["errors"].append({"uri": uri, "error": str(exc)})

    return report

def run_bluesky_engagement(state: dict, marginboost_url: str) -> dict:
    replies_enabled = env_bool("ENABLE_PUBLIC_REPLIES", True)
    likes_enabled = env_bool("ENABLE_LIKES", True)
    follows_enabled = env_bool("ENABLE_FOLLOWS", True)

    max_replies_run = max(0, int(os.getenv("MAX_REPLIES_PER_RUN", "1")))
    max_replies_day = max(0, int(os.getenv("MAX_REPLIES_PER_DAY", "5")))
    min_reply_score = max(1, int(os.getenv("MIN_REPLY_SCORE", "18")))

    max_likes_run = max(0, int(os.getenv("MAX_LIKES_PER_RUN", "5")))
    max_likes_day = max(0, int(os.getenv("MAX_LIKES_PER_DAY", "25")))
    min_like_score = max(1, int(os.getenv("MIN_LIKE_SCORE", "12")))

    max_follows_run = max(0, int(os.getenv("MAX_FOLLOWS_PER_RUN", "1")))
    max_follows_day = max(0, int(os.getenv("MAX_FOLLOWS_PER_DAY", "3")))
    min_follow_score = max(1, int(os.getenv("MIN_FOLLOW_SCORE", "14")))

    cooldown_days = max(1, int(os.getenv("AUTHOR_COOLDOWN_DAYS", "7")))
    own_handle = os.getenv("BLUESKY_HANDLE", "")

    report = {
        "enabled": {"replies": replies_enabled, "likes": likes_enabled, "follows": follows_enabled},
        "candidates": 0,
        "reply_qualified": 0,
        "like_qualified": 0,
        "follow_qualified": 0,
        "replied": 0,
        "liked": 0,
        "followed": 0,
        "reply_records": [],
        "like_records": [],
        "follow_records": [],
    }

    if not bluesky.configured() or not (replies_enabled or likes_enabled or follows_enabled):
        return report

    candidates, search_stats = search_candidates(own_handle=own_handle)
    report["candidates"] = len(candidates)
    report["search_stats"] = search_stats
    touched_this_run = set()

    reply_qualified = [
        c for c in candidates
        if c.score >= min_reply_score
        and not already_engaged(state, c.id)
        and not author_touched_recently(state, c.author_did, days=cooldown_days)
    ]
    report["reply_qualified"] = len(reply_qualified)
    reply_limit = min(
        max_replies_run,
        max(0, max_replies_day - engaged_today(state)),
    ) if replies_enabled else 0

    for candidate in reply_qualified[:reply_limit]:
        reply_text = build_reply(candidate.to_dict(), marginboost_url)
        rec = {
            "candidate_id": candidate.id,
            "author": candidate.author_handle,
            "author_did": candidate.author_did,
            "source_uri": candidate.uri,
            "score": candidate.score,
            "relevance_score": candidate.relevance_score,
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
            rec["ok"] = True
            rec["result"] = result
            report["replied"] += 1
            touched_this_run.add(candidate.author_did)
            state["engaged"].append({
                "candidate_id": candidate.id,
                "author_did": candidate.author_did,
                "author_handle": candidate.author_handle,
                "source_uri": candidate.uri,
                "reply_uri": result.get("uri"),
                "at": utc_now(),
                "score": candidate.score,
                "relevance_score": candidate.relevance_score,
            })
        except Exception as exc:
            rec["error"] = str(exc)
        report["reply_records"].append(rec)

    follow_candidates = [
        c for c in candidates
        if c.relevance_score >= min_follow_score
        and c.author_did
        and c.author_did not in touched_this_run
        and not already_followed_author(state, c.author_did)
        and not author_touched_recently(state, c.author_did, days=cooldown_days)
    ]
    unique_follows = []
    seen_authors = set()
    for c in follow_candidates:
        if c.author_did in seen_authors:
            continue
        seen_authors.add(c.author_did)
        unique_follows.append(c)

    report["follow_qualified"] = len(unique_follows)
    follow_limit = min(
        max_follows_run,
        max(0, max_follows_day - follows_today(state)),
    ) if follows_enabled else 0

    for candidate in unique_follows[:follow_limit]:
        rec = {
            "candidate_id": candidate.id,
            "author": candidate.author_handle,
            "author_did": candidate.author_did,
            "source_uri": candidate.uri,
            "relevance_score": candidate.relevance_score,
            "matches": candidate.matches,
            "ok": False,
        }
        try:
            result = bluesky.follow_author(candidate.author_did)
            rec["ok"] = True
            rec["result"] = result
            report["followed"] += 1
            touched_this_run.add(candidate.author_did)
            state["followed"].append({
                "candidate_id": candidate.id,
                "author_did": candidate.author_did,
                "author_handle": candidate.author_handle,
                "source_uri": candidate.uri,
                "follow_uri": result.get("uri"),
                "at": utc_now(),
                "relevance_score": candidate.relevance_score,
            })
        except Exception as exc:
            rec["error"] = str(exc)
        report["follow_records"].append(rec)

    like_candidates = [
        c for c in candidates
        if c.relevance_score >= min_like_score
        and c.author_did
        and c.author_did not in touched_this_run
        and not already_liked(state, c.id)
        and not author_touched_recently(state, c.author_did, days=cooldown_days)
    ]
    report["like_qualified"] = len(like_candidates)
    like_limit = min(
        max_likes_run,
        max(0, max_likes_day - likes_today(state)),
    ) if likes_enabled else 0

    for candidate in like_candidates[:like_limit]:
        rec = {
            "candidate_id": candidate.id,
            "author": candidate.author_handle,
            "author_did": candidate.author_did,
            "source_uri": candidate.uri,
            "relevance_score": candidate.relevance_score,
            "matches": candidate.matches,
            "ok": False,
        }
        try:
            result = bluesky.like_post(candidate.uri, candidate.cid)
            rec["ok"] = True
            rec["result"] = result
            report["liked"] += 1
            touched_this_run.add(candidate.author_did)
            state["liked"].append({
                "candidate_id": candidate.id,
                "author_did": candidate.author_did,
                "author_handle": candidate.author_handle,
                "source_uri": candidate.uri,
                "like_uri": result.get("uri"),
                "at": utc_now(),
                "relevance_score": candidate.relevance_score,
            })
        except Exception as exc:
            rec["error"] = str(exc)
        report["like_records"].append(rec)

    return report


def main():
    min_score = int(os.getenv("MIN_SCORE", "8"))
    max_per_run = max(0, int(os.getenv("MAX_POSTS_PER_RUN", "1")))
    max_per_day = max(0, int(os.getenv("MAX_POSTS_PER_DAY", "1")))
    auto_publish = env_bool("AUTO_PUBLISH", True)
    marginboost_url = os.getenv("MARGINBOOST_URL", "https://marginboost.co.za").strip()

    state = load_state()
    prune_state(state)

    # Remove any explicitly revoked/false-positive replies first.
    cleanup = cleanup_revoked_replies(state)

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
        "cleanup": cleanup,
        "rss_discovered": len(discovered),
        "rss_skipped_old": skipped_old,
        "rss_qualified_new": len(fresh),
        "standalone_published": successful_posts,
        "bluesky_search_candidates": engagement["candidates"],
        "bluesky_search_stats": engagement.get("search_stats", {}),
        "bluesky_reply_qualified": engagement["reply_qualified"],
        "bluesky_public_replies": engagement["replied"],
        "bluesky_like_qualified": engagement["like_qualified"],
        "bluesky_likes": engagement["liked"],
        "bluesky_follow_qualified": engagement["follow_qualified"],
        "bluesky_follows": engagement["followed"],
        "auto_publish": auto_publish,
        "bluesky_configured": bluesky.configured(),
    }, indent=2))


if __name__ == "__main__":
    main()