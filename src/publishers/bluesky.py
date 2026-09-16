from __future__ import annotations

import os
from datetime import datetime, timezone

import requests


BASE = "https://bsky.social/xrpc"


def configured() -> bool:
    return bool(os.getenv("BLUESKY_HANDLE") and os.getenv("BLUESKY_APP_PASSWORD"))


def publish(text: str) -> dict:
    handle = os.environ["BLUESKY_HANDLE"]
    password = os.environ["BLUESKY_APP_PASSWORD"]

    session = requests.post(
        f"{BASE}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    session.raise_for_status()
    sess = session.json()

    token = sess["accessJwt"]
    did = sess["did"]

    payload = {
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }

    response = requests.post(
        f"{BASE}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
