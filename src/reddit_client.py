from __future__ import annotations

import os
import time
import requests

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE = "https://oauth.reddit.com"

class RedditClient:
    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
        self.refresh_token = os.getenv("REDDIT_REFRESH_TOKEN", "").strip()
        self.user_agent = os.getenv(
            "REDDIT_USER_AGENT",
            "windows:marginboost-organic-engine:v1.0 (by /u/MarginBoost)",
        ).strip()
        self._access_token = ""
        self._expires_at = 0.0

    def configured(self) -> bool:
        return bool(self.client_id and self.refresh_token and self.user_agent)

    def _token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        if not self.configured():
            raise RuntimeError("Reddit OAuth is not configured")
        response = requests.post(
            TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "refresh_token", "refresh_token": self.refresh_token},
            headers={"User-Agent": self.user_agent},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Reddit token response did not contain access_token")
        self._access_token = token
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))
        return token

    def request(self, method: str, path: str, *, params=None, data=None):
        response = requests.request(
            method,
            f"{OAUTH_BASE}{path}",
            params=params,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "User-Agent": self.user_agent,
            },
            timeout=20,
        )
        if response.status_code == 429:
            reset = response.headers.get("x-ratelimit-reset", "unknown")
            raise RuntimeError(f"Reddit rate limited this client; reset={reset}s")
        response.raise_for_status()
        return response

    def get_json(self, path: str, params=None) -> dict:
        return self.request("GET", path, params=params).json()

    def subreddit_rules(self, subreddit: str) -> dict:
        return self.get_json(f"/r/{subreddit}/about/rules")

    def comment(self, thing_id: str, text: str) -> dict:
        payload = self.request(
            "POST",
            "/api/comment",
            data={"api_type": "json", "thing_id": thing_id, "text": text},
        ).json()
        errors = ((payload.get("json") or {}).get("errors") or [])
        if errors:
            raise RuntimeError(f"Reddit comment failed: {errors}")
        return payload
