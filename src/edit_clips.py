from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from . import config
from .captioner import transcribe
from .editor import (
    burn_captions_and_title,
    compute_video_bounds,
    wrap_title,
    write_ass,
)

READY_DIR = config.OUTPUT_DIR / "ready"
WORK_DIR = config.OUTPUT_DIR / "_work"
READY_CSV = config.OUTPUT_DIR / "ready.csv"


def _safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text) or "clip"


def process_row(row: dict, model_size: str) -> str | None:
    src = Path(row["yerel_dosya"])
    if not src.exists():
        print(f"  [ATLA] dosya yok: {src}")
        return None

    clip_key = _safe_id(src.stem)
    work_dir = WORK_DIR / clip_key
    work_dir.mkdir(parents=True, exist_ok=True)

    ass_path = work_dir / "captions.ass"
    title_path = work_dir / "title.txt"

    video_top, video_bottom = compute_video_bounds(src)

    print(f"  Altyazı çıkarılıyor: {src.name}")
    segments = transcribe(src, language=row.get("dil") or None, model_size=model_size)
    write_ass(segments, ass_path, video_bottom=video_bottom)

    broadcaster = row.get("yayinci", "").strip()
    wrapped_title = wrap_title(row.get("baslik", "") or "")
    title_text = f"{broadcaster}\n{wrapped_title}" if broadcaster else wrapped_title
    title_path.write_text(title_text, encoding="utf-8")

    dest = READY_DIR / src.name
    print(f"  Video işleniyor: {src.name}")
    burn_captions_and_title(src, ass_path, title_path, dest, video_top=video_top)
    return str(dest)


def main() -> None:
    parser = argparse.ArgumentParser(description="İndirilen klipleri altyazı + başlıkla işler.")
    parser.add_argument("--csv", default=str(config.CSV_PATH))
    parser.add_argument("--model-size", default="small")
    args = parser.parse_args()

    READY_DIR.mkdir(parents=True, exist_ok=True)

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    output_rows = []
    for i, row in enumerate(rows, start=1):
        print(f"[{i}/{len(rows)}] {row.get('yayinci', '')} - {row.get('baslik', '')[:50]}")
        try:
            ready_path = process_row(row, args.model_size)
        except Exception as e:
            print(f"  [HATA] {e}")
            ready_path = None
        new_row = dict(row)
        new_row["hazir_dosya"] = ready_path or ""
        output_rows.append(new_row)

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with open(READY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Bitti. Gözden geçirmek için: {READY_DIR}")
    print(f"CSV: {READY_CSV}")


if __name__ == "__main__":
    main()
