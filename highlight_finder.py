from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from .captioner import CaptionSegment

MODEL = "claude-sonnet-5"


@dataclass
class Highlight:
    start: float
    end: float
    title: str


def slice_segments(
    segments: list[CaptionSegment], start: float, end: float
) -> list[CaptionSegment]:
    """Belirtilen [start, end] aralığına düşen segmentleri, klibin kendi
    0 noktasına göre zamanları kaydırılmış olarak döndürür."""
    sliced = []
    for seg in segments:
        if seg.end <= start or seg.start >= end:
            continue
        sliced.append(
            CaptionSegment(
                start=max(seg.start, start) - start,
                end=min(seg.end, end) - start,
                text=seg.text,
            )
        )
    return sliced


def _build_transcript(segments: list[CaptionSegment]) -> str:
    return "\n".join(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}" for seg in segments)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def find_highlights(
    segments: list[CaptionSegment],
    api_key: str,
    max_clips: int = 8,
    min_duration: float = 15.0,
    max_duration: float = 60.0,
) -> list[Highlight]:
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY bulunamadı. .env dosyasına ANTHROPIC_API_KEY ekleyin."
        )

    transcript = _build_transcript(segments)

    prompt = f"""Aşağıda bir podcast'in zaman damgalı (saniye cinsinden) transkripti var.

Bu podcast'ten YouTube Shorts / TikTok için en ilgi çekici, çarpıcı, tek başına
anlam ifade eden (bağlamsız izlenebilir) en fazla {max_clips} kesiti seç.

Kurallar:
- Her kesit {min_duration:.0f}-{max_duration:.0f} saniye arasında olsun.
- Başlangıç ve bitiş bir cümlenin/düşüncenin doğal sınırında olsun, cümle
  ortasında başlamasın veya bitmesin.
- Kesitler birbiriyle çakışmasın.
- Her kesit için kısa, çarpıcı, merak uyandıran bir başlık öner (Türkçe ya da
  transkriptin dilinde, hangisi daha doğal geliyorsa).

Sadece şu JSON formatında cevap ver, başka hiçbir açıklama/metin ekleme:
[{{"start": <saniye, sayı>, "end": <saniye, sayı>, "title": "<başlık>"}}, ...]

Transkript:
{transcript}
"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    data = json.loads(_extract_json(raw_text))

    highlights = [
        Highlight(start=float(item["start"]), end=float(item["end"]), title=str(item["title"]))
        for item in data
    ]
    highlights.sort(key=lambda h: h.start)
    return highlights
