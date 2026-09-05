from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import imageio_ffmpeg
from PIL import ImageFont

from .captioner import CaptionSegment

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TITLE_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
CAPTION_WRAP_CHARS = 24
CAPTION_GAP = 90  # videonun alt kenarı ile altyazı arasındaki minimum boşluk (px)
TITLE_GAP = 20  # videonun üst kenarı ile başlık arasındaki minimum boşluk (px)

TITLE_FONT_SIZE = 58
TITLE_MAX_WIDTH = TARGET_WIDTH - 120  # sağ/sol kenar boşluğu
_TITLE_FONT_OBJ = ImageFont.truetype(TITLE_FONT, TITLE_FONT_SIZE)

ASS_HEADER_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def probe_dimensions(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        [FFMPEG, "-i", str(path)], capture_output=True, text=True, timeout=15
    )
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", result.stderr)
    if not match:
        raise RuntimeError(f"Video çözünürlüğü tespit edilemedi: {path}")
    return int(match.group(1)), int(match.group(2))


def compute_video_bounds(src_path: Path) -> tuple[int, int]:
    """Klip 1080 genişliğe ölçeklenip dikey tuvale ortalanınca videonun
    gerçekte hangi Y aralığında (üst, alt) duracağını hesaplar."""
    src_w, src_h = probe_dimensions(src_path)
    scaled_h = round(src_h * TARGET_WIDTH / src_w)
    video_top = max((TARGET_HEIGHT - scaled_h) // 2, 0)
    video_bottom = min(video_top + scaled_h, TARGET_HEIGHT)
    return video_top, video_bottom


LINE_HEIGHT_PX = 90  # Fontsize=70 için yaklaşık satır yüksekliği (ASS satır aralığı dahil)


def compute_caption_margin(video_bottom: int, line_count: int = 1) -> int:
    # MarginV, bloğun ALT kenarının konumunu belirler; blok yukarı doğru
    # büyüdüğü için satır sayısı arttıkça payı da o kadar artırmamız gerekir,
    # yoksa üstteki satır(lar) videoya taşar.
    return max(TARGET_HEIGHT - video_bottom - CAPTION_GAP - line_count * LINE_HEIGHT_PX, 20)


def _format_ass_time(seconds: float) -> str:
    cs = int(round(max(seconds, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


MAX_CAPTION_LINES = 2


def _split_text_into_chunks(text: str, wrap_width: int, max_lines: int) -> list[str]:
    """Metni, sarıldığında en fazla max_lines satır tutacak parçalara böler.
    Karaktere değil gerçek sarma sonucuna bakar, bu yüzden kelime uzunluğu/
    satır sınırı tuhaflıklarında bile satır sayısını garanti eder."""
    words = text.split()
    if not words:
        return []

    chunks = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        line_count = textwrap.fill(candidate, width=wrap_width).count("\n") + 1
        if line_count <= max_lines:
            current = candidate
        else:
            chunks.append(current)
            current = word
    chunks.append(current)
    return chunks


def write_ass(segments: list[CaptionSegment], path: Path, video_bottom: int) -> None:
    header = ASS_HEADER_TEMPLATE.format(
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        margin_v=compute_caption_margin(video_bottom, line_count=1),
    )
    lines = [header]
    for seg in segments:
        # Çok uzun tek bir segment video üzerine taşabilecek kadar büyük bir
        # altyazı bloğu oluşturabiliyor; bunu süre içinde sıralı, en fazla
        # 2 satırlık parçalara bölüyoruz.
        chunks = _split_text_into_chunks(seg.text.strip(), CAPTION_WRAP_CHARS, MAX_CAPTION_LINES)
        if not chunks:
            continue

        duration = max(seg.end - seg.start, 0.01)
        total_chars = sum(len(c) for c in chunks) or 1
        cursor = seg.start
        for chunk in chunks:
            chunk_duration = duration * (len(chunk) / total_chars)
            chunk_end = cursor + chunk_duration
            wrapped_text = textwrap.fill(chunk, width=CAPTION_WRAP_CHARS)
            line_count = wrapped_text.count("\n") + 1
            # Blok yukarı doğru büyür; bu parçanın gerçek satır sayısına göre
            # kendi MarginV'ini yazıp stil varsayılanını geçersiz kılıyoruz.
            cue_margin = compute_caption_margin(video_bottom, line_count=line_count)
            wrapped = wrapped_text.replace("\n", "\\N")
            start = _format_ass_time(cursor)
            end = _format_ass_time(chunk_end)
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,{cue_margin},,{wrapped}")
            cursor = chunk_end
    path.write_text("\n".join(lines), encoding="utf-8")


def enhance_title(title: str) -> str:
    title = title.strip()
    if not title:
        return title
    if title[-1] not in "!?‼":
        title = f"{title} ‼"
    return title


def _wrap_by_pixel_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    words = text.split()
    if not words:
        return text

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.getlength(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def wrap_title(title: str) -> str:
    enhanced = enhance_title(title)
    if not enhanced:
        return enhanced
    # Tek satıra sığıyorsa satır kırma; sığmıyorsa sadece o zaman alt satıra geç.
    if _TITLE_FONT_OBJ.getlength(enhanced) <= TITLE_MAX_WIDTH:
        return enhanced
    return _wrap_by_pixel_width(enhanced, _TITLE_FONT_OBJ, TITLE_MAX_WIDTH)


def burn_captions_and_title(
    input_path: Path,
    ass_path: Path,
    title_path: Path,
    output_path: Path,
    video_top: int,
    clip_start: float | None = None,
    clip_duration: float | None = None,
) -> None:
    # Arka plan: aynı klibin bulanıklaştırılmış, tuvali tamamen kaplayan hali
    # (düz siyah bar yerine). Ön plan: klip, orantısı bozulmadan ortalanmış.
    filter_complex = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},gblur=sigma=20,eq=brightness=-0.08[bgblur];"
        f"[fg]scale={TARGET_WIDTH}:-2:force_original_aspect_ratio=decrease[fgscaled];"
        f"[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2[merged];"
        f"[merged]drawtext=textfile={title_path}:fontfile='{TITLE_FONT}':"
        f"fontcolor=white:fontsize={TITLE_FONT_SIZE}:box=1:boxcolor=black@0.55:boxborderw=16:"
        f"text_align=center:x=(w-text_w)/2:y={video_top}-text_h-{TITLE_GAP}:line_spacing=8[titled];"
        f"[titled]subtitles={ass_path}[out]"
    )

    cmd = [FFMPEG, "-y"]
    if clip_start is not None:
        cmd += ["-ss", str(clip_start)]
    cmd += ["-i", str(input_path)]
    if clip_duration is not None:
        cmd += ["-t", str(clip_duration)]
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg hatası: {result.stderr[-2000:]}")
