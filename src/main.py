from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .content import build_post
from .discovery import discover, load_sources
from .scoring import score_item
from .state import load_state, save_state, prune_state, published_today
from .publishers import bluesky, mastodon


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def main():
    min_score = int(os.getenv("MIN_SCORE", "8"))
    max_per_run = max(0, int(os.getenv("MAX_POSTS_PER_RUN", "1")))
    max_per_day = max(0, int(os.getenv("MAX_POSTS_PER_DAY", "3")))
    auto_publish = env_bool("AUTO_PUBLISH", True)
    marginboost_url = os.getenv("MARGINBOOST_URL", "https://marginboost.co.za").strip()

    state = load_state()
    prune_state(state)

    feeds = load_sources()
    discovered = discover(feeds)

    now = utc_now()
    fresh = []
    for item in discovered:
        if item.id in state["seen"]:
            continue
        state["seen"][item.id] = now
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

            # A post counts only if at least one configured publisher succeeded.
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

    print(json.dumps({
        "discovered": len(discovered),
        "qualified_new": len(fresh),
        "queued": len(queue[:25]),
        "published": successful_posts,
        "auto_publish": auto_publish,
        "bluesky_configured": bluesky.configured(),
        "mastodon_configured": mastodon.configured(),
    }, indent=2))


if __name__ == "__main__":
    main()
