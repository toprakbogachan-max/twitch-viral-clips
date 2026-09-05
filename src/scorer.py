from __future__ import annotations

from datetime import datetime, timezone


def _parse_twitch_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def score_clip(
    clip: dict,
    now: datetime,
    min_duration: float,
    max_duration: float,
    ideal_min: float,
    ideal_max: float,
) -> float | None:
    """view/saat (tazelik-normalize) skoru döner; süre aralığı dışındaysa None."""
    duration = clip.get("duration", 0.0)
    if duration < min_duration or duration > max_duration:
        return None

    created_at = _parse_twitch_time(clip["created_at"])
    hours_since_created = max((now - created_at).total_seconds() / 3600.0, 0.5)
    view_rate = clip.get("view_count", 0) / hours_since_created

    if ideal_min <= duration <= ideal_max:
        view_rate *= 1.2

    return view_rate


def rank_and_select(
    clips: list[dict],
    top_n: int = 15,
    per_streamer_cap: int = 2,
    min_duration: float = 5.0,
    max_duration: float = 90.0,
    ideal_min: float = 15.0,
    ideal_max: float = 60.0,
) -> list[dict]:
    now = datetime.now(timezone.utc)

    scored = []
    for clip in clips:
        score = score_clip(clip, now, min_duration, max_duration, ideal_min, ideal_max)
        if score is None:
            continue
        enriched = dict(clip)
        enriched["score"] = round(score, 2)
        scored.append(enriched)

    scored.sort(key=lambda c: c["score"], reverse=True)

    selected = []
    per_streamer_count: dict[str, int] = {}
    for clip in scored:
        broadcaster_id = clip["broadcaster_id"]
        if per_streamer_count.get(broadcaster_id, 0) >= per_streamer_cap:
            continue
        selected.append(clip)
        per_streamer_count[broadcaster_id] = per_streamer_count.get(broadcaster_id, 0) + 1
        if len(selected) >= top_n:
            break

    return selected
