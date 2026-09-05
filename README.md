# twitch-viral-clips

End-to-end automation that finds viral Twitch clips across three language markets, reformats them for vertical short-form video with automatic captions, and uploads them to YouTube Shorts.

Built to remove the manual work from short-form content production: discovery, scoring, download, editing and publishing all run from three commands, with a human approval gate before anything goes live.

## Pipeline

**1. Discovery and download** — Scans trending Twitch streamers in English, Turkish and Spanish via the Helix API, pulls their clips from a configurable time window, ranks them by view velocity and downloads the top selection as `.mp4`.

**2. Editing** — Transcribes each clip's speech with Whisper, then rebuilds the video in 9:16 vertical format with the title rendered at the top and generated captions at the bottom.

**3. Upload** — Walks through the processed clips one by one, showing the generated title, category and hashtags, and uploads the approved ones to YouTube. Defaults to private visibility so nothing publishes unreviewed.

Scoring uses view velocity rather than raw view count, so a clip with 5,000 views in two hours outranks one with 20,000 views over three days.

## Usage

```bash
cd twitch-viral-clips
source .venv/bin/activate
```

### Find and download clips

```bash
python -m src.main --top-n 15 --streamers-per-language 40
```

| Flag | Default | Purpose |
|---|---|---|
| `--top-n` | 15 | How many clips to select |
| `--streamers-per-language` | 40 | Streamers scanned per language (en/tr/es) |
| `--hours` | 48 | Clip time window |
| `--broadcasters` | — | Comma-separated usernames; skips trending discovery entirely and pulls only from these channels |

```bash
# Target specific streamers instead of scanning trends
python -m src.main --broadcasters jasontheween,stableronaldo --top-n 10
```

Writes `.mp4` files to `output/clips/` and a metadata table to `output/clips.csv`.

### Add captions and reformat

```bash
python -m src.edit_clips
```

Runs Whisper transcription and rebuilds each clip vertically with title and caption overlays. Takes roughly 1–3 minutes per clip.

Writes to `output/ready/` and `output/ready.csv`. Clips deleted from this folder are skipped at the upload stage, so this doubles as a manual quality gate.

### Upload to YouTube

```bash
python -m src.youtube_upload
```

Prompts for confirmation per clip before uploading. Private by default:

```bash
python -m src.youtube_upload --privacy public
```

## Setup

Requires Python 3.10+, FFmpeg, a Twitch developer application and a Google Cloud OAuth client.

```bash
git clone https://github.com/toprakbogachan-max/twitch-viral-clips.git
cd twitch-viral-clips
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
```

For YouTube upload, create an OAuth client of type **Desktop app** in the Google Cloud Console and save the credentials as `youtube_client_secret.json` in the project root. The first upload opens a browser for consent once; the resulting `youtube_token.json` is reused and refreshed automatically afterwards.

Neither credential file is tracked in this repository.

## Design notes

**Approval gate by design.** The pipeline is fully automated up to publishing, but never publishes without a human "yes" and defaults to private visibility. Fully autonomous posting to a real channel is a reputational risk that isn't worth the saved keystroke.

**Whisper over platform captions.** Twitch clips have no reliable caption track, so transcription happens locally. This also keeps the pipeline independent of any captioning API.

**Three language markets.** Scanning English, Turkish and Spanish roughly triples the candidate pool and surfaces clips that English-only tooling never sees.

**Configurable thresholds.** Scoring and selection parameters are exposed as CLI flags and config values, so output quality can be tuned without touching pipeline logic.

## Roadmap

- [ ] TikTok publishing via the Content Posting API — pending developer portal approval; unapproved apps can only push drafts into the TikTok app rather than publish directly
- [ ] Podcast source support (long-form clip extraction)
- [ ] Automatic highlight detection within longer clips

## Tech

Python · Twitch Helix API · OpenAI Whisper · FFmpeg · YouTube Data API v3 (OAuth 2.0) · `requests` · `python-dotenv`

## License

MIT
