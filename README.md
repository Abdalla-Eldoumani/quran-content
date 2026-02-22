# Quran Verse Videos

Generates vertical videos (1080x1920) of Quran verses — Arabic text over scenic backgrounds with recitation audio. Built for Instagram Reels, TikTok, and YouTube Shorts.

The text appears in sync with the recitation: roughly five words at a time, centered on screen, then the next group, and so on until the verse ends. Arabic only, no English translation.

## Project structure

```
quran-content/
├── fonts/
│   ├── Amiri-Regular.ttf        # Arabic font (with tashkeel support)
│   └── OpenSans-Regular.ttf     # Used for the surah reference line
├── output/                      # Generated videos land here
│   └── generation.log           # Log from the last run
├── verses.json                  # Which verses to generate (edit this)
├── generate_videos.py           # The main script
└── README.md
```

## What you need

- **Python 3.12+**
- **FFmpeg** on your PATH (both `ffmpeg` and `ffprobe`)
- **Pexels API key** — free at https://www.pexels.com/api/
- Python packages:
  ```
  pip install requests python-bidi arabic-reshaper Pillow
  ```

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

4. Generate all 30 verses:
   ```bash
   python generate_videos.py
   ```
   This takes a while — each verse needs multiple API calls and an FFmpeg render pass. Videos are saved as `output/verse_001_2_255.mp4`, etc.

## How to pick verses

Edit `verses.json`. Each entry looks like this:

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

Available reciters: `ar.alafasy`, `ar.husary`, `ar.minshawi`, `ar.muhammadayyoub`, `ar.abdurrahmaansudais`.

For scenery queries, stick to nature terms. Add "aerial", "drone", "timelapse", or "close up" to avoid results with people in them.

## Where the data comes from

- Verse text and audio: [AlQuran Cloud API](https://alquran.cloud/api) (quran-uthmani edition, full tashkeel)
- Background clips: [Pexels Videos API](https://www.pexels.com/api/)

Nothing is hardcoded — all text and audio is fetched at runtime.

---

**N/A — Posting and scheduling**

This project only handles video generation. Uploading to Instagram, TikTok, or YouTube is a manual step. None of these platforms offer a public API for posting Reels/Shorts that individuals can freely use, so there is no reliable way to automate that part. Generate your videos, review them, and upload by hand.