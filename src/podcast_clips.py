from __future__ import annotations

import argparse
import csv
import re

from . import config
from .captioner import transcribe
from .editor import (
    burn_captions_and_title,
    compute_video_bounds,
    wrap_title,
    write_ass,
)
from .highlight_finder import find_highlights, slice_segments
from .podcast_downloader import download_podcast

PODCAST_SRC_DIR = config.OUTPUT_DIR / "podcast_source"
READY_DIR = config.OUTPUT_DIR / "podcast_ready"
WORK_DIR = config.OUTPUT_DIR / "_podcast_work"
READY_CSV = config.OUTPUT_DIR / "podcast_ready.csv"


def _safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text) or "clip"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bir podcast linkinden en ilgi çekici kesitleri bulup 9:16 formatında işler."
    )
    parser.add_argument("url", help="Podcast video linki (YouTube vb.)")
    parser.add_argument("--max-clips", type=int, default=8)
    parser.add_argument("--min-duration", type=float, default=15.0)
    parser.add_argument("--max-duration", type=float, default=60.0)
    parser.add_argument("--model-size", default="small")
    args = parser.parse_args()

    PODCAST_SRC_DIR.mkdir(parents=True, exist_ok=True)
    READY_DIR.mkdir(parents=True, exist_ok=True)

    print("Podcast indiriliyor...")
    src = download_podcast(args.url, PODCAST_SRC_DIR)
    print(f"İndirildi: {src.name}")

    print("Podcast'in tamamı yazıya dökülüyor (uzun podcast'lerde bu adım epey sürebilir)...")
    segments = transcribe(src, model_size=args.model_size)
    print(f"{len(segments)} segment bulundu.")

    print("Claude ile en ilgi çekici kesitler bulunuyor...")
    highlights = find_highlights(
        segments,
        config.ANTHROPIC_API_KEY,
        max_clips=args.max_clips,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
    )
    print(f"{len(highlights)} kesit seçildi.")

    video_top, video_bottom = compute_video_bounds(src)

    rows = []
    for i, hl in enumerate(highlights, start=1):
        duration = hl.end - hl.start
        print(f"[{i}/{len(highlights)}] {hl.title} ({hl.start:.0f}s-{hl.end:.0f}s, {duration:.0f}sn)")

        work_dir = WORK_DIR / f"clip_{i:02d}_{_safe_id(hl.title)[:30]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        ass_path = work_dir / "captions.ass"
        title_path = work_dir / "title.txt"

        clip_segments = slice_segments(segments, hl.start, hl.end)
        write_ass(clip_segments, ass_path, video_bottom=video_bottom)
        title_path.write_text(wrap_title(hl.title), encoding="utf-8")

        dest = READY_DIR / f"podcast_clip_{i:02d}_{_safe_id(hl.title)[:40]}.mp4"
        try:
            burn_captions_and_title(
                src,
                ass_path,
                title_path,
                dest,
                video_top=video_top,
                clip_start=hl.start,
                clip_duration=duration,
            )
            ready_path = str(dest)
        except Exception as e:
            print(f"  [HATA] {e}")
            ready_path = ""

        rows.append(
            {
                "yayinci": src.stem,
                "baslik": hl.title,
                "dil": "",
                "kategori": "Podcast",
                "sure_sn": round(duration, 1),
                "view": "",
                "skor": "",
                "link": args.url,
                "yerel_dosya": ready_path,
                "hazir_dosya": ready_path,
            }
        )

    if rows:
        with open(READY_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print(f"Bitti. Klipler: {READY_DIR}")
    print(f"CSV: {READY_CSV}")
    print(f"YouTube'a yüklemek için: python -m src.youtube_upload --csv {READY_CSV}")


if __name__ == "__main__":
    main()
