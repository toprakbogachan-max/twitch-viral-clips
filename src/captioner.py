from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel

_model_cache: dict[str, WhisperModel] = {}


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str


def _get_model(model_size: str) -> WhisperModel:
    if model_size not in _model_cache:
        _model_cache[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model_cache[model_size]


def transcribe(
    video_path: Path, language: str | None = None, model_size: str = "small"
) -> list[CaptionSegment]:
    model = _get_model(model_size)
    lang = language.lower() if language else None
    segments, _info = model.transcribe(str(video_path), language=lang, vad_filter=True)
    return [
        CaptionSegment(start=s.start, end=s.end, text=s.text.strip())
        for s in segments
        if s.text.strip()
    ]
