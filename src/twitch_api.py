from __future__ import annotations

import time

import requests

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_BASE = "https://api.twitch.tv/helix"


def get_app_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = requests.Session()
        self._authenticate()

    def _authenticate(self):
        token = get_app_token(self.client_id, self.client_secret)
        self.session.headers.update(
            {"Client-Id": self.client_id, "Authorization": f"Bearer {token}"}
        )

    def _get(self, path: str, params: dict) -> dict:
        url = f"{API_BASE}/{path}"
        for attempt in range(5):
            resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code == 401:
                self._authenticate()
                continue

            if resp.status_code == 429:
                reset = resp.headers.get("Ratelimit-Reset")
                wait = max(float(reset) - time.time(), 1.0) if reset else 2.0 * (attempt + 1)
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                time.sleep(2.0 * (attempt + 1))
                continue

            resp.raise_for_status()

            remaining = resp.headers.get("Ratelimit-Remaining")
            reset = resp.headers.get("Ratelimit-Reset")
            if remaining is not None and int(remaining) <= 1 and reset:
                time.sleep(max(float(reset) - time.time(), 0.0))

            return resp.json()

        raise RuntimeError(f"Twitch API isteği tekrar denemelerine rağmen başarısız: {path}")

    def get_top_streams(self, language: str, limit: int = 50) -> list[dict]:
        streams: list[dict] = []
        cursor = None
        while len(streams) < limit:
            params = {"language": language, "first": min(100, limit - len(streams))}
            if cursor:
                params["after"] = cursor
            data = self._get("streams", params)
            batch = data.get("data", [])
            if not batch:
                break
            streams.extend(batch)
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return streams[:limit]

    def get_clips(
        self, broadcaster_id: str, started_at: str, ended_at: str, limit: int = 20
    ) -> list[dict]:
        clips: list[dict] = []
        cursor = None
        while len(clips) < limit:
            params = {
                "broadcaster_id": broadcaster_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "first": min(100, limit - len(clips)),
            }
            if cursor:
                params["after"] = cursor
            data = self._get("clips", params)
            batch = data.get("data", [])
            if not batch:
                break
            clips.extend(batch)
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return clips[:limit]

    def get_users_by_login(self, logins: list[str]) -> list[dict]:
        users: list[dict] = []
        unique_logins = [login for login in dict.fromkeys(logins) if login]
        for i in range(0, len(unique_logins), 100):
            batch = unique_logins[i : i + 100]
            data = self._get("users", {"login": batch})
            users.extend(data.get("data", []))
        return users

    def get_games(self, game_ids: list[str]) -> dict[str, str]:
        names: dict[str, str] = {}
        unique_ids = [gid for gid in dict.fromkeys(game_ids) if gid]
        for i in range(0, len(unique_ids), 100):
            batch = unique_ids[i : i + 100]
            data = self._get("games", {"id": batch})
            for game in data.get("data", []):
                names[game["id"]] = game["name"]
        return names
