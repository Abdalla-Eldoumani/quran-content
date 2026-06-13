# Quran Verse Videos

Generates vertical videos (1080×1920) of Quran verses — Arabic text over scenic backgrounds with recitation audio. Built for Instagram Reels, TikTok, and YouTube Shorts.

The text appears in sync with the recitation: about five words at a time, centered on screen. Timing is extracted from the actual audio using Whisper (`faster-whisper`), with Quran.com proportional scaling as a fallback. Arabic only, no English translation.

## Project structure

```
quran-content/
├── .github/workflows/
│   └── daily_post.yml             # GitHub Actions: daily generate + post
├── docs/
│   └── automation-setup.md        # Step-by-step automation setup guide
├── fonts/
│   ├── Amiri-Regular.ttf          # Arabic font (with tashkeel support)
│   └── OpenSans-Regular.ttf       # Used for the surah reference line
├── output/                        # Generated videos land here (gitignored)
├── verses.json                    # 1,282 passages covering the entire Quran
├── state.json                     # Tracks next verse index + run history
├── generate_verses_json.py        # Script to regenerate verses.json
├── generate_videos.py             # The main video generation script
├── auto_post.py                   # Automated daily posting pipeline
├── setup_meta.py                  # One-time Meta token setup
├── setup_youtube.py               # One-time YouTube OAuth setup
├── .env.example                   # Template for environment variables
└── README.md
```

## What you need

- **Python 3.12+**
- **FFmpeg** on your PATH (both `ffmpeg` and `ffprobe`)
- **Pexels API key** — free at https://www.pexels.com/api/
- Python packages:
  ```
  pip install requests python-bidi arabic-reshaper Pillow faster-whisper
  ```
  For automated posting, also install:
  ```
  pip install python-dotenv google-auth-oauthlib google-api-python-client
  ```
- Optional: set `WHISPER_MODEL` env var to override model size (default: `large-v3`, use `small` for CI/testing)

## How to generate videos

1. Set your Pexels key:
   ```bash
   export PEXELS_API_KEY="your_key_here"
   ```

2. Test with a single verse first:
   ```bash
   python generate_videos.py --test
   ```
   This generates only the first verse in `verses.json`. Check `output/` for the result. If it looks and sounds right, move on.

3. Generate a specific verse by number:
   ```bash
   python generate_videos.py --verse 5
   ```

4. Generate without subtitles (background + audio only, no Whisper needed):
   ```bash
   python generate_videos.py --verse 5 --no-subtitles
   ```

5. Generate all verses (resumes from where you left off):
   ```bash
   python generate_videos.py
   ```
   The script reads `state.json` and picks up from the next ungenerated verse. After each successful video, it advances the counter so you can stop and restart at any time. Videos are saved as `output/verse_001_2_255.mp4`, etc.

   With 1,282 entries in `verses.json`, generating everything takes a long time. Stop with Ctrl+C whenever you want — progress is saved after each verse.

## About verses.json

The file contains **1,282 passage entries covering all 6,236 verses** of the Quran:

- **66 famous standalone verses** appear first — Ayat al-Kursi, du'as of the Prophets, beloved passages. Best for starting your content.
- **1,216 thematic passages** cover the rest, grouped into meaningful ranges of 3–7 ayahs so nothing is cut mid-thought.

Major surahs have curated thematic breakpoints. Short surahs (≤15 ayahs) are kept whole. At one video per day, this is roughly **3.5 years of content**.

Five reciters are distributed evenly across entries. All reciters get exact word-level timing via Whisper transcription of the actual audio. Quran.com timestamps (available for four reciters) serve as a fallback if Whisper fails.

| Reciter | AlQuran Cloud ID | Quran.com ID |
|---|---|---|
| Mishary Rashid al-Afasy | `ar.alafasy` | 7 |
| Mahmoud Khaleel al-Husary | `ar.husary` | 6 |
| Muhammad Siddiq al-Minshawi | `ar.minshawi` | 9 |
| Muhammad Ayyub | `ar.muhammadayyoub` | N/A |
| Abdul Rahman As-Sudais | `ar.abdurrahmaansudais` | 3 |

Each entry looks like this:

```json
{
  "surah": 94,
  "ayah": 5,
  "ayah_end": 6,
  "name": "With Hardship Comes Ease",
  "reciter": "ar.minshawi",
  "scenery_query": "spring cherry blossom close up"
}
```

| Field | What it does |
|---|---|
| `surah`, `ayah` | Starting verse reference |
| `ayah_end` | Last ayah in range (same as `ayah` for a single verse) |
| `name` | Label for logs — not shown in the video |
| `reciter` | Reciter ID from AlQuran Cloud API |
| `scenery_query` | Pexels search query for the background video |

## Customizing verses.json

Edit `generate_verses_json.py` and re-run it:

```bash
python generate_verses_json.py
```

Inside the script you can:
- Add or remove reciters in the `RECITERS` list
- Change scenery queries in the `SCENERY_QUERIES` list
- Add curated thematic breakpoints for any surah in `CURATED_PASSAGES`
- Add famous standalone verses in `FAMOUS_VERSES`
- Adjust the auto-chunk size (default: 5 verses per passage)

For scenery queries, stick to nature terms and add "aerial", "drone", "timelapse", or "close up" to reduce the chance of videos containing people.

## Where the data comes from

