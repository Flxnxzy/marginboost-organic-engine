from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests


BASE = "https://bsky.social/xrpc"


def configured() -> bool:
    return bool(os.getenv("BLUESKY_HANDLE") and os.getenv("BLUESKY_APP_PASSWORD"))


def _session() -> tuple[str, str]:
    handle = os.environ["BLUESKY_HANDLE"]
    password = os.environ["BLUESKY_APP_PASSWORD"]

    response = requests.post(
        f"{BASE}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data["accessJwt"], data["did"]


def _link_facets(text: str) -> list[dict]:
    facets = []
    for match in re.finditer(r"https?://[^\s]+", text):
        start_chars = text[:match.start()]
        link_text = match.group(0)
        byte_start = len(start_chars.encode("utf-8"))
        byte_end = byte_start + len(link_text.encode("utf-8"))
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": link_text,
            }],
        })
    return facets


def _create_record(record: dict) -> dict:
    token, did = _session()
    response = requests.post(
        f"{BASE}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def publish(text: str) -> dict:
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["en"],
    }
    facets = _link_facets(text)
    if facets:
        record["facets"] = facets
    return _create_record(record)


def publish_reply(
    text: str,
    parent_uri: str,
    parent_cid: str,
    root_uri: str | None = None,
    root_cid: str | None = None,
) -> dict:
    root_uri = root_uri or parent_uri
    root_cid = root_cid or parent_cid

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["en"],
        "reply": {
            "root": {"uri": root_uri, "cid": root_cid},
            "parent": {"uri": parent_uri, "cid": parent_cid},
        },
    }

    facets = _link_facets(text)
    if facets:
        record["facets"] = facets

    return _create_record(record)

def delete_post(uri: str) -> dict:
    token, did = _session()
    prefix = f"at://{did}/app.bsky.feed.post/"
    if not uri.startswith(prefix):
        raise ValueError("Refusing to delete a post that does not belong to the authenticated account")

    rkey = uri[len(prefix):]
    response = requests.post(
        f"{BASE}/com.atproto.repo.deleteRecord",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "repo": did,
            "collection": "app.bsky.feed.post",
            "rkey": rkey,
        },
        timeout=20,
    )

    if response.ok:
        return {"deleted": True, "uri": uri}

    if response.status_code in (400, 404) and "RecordNotFound" in response.text:
        return {"deleted": False, "already_absent": True, "uri": uri}

    response.raise_for_status()
    return {"deleted": True, "uri": uri}