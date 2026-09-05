from __future__ import annotations

import argparse
import csv
import pathlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import config
from .hashtags import build_hashtags, build_keywords

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_PATH = config.ROOT_DIR / "youtube_client_secret.json"
TOKEN_PATH = config.ROOT_DIR / "youtube_token.json"


def get_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise RuntimeError(
                    f"{CLIENT_SECRET_PATH} bulunamadı. Google Cloud'dan indirdiğin "
                    "OAuth client JSON dosyasını bu isimle proje köküne koy."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_video(
    file_path: pathlib.Path,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = "private",
) -> str:
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "24",  # Entertainment
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }

    media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  yükleniyor... %{int(status.progress() * 100)}")

    return response["id"]


def main() -> None:
    parser = argparse.ArgumentParser(description="output/ready.csv'deki klipleri YouTube'a yükler.")
    parser.add_argument("--csv", default=str(config.OUTPUT_DIR / "ready.csv"))
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        ready_path = row.get("hazir_dosya", "")
        if not ready_path or not pathlib.Path(ready_path).exists():
            continue

        title = row.get("baslik", "").strip() or "Twitch Clip"
        category = row.get("kategori", "")
        language = row.get("dil", "")
        broadcaster = row.get("yayinci", "")

        hashtags = build_hashtags(category, language)
        keywords = build_keywords(category, language)

        print(f"\n{broadcaster} - {title}")
        print(f"  Kategori: {category} | Dil: {language}")
        print(f"  Hashtag'ler: {' '.join(hashtags)}")
        print(f"  Dosya: {ready_path}")
        answer = input("  YouTube'a yükle? (e/h): ").strip().lower()
        if answer != "e":
            print("  Atlandı.")
            continue

        if "#shorts" not in title.lower():
            title = f"{title} #Shorts"
        description = f"Kaynak: {row.get('link', '')}\n\n{' '.join(hashtags)}"

        video_id = upload_video(
            pathlib.Path(ready_path),
            title=title,
            description=description,
            tags=keywords,
            privacy_status=args.privacy,
        )
        print(f"  Yüklendi: https://youtu.be/{video_id}")


if __name__ == "__main__":
    main()
