import argparse
import csv
from datetime import datetime, timedelta, timezone

from . import config
from .downloader import download_clip
from .scorer import rank_and_select
from .twitch_api import TwitchClient

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Twitch'te viral klipleri bulup indirir.")
    parser.add_argument("--languages", default="en,tr,es", help="Virgülle ayrılmış dil kodları")
    parser.add_argument(
        "--broadcasters",
        default="",
        help=(
            "Virgülle ayrılmış Twitch kullanıcı adları (ör. jasontheween,stableronaldo). "
            "Verilirse trend yayıncı taraması atlanır, sadece bu yayıncıların klipleri çekilir."
        ),
    )
    parser.add_argument("--streamers-per-language", type=int, default=40)
    parser.add_argument("--clips-per-streamer", type=int, default=20)
    parser.add_argument("--hours", type=float, default=48, help="Klip arama penceresi (saat)")
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--per-streamer-cap", type=int, default=2)
    parser.add_argument("--min-duration", type=float, default=5.0)
    parser.add_argument("--max-duration", type=float, default=90.0)
    parser.add_argument("--ideal-min", type=float, default=15.0)
    parser.add_argument("--ideal-max", type=float, default=60.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    client = TwitchClient(config.TWITCH_CLIENT_ID, config.TWITCH_CLIENT_SECRET)

    now = datetime.now(timezone.utc)
    started_at = (now - timedelta(hours=args.hours)).strftime(TIME_FORMAT)
    ended_at = now.strftime(TIME_FORMAT)

    requested_logins = [name.strip() for name in args.broadcasters.split(",") if name.strip()]

    broadcasters: dict[str, dict] = {}
    if requested_logins:
        print(f"Belirtilen {len(requested_logins)} yayıncı çözümleniyor: {', '.join(requested_logins)}")
        users = client.get_users_by_login(requested_logins)
        found_logins = {u["login"].lower() for u in users}
        missing = [n for n in requested_logins if n.lower() not in found_logins]
        if missing:
            print(f"  [UYARI] Twitch'te bulunamadı: {', '.join(missing)}")
        for user in users:
            broadcasters[user["id"]] = {"user_id": user["id"], "user_name": user["display_name"]}
        print(f"{len(broadcasters)} yayıncı bulundu.")
    else:
        for lang in languages:
            print(f"[{lang}] trend yayıncılar çekiliyor...")
            streams = client.get_top_streams(lang, limit=args.streamers_per_language)
            for stream in streams:
                broadcasters.setdefault(stream["user_id"], stream)
            print(f"[{lang}] {len(streams)} yayıncı bulundu.")

    print(f"Toplam {len(broadcasters)} benzersiz yayıncı için klipler çekiliyor...")
    all_clips: list[dict] = []
    for i, broadcaster_id in enumerate(broadcasters, start=1):
        clips = client.get_clips(
            broadcaster_id, started_at, ended_at, limit=args.clips_per_streamer
        )
        all_clips.extend(clips)
        if i % 10 == 0 or i == len(broadcasters):
            print(f"  {i}/{len(broadcasters)} yayıncı tarandı, {len(all_clips)} klip toplandı.")

    print(f"Toplam {len(all_clips)} klip bulundu, skorlanıyor...")
    selected = rank_and_select(
        all_clips,
        top_n=args.top_n,
        per_streamer_cap=args.per_streamer_cap,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        ideal_min=args.ideal_min,
        ideal_max=args.ideal_max,
    )
    print(f"{len(selected)} klip seçildi.")

    game_names = client.get_games([clip.get("game_id", "") for clip in selected])

    config.CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for clip in selected:
        print(f"İndiriliyor: {clip['broadcaster_name']} - {clip['title'][:60]}")
        local_path = download_clip(clip, config.CLIPS_DIR)
        rows.append(
            {
                "yayinci": clip["broadcaster_name"],
                "baslik": clip.get("title", ""),
                "dil": clip.get("language", ""),
                "kategori": game_names.get(clip.get("game_id", ""), clip.get("game_id", "")),
                "sure_sn": clip.get("duration", ""),
                "view": clip.get("view_count", ""),
                "skor": clip.get("score", ""),
                "link": clip.get("url", ""),
                "yerel_dosya": str(local_path) if local_path else "",
            }
        )

    with open(config.CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Bitti. CSV: {config.CSV_PATH}")


if __name__ == "__main__":
    main()
