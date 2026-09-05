from __future__ import annotations

import subprocess
from pathlib import Path


def download_podcast(url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "yt-dlp",
            "-f",
            "bv*[ext=mp4]+ba[ext=m4a]/mp4/best",
            "--no-playlist",
            "--print",
            "after_move:filepath",
            "-o",
            str(output_dir / "%(title).100B [%(id)s].%(ext)s"),
            url,
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp indirme hatası: {result.stderr[-2000:]}")

    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("yt-dlp dosya yolu döndürmedi.")

    path = Path(lines[-1])
    if not path.exists():
        raise RuntimeError(f"İndirilen dosya bulunamadı: {path}")

    return path
