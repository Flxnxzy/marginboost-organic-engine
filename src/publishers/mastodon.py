from __future__ import annotations

import os

import requests


def configured() -> bool:
    return bool(os.getenv("MASTODON_BASE_URL") and os.getenv("MASTODON_ACCESS_TOKEN"))


def publish(text: str) -> dict:
    base = os.environ["MASTODON_BASE_URL"].rstrip("/")
    token = os.environ["MASTODON_ACCESS_TOKEN"]

    response = requests.post(
        f"{base}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        data={"status": text, "visibility": "public"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