- Verse text: [AlQuran Cloud API](https://alquran.cloud/api) — `quran-uthmani` edition with full tashkeel
- Recitation audio: [AlQuran Cloud API](https://alquran.cloud/api) — per-ayah MP3s, concatenated for multi-ayah passages
- Word-level timing: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — extracts exact timestamps from the actual audio file
- Fallback timing: [Quran.com API v4](https://api-docs.quran.com/) — word-level timestamps scaled proportionally (used if Whisper fails)
- Background clips: [Pexels Videos API](https://www.pexels.com/api/)

No Quranic content is hardcoded or AI-generated. All text and audio is fetched from authenticated sources at runtime.

## Automated daily posting

A GitHub Actions workflow generates one video per day and posts it to Instagram, Facebook, and YouTube automatically.

**Supported platforms:**
- **Instagram** — posted as a Reel via Meta Graph API
- **Facebook** — posted as a native video to your Page
- **YouTube** — uploaded as a Short via YouTube Data API v3

For detailed step-by-step instructions, see [docs/automation-setup.md](docs/automation-setup.md).

### Quick start

1. Set up Meta credentials:
   ```bash
   # Fill in META_SHORT_TOKEN, META_APP_ID, META_APP_SECRET in .env
   python3 setup_meta.py
   ```

2. Set up YouTube credentials:
   ```bash
   # Fill in YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET in .env
   python3 setup_youtube.py
   ```

3. Copy all tokens to GitHub repository secrets (Settings > Secrets and variables > Actions):
   - `PEXELS_API_KEY`, `META_ACCESS_TOKEN`, `IG_USER_ID`, `FB_PAGE_ID`
   - `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`

4. The workflow runs daily at 2 PM UTC. To trigger manually: Actions > Daily Quran Post > Run workflow.

5. Test locally:
   ```bash
   python3 auto_post.py --dry-run          # Simulate everything
   python3 auto_post.py --generate-only    # Generate one video, don't post
   python3 auto_post.py --post-only        # Post the latest generated video
   python3 auto_post.py --post-all         # Post all unposted videos in output/
   python3 auto_post.py --platform meta    # Post to Meta only
   python3 auto_post.py --platform youtube # Post to YouTube only
   ```

**YouTube note:** API projects created after July 2020 upload videos as private until you pass a compliance audit in Google Cloud Console (APIs & Services > YouTube Data API v3 > Compliance). Videos will upload but stay private until the audit passes.

`state.json` tracks two cursors: `next_index` (which verse to generate next) and `next_post_index` (which verse to post next). This lets you batch-generate videos with `generate_videos.py`, then drip-post them with `--post-all`. The workflow commits state back to the repo after each run.

## Planned reels

Beside the daily sequential pipeline there is a second mode for building a one-off themed reel. You name a theme or a current moment, pick a verified passage, and render a short video with the Arabic and a verbatim English translation. The finished file is emailed for review first, and posting stays a separate, explicit step. This mode never reads or advances the daily `state.json` cursors.

Themes and their passages live in `themes.json`, a hand-maintained index. A passage renders only when its `verified` flag is true, which you set yourself after confirming the range reads as a complete thought on its own. Until then the planner lists it with an `UNVERIFIED` marker and the renderer refuses it. Nothing here chooses or interprets a passage for you: matching is plain keyword search and the selection is yours.

Every planned reel finishes under 60 seconds. The planner measures the real recitation length for the chosen reciter before you commit, so a passage that would run long is shown as `OVER BUDGET` and cannot be picked. The translation is the Saheeh International (`en.sahih`) text, fetched at runtime and shown in a lower third that switches as each ayah is recited.

1. Plan. Match a theme or a free-text topic and see the measured duration for each candidate:
   ```bash
   python3 plan_reel.py --topic "flood relief" --reciter ar.minshawi
   python3 plan_reel.py --theme hardship-and-relief --pick 1
   ```
   `--pick N` writes `output/reels/<slug>/reel_plan.json`. Translation is on by default; pass `--no-translation` to omit it. Scenery defaults rotate through the project's nature queries; if you pass `--scenery`, keep it to nature terms (add aerial, drone, timelapse, or close up) so clips stay free of people and text.

2. Render the picked plan into its own directory:
   ```bash
   python3 generate_videos.py --plan output/reels/<slug>/reel_plan.json
   ```
   This produces the mp4 and a caption sidecar beside it. It re-checks the duration budget before encoding and never touches `state.json`.

3. Deliver the reel and caption to yourself for review over email:
   ```bash
   python3 deliver_reel.py output/reels/<slug>
   ```
   Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, and `DELIVER_TO` in the environment. A file at or over 22MB arrives as the caption plus a local path instead of an attachment.

4. Post one specific file when you are ready, with a dry run first:
   ```bash
   python3 auto_post.py --video output/reels/<slug>/<file>.mp4 --caption-file output/reels/<slug>/caption.txt --dry-run
   python3 auto_post.py --video output/reels/<slug>/<file>.mp4 --caption-file output/reels/<slug>/caption.txt
   ```
   Direct posting records nothing in `state.json`. Instagram uploads through the Meta resumable endpoint; the caption, title, and description default to the sidecars beside the video.

## Manual posting

You can also upload videos manually:

- **Instagram + Facebook**: Meta Business Suite (business.facebook.com) — schedule Reels up to 75 days ahead, free
- **TikTok**: TikTok Studio (tiktok.com/tiktokstudio) — schedule up to 10 days ahead, free
- **YouTube Shorts**: YouTube Studio — schedule uploads, free

## License

MIT