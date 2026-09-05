import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")

if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
    raise RuntimeError(
        "TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET bulunamadı. "
        f".env dosyasını {ROOT_DIR}/.env.example örneğine göre doldurun."
    )

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

OUTPUT_DIR = ROOT_DIR / "output"
CLIPS_DIR = OUTPUT_DIR / "clips"
CSV_PATH = OUTPUT_DIR / "clips.csv"
