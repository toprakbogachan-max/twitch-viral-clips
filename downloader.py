from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import requests

GQL_URL = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Twitch web'in genel (secret olmayan) anonim client id'si
SHARE_CLIP_HASH = "66038e29eb00d8fd115b0ce1a1382dd9d41168739b08bc87dc042af6a730541f"


def _clean_for_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", text)
    return text.strip()


def _safe_filename(clip: dict) -> str:
    broadcaster = _clean_for_filename(clip.get("broadcaster_name", "")) or "unknown"
    title = _clean_for_filename(clip.get("title", ""))
    clip_id = clip.get("id", "")

    name = f"{broadcaster} - {title}" if title else broadcaster
    name = name[:120]
    suffix = re.sub(r"[^A-Za-z0-9]", "", clip_id)[-8:]
    return f"{name} [{suffix}].mp4" if suffix else f"{name}.mp4"


def _resolve_source_url(slug: str) -> str | None:
    resp = requests.post(
        GQL_URL,
        headers={"Client-Id": GQL_CLIENT_ID, "Content-Type": "text/plain;charset=UTF-8"},
        json=[
            {
                "operationName": "ShareClipRenderStatus",
                "variables": {"slug": slug},
                "extensions": {"persistedQuery": {"version": 1, "sha256Hash": SHARE_CLIP_HASH}},
            }
        ],
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()[0]

    if "errors" in payload:
        raise RuntimeError(
            f"Twitch GQL hatası ({payload['errors']}). Twitch API'si değişmiş olabilir, "
            "SHARE_CLIP_HASH güncellenmesi gerekebilir."
        )

    clip_data = (payload.get("data") or {}).get("clip")
    if not clip_data or not clip_data.get("assets"):
        return None

    qualities = clip_data["assets"][0].get("videoQualities", [])
    if not qualities:
        return None

    avc_qualities = [q for q in qualities if q.get("videoCodec") == "AVC"]
    pool = avc_qualities or qualities
    best = max(pool, key=lambda q: int(q.get("quality", 0)))
    source_url = best.get("sourceURL")
    if not source_url:
        return None

    # nauth kaynak URL'leri playbackAccessToken ile imzalanmadan 401 döner.
    token = clip_data.get("playbackAccessToken") or {}
    signature = token.get("signature")
    value = token.get("value")
    if signature and value:
        source_url = f"{source_url}?sig={signature}&token={urllib.parse.quote(value)}"

    return source_url


def download_clip(clip: dict, output_dir: Path) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / _safe_filename(clip)

    try:
        source_url = _resolve_source_url(clip["id"])
    except Exception as e:
        print(f"  [HATA] klip çözümlenemedi: {clip.get('url')} -> {e}")
        return None

    if not source_url:
        print(f"  [HATA] indirme linki bulunamadı: {clip.get('url')}")
        return None

    try:
        with requests.get(source_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
    except Exception as e:
        print(f"  [HATA] indirilemedi: {clip.get('url')} -> {e}")
        if dest.exists():
            dest.unlink()
        return None

    return dest
