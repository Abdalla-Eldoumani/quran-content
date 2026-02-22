# Quran Verse Videos

Generates vertical videos (1080×1920) of Quran verses — Arabic text over scenic backgrounds with recitation audio. Built for Instagram Reels, TikTok, and YouTube Shorts.

The text appears in sync with the recitation: roughly five words at a time, centered on screen, then the next group, and so on until the verse ends. Arabic only, no English translation.

## Project structure

```
quran-content/
├── fonts/
│   ├── Amiri-Regular.ttf          # Arabic font (with tashkeel support)
│   └── OpenSans-Regular.ttf       # Used for the surah reference line
├── output/                        # Generated videos land here
│   └── generation.log             # Log from the last run
├── verses.json                    # 1,282 passages covering the entire Quran
├── generate_verses_json.py        # Script to regenerate verses.json
├── generate_videos.py             # The main video generation script
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

4. Generate all verses:
   ```bash
   python generate_videos.py
   ```
   Each verse needs multiple API calls and an FFmpeg render pass. Videos are saved as `output/verse_001_2_255.mp4`, etc.

   With 1,282 entries in `verses.json`, generating everything takes a long time. Generate in batches or ranges as needed.

## About verses.json

The file contains **1,282 passage entries covering all 6,236 verses** of the Quran:

- **66 famous standalone verses** (marked with ★) appear first — Ayat al-Kursi, du'as of the Prophets, beloved passages. Best for starting your content.
- **1,216 thematic passages** cover the rest, grouped into meaningful ranges of 3–7 ayahs so nothing is cut mid-thought.

Major surahs have curated thematic breakpoints. Short surahs (≤15 ayahs) are kept whole. At one video per day, this is roughly **3.5 years of content**.

Five reciters are distributed evenly across entries:

| Reciter | API ID |
|---|---|
| Mishary Rashid al-Afasy | `ar.alafasy` |
| Mahmoud Khaleel al-Husary | `ar.husary` |
| Muhammad Siddiq al-Minshawi | `ar.minshawi` |
| Muhammad Ayyub | `ar.muhammadayyoub` |
| Abdul Rahman As-Sudais | `ar.abdurrahmaansudais` |

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

- Verse text and audio: [AlQuran Cloud API](https://alquran.cloud/api) — `quran-uthmani` edition with full tashkeel
- Background clips: [Pexels Videos API](https://www.pexels.com/api/)

No Quranic content is hardcoded or AI-generated. All text and audio is fetched from authenticated sources at runtime.

## Posting

This project handles video generation only. Upload to platforms manually:

- **Instagram + Facebook**: Meta Business Suite (business.facebook.com) — schedule Reels up to 75 days ahead, free
- **TikTok**: TikTok Studio (tiktok.com/tiktokstudio) — schedule up to 10 days ahead, free
- **YouTube Shorts**: YouTube Studio — schedule uploads, free

## License

MIT