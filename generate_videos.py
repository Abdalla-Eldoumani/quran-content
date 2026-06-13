#!/usr/bin/env python3
"""
Quran Verse Video Generator

Generates short-form vertical videos (1080x1920) of Quran verses.
Arabic text appears in timed chunks (~5 words) synced to the recitation audio,
over scenic background videos from Pexels.
"""

import argparse
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

# Fix Windows console encoding for Arabic text output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import arabic_reshaper
import requests
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

# ── Constants ────────────────────────────────────────────────────────────────

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(SCRIPT_DIR, "fonts")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
VERSES_FILE = os.path.join(SCRIPT_DIR, "verses.json")
STATE_FILE = os.path.join(SCRIPT_DIR, "state.json")
LOG_FILE = os.path.join(OUTPUT_DIR, "generation.log")

ARABIC_FONT_PATH = os.path.join(FONTS_DIR, "Amiri-Regular.ttf")
ENGLISH_FONT_PATH = os.path.join(FONTS_DIR, "OpenSans-Regular.ttf")

ARABIC_FONT_SIZE = 72
REFERENCE_FONT_SIZE = 30

ALQURAN_API_BASE = "https://api.alquran.cloud/v1"
PEXELS_API_BASE = "https://api.pexels.com"

AUDIO_DELAY_S = 1.5  # fallback delay when Whisper is unavailable
MIN_AUDIO_DELAY_S = 0.3  # minimum visual buffer before first word
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "large-v3")
EXTRA_DURATION_S = 3.0
API_SLEEP_S = 2
WORDS_PER_CHUNK = 5

FALLBACK_RECITER = "ar.alafasy"
FALLBACK_SCENERY = "ocean waves aerial"

QURANCOM_API_BASE = "https://api.quran.com/api/v4"
QURANCOM_RECITER_IDS = {
    "ar.alafasy": 7,
    "ar.husary": 6,
    "ar.minshawi": 9,
    "ar.abdurrahmaansudais": 3,
}
CHUNK_ANTICIPATION_S = 0.150  # show text 150ms before reciter speaks

# Arabic reshaper config: preserve tashkeel/harakat
RESHAPER_CONFIG = {
    "delete_harakat": False,
    "delete_tatweel": False,
}


# ── Logging ──────────────────────────────────────────────────────────────────

_log_lines = []


def log(msg):
    """Print and buffer a log line."""
    print(msg)
    _log_lines.append(msg)


def save_log():
    """Write buffered log to output/generation.log."""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(_log_lines) + "\n")
    except Exception:
        pass


# ── Verse loading ────────────────────────────────────────────────────────────

def load_verses():
    """Read and validate verses.json."""
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        verses = json.load(f)
    required_keys = {"surah", "ayah", "name", "reciter", "scenery_query"}
    for i, v in enumerate(verses):
        missing = required_keys - set(v.keys())
        if missing:
            raise ValueError(f"Verse {i} missing keys: {missing}")
        if "ayah_end" not in v:
            v["ayah_end"] = v["ayah"]
    return verses


def load_state():
    """Read state.json (shared with auto_post.py)."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"next_index": 0, "next_post_index": 0, "history": []}


def save_state(state):
    """Write state.json atomically (compatible with auto_post.py)."""
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


# ── API helpers ──────────────────────────────────────────────────────────────

def fetch_verse_text(surah, ayah_start, ayah_end):
    """Fetch Arabic (Uthmani) text for a verse range."""
    all_arabic = []
    surah_name = ""
    surah_name_ar = ""

    for ayah in range(ayah_start, ayah_end + 1):
        url = f"{ALQURAN_API_BASE}/ayah/{surah}:{ayah}/editions/quran-uthmani"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()["data"][0]
        all_arabic.append(data["text"])
        if not surah_name:
            surah_name = data["surah"]["englishName"]
            surah_name_ar = data["surah"]["name"]
        if ayah < ayah_end:
            time.sleep(1)

    arabic_text = " ".join(all_arabic)
    return arabic_text, surah_name, surah_name_ar


def fetch_audio(surah, ayah_start, ayah_end, reciter, dest):
    """Download recitation audio for a verse range. Concatenates if multiple ayahs."""
    audio_files = []
    tmpdir = tempfile.mkdtemp(prefix="quran_audio_")

    try:
        for ayah in range(ayah_start, ayah_end + 1):
            url = f"{ALQURAN_API_BASE}/ayah/{surah}:{ayah}/{reciter}"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            audio_url = resp.json()["data"]["audio"]
            log(f"    Audio URL ({surah}:{ayah}): {audio_url}")
            time.sleep(API_SLEEP_S)

            audio_path = os.path.join(tmpdir, f"ayah_{ayah}.mp3")
            audio_resp = requests.get(audio_url, timeout=60)
            audio_resp.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(audio_resp.content)

            size = os.path.getsize(audio_path)
            if size == 0:
                raise RuntimeError(f"Downloaded audio for {surah}:{ayah} is empty (0 bytes)")
            log(f"    Downloaded {surah}:{ayah} audio: {size} bytes")
            audio_files.append(audio_path)

        if len(audio_files) == 1:
            shutil.copy2(audio_files[0], dest)
        else:
            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w") as f:
                for ap in audio_files:
                    f.write(f"file '{ap}'\n")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_list, "-c", "copy", dest,
                ],
                check=True, capture_output=True, text=True,
            )
            log(f"    Concatenated {len(audio_files)} audio files")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def get_audio_duration(path):
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def verify_video_has_audio(path):
    """Check that the output video contains an audio stream."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            path,
        ],
        capture_output=True, text=True,
    )
    has_audio = "audio" in result.stdout
    if not has_audio:
        log("  WARNING: Output video has NO audio stream!")
    return has_audio


def fetch_background_video(query, dest):
    """Download a random HD portrait-oriented video from Pexels (>= 10s preferred)."""
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY environment variable is not set")

    headers = {"Authorization": api_key}

    def _search(q):
        url = f"{PEXELS_API_BASE}/videos/search"
        params = {"query": q, "orientation": "portrait", "size": "large", "per_page": 30}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("videos", [])

    videos = _search(query)
    if not videos:
        log(f"    No Pexels results for '{query}', retrying with '{FALLBACK_SCENERY}'")
        time.sleep(API_SLEEP_S)
        videos = _search(FALLBACK_SCENERY)
    if not videos:
        raise RuntimeError("No background videos found on Pexels")

    long_videos = [v for v in videos if v.get("duration", 0) >= 10]
    pool = long_videos if long_videos else videos
    video = random.choice(pool)

    video_files = sorted(
        video["video_files"],
        key=lambda vf: vf.get("height", 0),
        reverse=True,
    )
    download_url = video_files[0]["link"]
    log(f"    Pexels video: {video.get('duration', '?')}s, "
        f"{video_files[0].get('width', '?')}x{video_files[0].get('height', '?')}")

    time.sleep(API_SLEEP_S)
    vid_resp = requests.get(download_url, timeout=120, stream=True)
    vid_resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in vid_resp.iter_content(chunk_size=8192):
            f.write(chunk)


def fetch_word_segments(surah, ayah_start, ayah_end, reciter):
    """Fetch word-level timing segments from Quran.com API.

    Returns (chapter_audio_url, verse_timestamps) where verse_timestamps is a
    dict mapping ayah number to a list of [word_index, start_ms, end_ms] segments.
    Returns (None, None) if the reciter is not mapped or any request fails.
    """
    reciter_id = QURANCOM_RECITER_IDS.get(reciter)
    if reciter_id is None:
        log(f"    Reciter {reciter} not mapped on Quran.com, skipping word-level timing")
        return None, None

    try:
        url = f"{QURANCOM_API_BASE}/chapter_recitations/{reciter_id}/{surah}"
        resp = requests.get(url, params={"segments": "true"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        audio_file = data.get("audio_file", {})
        chapter_audio_url = audio_file.get("audio_url")
        if not chapter_audio_url:
            log("    No chapter audio URL in Quran.com response")
            return None, None

        timestamps = audio_file.get("timestamps", {})

        # Extract timestamps for only the requested ayah range
        verse_timestamps = {}
        for ayah in range(ayah_start, ayah_end + 1):
            key = str(ayah)
            if key not in timestamps:
                log(f"    Missing timestamps for ayah {ayah} in Quran.com response")
                return None, None
            # Filter out malformed segments (keep only entries with exactly 3 elements)
            segments = [s for s in timestamps[key] if isinstance(s, list) and len(s) == 3]
            if not segments:
                log(f"    No valid segments for ayah {ayah} after filtering")
                return None, None
            verse_timestamps[ayah] = segments

        log(f"    Quran.com: got word segments for {len(verse_timestamps)} ayah(s)")
        return chapter_audio_url, verse_timestamps

    except Exception as e:
        log(f"    Quran.com API error: {e}")
        return None, None


# ── Arabic text processing ───────────────────────────────────────────────────

_reshaper = arabic_reshaper.ArabicReshaper(configuration=RESHAPER_CONFIG)


def reshape_arabic(text):
    """Reshape Arabic text and apply bidi algorithm. Preserves tashkeel."""
    reshaped = _reshaper.reshape(text)
    return get_display(reshaped)


def wrap_arabic_text(text, font, max_width, draw):
    """
    Wrap Arabic text into lines that fit within max_width.
    Words are split BEFORE reshaping; each line is reshaped individually
    to preserve letter connections.
    """
    words = text.split()
    lines = []
    current_line_words = []

    for word in words:
        test_line = " ".join(current_line_words + [word])
        test_display = reshape_arabic(test_line)
        bbox = draw.textbbox((0, 0), test_display, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width and current_line_words:
            current_line_words.append(word)
        elif not current_line_words:
            current_line_words.append(word)
        else:
            line_text = " ".join(current_line_words)
            lines.append(reshape_arabic(line_text))
            current_line_words = [word]

    if current_line_words:
        line_text = " ".join(current_line_words)
        lines.append(reshape_arabic(line_text))

    return lines


def split_into_chunks(text, words_per_chunk=WORDS_PER_CHUNK):
    """Split Arabic text into groups of ~N words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunks.append(" ".join(words[i:i + words_per_chunk]))
    return chunks


def _flatten_segments(verse_timestamps, ayah_start, ayah_end):
    """Flatten word segments across all ayahs into one ordered list."""
    all_segments = []
    for ayah in range(ayah_start, ayah_end + 1):
        all_segments.extend(verse_timestamps.get(ayah, []))
    return all_segments


def _map_chunks_to_segments(num_text_words, num_segments, words_per_chunk):
    """Map text chunk boundaries to segment index ranges via proportional mapping.

    AlQuran Cloud and Quran.com tokenize Arabic differently, so the text word
    count and segment count often don't match. This maps each text chunk to the
    corresponding segment range proportionally, so timing always works regardless
    of word count differences.
    """
    num_chunks = -(-num_text_words // words_per_chunk)  # ceil division
    ranges = []
    for i in range(num_chunks):
        text_start = i * words_per_chunk
        text_end = min((i + 1) * words_per_chunk, num_text_words)
        seg_start = round(text_start * num_segments / num_text_words)
        seg_end = round(text_end * num_segments / num_text_words)
        seg_start = min(seg_start, num_segments - 1)
        seg_end = max(seg_start + 1, min(seg_end, num_segments))
        ranges.append((seg_start, seg_end))
    return ranges


_whisper_model = None


def get_whisper_model():
    """Lazy singleton for the Whisper model. Imports faster_whisper on first call."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        log(f"  Loading Whisper model ({WHISPER_MODEL_SIZE})...")
        _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


def transcribe_word_timestamps(audio_path):
    """Extract word-level timestamps from audio using faster-whisper.

    Returns (word_segments, speech_onset_s) where word_segments is a list of
    (start_s, end_s) per word, and speech_onset_s is the start time of the first word.
    Returns (None, None) on failure.
    """
    try:
        model = get_whisper_model()
        segments, _ = model.transcribe(
            audio_path, language="ar", word_timestamps=True, vad_filter=True
        )
        word_segments = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    word_segments.append((w.start, w.end))
        if not word_segments:
            log("  Whisper: no words detected in audio")
            return None, None
        speech_onset_s = word_segments[0][0]
        log(f"  Whisper: {len(word_segments)} words detected, speech onset at {speech_onset_s:.3f}s")
        return word_segments, speech_onset_s
    except Exception as e:
        log(f"  Whisper transcription failed: {e}")
        return None, None


def build_whisper_chunk_timings(whisper_segments, num_text_words,
                                words_per_chunk=WORDS_PER_CHUNK):
    """Build chunk timings from Whisper word-level timestamps.

    Uses proportional index mapping to handle tokenization mismatches between
    Whisper's detected words and the AlQuran Cloud text words.
    Returns a list of (start_s, end_s) tuples per chunk.
    """
    chunk_ranges = _map_chunks_to_segments(
        num_text_words, len(whisper_segments), words_per_chunk
    )
    timings = []
    for seg_start, seg_end in chunk_ranges:
        chunk_start_s = whisper_segments[seg_start][0]
        chunk_end_s = whisper_segments[seg_end - 1][1]
        timings.append((chunk_start_s, chunk_end_s))
    return timings


def build_proportional_chunk_timings(verse_timestamps, ayah_start, ayah_end,
                                     actual_duration, num_text_words,
                                     words_per_chunk=WORDS_PER_CHUNK):
    """Build chunk timings by scaling a reference reciter's word segments.

    Used when the actual reciter has no Quran.com timestamps (e.g., Muhammad Ayyub).
    Takes word segments from a reference reciter and scales them proportionally
    to the actual audio duration. Returns a list of (start_s, end_s) tuples,
    or None on failure.
    """
    all_segments = _flatten_segments(verse_timestamps, ayah_start, ayah_end)
    if not all_segments:
        return None

    ref_start_ms = all_segments[0][1]
    ref_end_ms = all_segments[-1][2]
    ref_duration_ms = ref_end_ms - ref_start_ms

    if ref_duration_ms <= 0:
        return None

    scale = actual_duration / (ref_duration_ms / 1000.0)

    chunk_ranges = _map_chunks_to_segments(
        num_text_words, len(all_segments), words_per_chunk
    )

    timings = []
    for seg_start, seg_end in chunk_ranges:
        chunk_start_s = ((all_segments[seg_start][1] - ref_start_ms) / 1000.0) * scale
        chunk_end_s = ((all_segments[seg_end - 1][2] - ref_start_ms) / 1000.0) * scale
        timings.append((chunk_start_s, chunk_end_s))

    return timings


# ── Overlay rendering ────────────────────────────────────────────────────────

def draw_rounded_rect(draw_ctx, bbox, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = bbox
    draw_ctx.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def render_chunk_overlay(chunk_text, surah_name, surah_name_ar, surah, ayah, ayah_end, dest):
    """
    Render a 1080x1920 RGBA PNG for one chunk:
    - Arabic chunk text centered vertically on screen
    - Surah reference at the bottom
    """
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    arabic_font = ImageFont.truetype(ARABIC_FONT_PATH, ARABIC_FONT_SIZE)
    reference_font = ImageFont.truetype(ENGLISH_FONT_PATH, REFERENCE_FONT_SIZE)

    max_text_width = VIDEO_WIDTH - 120
    padding = 30
    box_fill = (0, 0, 0, 160)
    shadow_color = (0, 0, 0, 180)
    text_color = (255, 255, 255, 255)
    shadow_offset = 2
    box_x0 = 30
    box_x1 = VIDEO_WIDTH - 30

    # ── Arabic chunk centered on screen ──
    arabic_lines = wrap_arabic_text(chunk_text, arabic_font, max_text_width, draw)
    line_heights = []
    for line in arabic_lines:
        bbox = draw.textbbox((0, 0), line, font=arabic_font)
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 20
    total_height = sum(line_heights) + line_spacing * max(len(arabic_lines) - 1, 0)

    block_y = (VIDEO_HEIGHT - total_height) // 2
    box_y0 = block_y - padding
    box_y1 = block_y + total_height + padding

    draw_rounded_rect(draw, (box_x0, box_y0, box_x1, box_y1), 20, box_fill)

    y = block_y
    for i, line in enumerate(arabic_lines):
        bbox = draw.textbbox((0, 0), line, font=arabic_font)
        line_w = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - line_w) // 2
        draw.text((x + shadow_offset, y + shadow_offset), line, font=arabic_font, fill=shadow_color)
        draw.text((x, y), line, font=arabic_font, fill=text_color)
        y += line_heights[i] + line_spacing

    # ── Reference at bottom ──
    if ayah == ayah_end:
        ref_str = f"{surah}:{ayah}"
    else:
        ref_str = f"{surah}:{ayah}-{ayah_end}"
    reference = f"{surah_name_ar}  |  {surah_name}  |  {ref_str}"
    ref_bbox = draw.textbbox((0, 0), reference, font=reference_font)
    ref_w = ref_bbox[2] - ref_bbox[0]
    ref_h = ref_bbox[3] - ref_bbox[1]

    ref_y = VIDEO_HEIGHT - 200
    ref_box_y0 = ref_y - padding
    ref_box_y1 = ref_y + ref_h + padding
    ref_box_x0 = (VIDEO_WIDTH - ref_w) // 2 - padding - 10
    ref_box_x1 = (VIDEO_WIDTH + ref_w) // 2 + padding + 10

    draw_rounded_rect(draw, (ref_box_x0, ref_box_y0, ref_box_x1, ref_box_y1), 15, box_fill)

    ref_x = (VIDEO_WIDTH - ref_w) // 2
    draw.text((ref_x + shadow_offset, ref_y + shadow_offset), reference, font=reference_font, fill=shadow_color)
    draw.text((ref_x, ref_y), reference, font=reference_font, fill=text_color)

    img.save(dest, "PNG")


# ── Video composition ────────────────────────────────────────────────────────

def compose_video_no_subtitles(bg_path, audio_path, output_path, audio_duration, video_duration,
                               audio_delay_s=None):
    """Compose video with background + audio only, no text overlays."""
    if audio_delay_s is None:
        audio_delay_s = AUDIO_DELAY_S

    delay_ms = int(audio_delay_s * 1000)
    filter_str = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1[outv];"
        f"[1:a]adelay={delay_ms}|{delay_ms},apad[outa]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", bg_path,
        "-i", audio_path,
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-map", "[outa]",
        "-t", str(video_duration),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  FFmpeg stderr: {result.stderr[-800:]}")
        result.check_returncode()


def compose_video(bg_path, chunk_paths, audio_path, output_path, audio_duration, video_duration, chunk_timings=None, audio_delay_s=None):
    """
    Compose final video with timed chunk overlays.

    When chunk_timings is provided (list of (start_s, end_s) tuples from word-level
    timestamps), each overlay is shown at its real recitation time. Otherwise falls
    back to equal-division timing.

    audio_delay_s controls the silence before audio starts. Defaults to AUDIO_DELAY_S
    if not provided (fallback for non-Whisper paths).
    """
    if audio_delay_s is None:
        audio_delay_s = AUDIO_DELAY_S

    num_chunks = len(chunk_paths)

    # Build input list: bg, chunk PNGs, audio
    inputs = ["-stream_loop", "-1", "-i", bg_path]
    for cp in chunk_paths:
        inputs.extend(["-i", cp])
    audio_idx = 1 + num_chunks
    inputs.extend(["-i", audio_path])

    # Build filter_complex
    filters = [
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1[bg]"
    ]

    prev = "bg"
    for i in range(num_chunks):
        if chunk_timings is not None:
            raw_start, raw_end = chunk_timings[i]
            start = max(0.0, audio_delay_s + raw_start - CHUNK_ANTICIPATION_S)
            end = audio_delay_s + raw_end
        else:
            chunk_dur = audio_duration / num_chunks
            start = audio_delay_s + i * chunk_dur
            end = audio_delay_s + (i + 1) * chunk_dur
        out = f"v{i}"
        filters.append(
            f"[{prev}][{i + 1}:v]overlay=0:0:format=auto:"
            f"enable='between(t,{start:.3f},{end:.3f})'[{out}]"
        )
        prev = out

    delay_ms = int(audio_delay_s * 1000)
    filters.append(
        f"[{audio_idx}:a]adelay={delay_ms}|{delay_ms},apad[outa]"
    )

    filter_str = ";".join(filters)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", f"[{prev}]",
        "-map", "[outa]",
        "-t", str(video_duration),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  FFmpeg stderr: {result.stderr[-800:]}")
        result.check_returncode()


# ── Per-verse pipeline ───────────────────────────────────────────────────────

def process_verse(verse, index, total, subtitles=True, output_dir=None):
    """Process a single verse: fetch data, render chunk overlays, compose video.

    output_dir overrides where the mp4 is written; it defaults to OUTPUT_DIR so
    the daily pipeline is unchanged. Plan mode passes the reel's own directory.
    """
    surah = verse["surah"]
    ayah = verse["ayah"]
    ayah_end = verse["ayah_end"]
    name = verse["name"]
    reciter = verse["reciter"]
    query = verse["scenery_query"]
    out_dir = output_dir or OUTPUT_DIR

    if ayah == ayah_end:
        ref_label = f"{surah}:{ayah}"
    else:
        ref_label = f"{surah}:{ayah}-{ayah_end}"

    log(f"\n[{index}/{total}] Generating: {name} ({ref_label}) — reciter: {reciter}")

    tmpdir = tempfile.mkdtemp(prefix="quran_video_")
    try:
        bg_path = os.path.join(tmpdir, "bg.mp4")
        audio_path = os.path.join(tmpdir, "audio.mp3")

        # 1. Fetch verse text (Arabic only)
        log("  Fetching verse text...")
        arabic, surah_name, surah_name_ar = fetch_verse_text(surah, ayah, ayah_end)
        time.sleep(API_SLEEP_S)

        # 2. Fetch audio from AlQuran Cloud (with fallback reciter)
        log(f"  Fetching recitation audio ({reciter})...")
        try:
            fetch_audio(surah, ayah, ayah_end, reciter, audio_path)
        except Exception as e:
            if reciter != FALLBACK_RECITER:
                log(f"  Audio failed with {reciter}: {e}")
                log(f"  Retrying with fallback reciter: {FALLBACK_RECITER}")
                fetch_audio(surah, ayah, ayah_end, FALLBACK_RECITER, audio_path)
            else:
                raise

        # 3. Verify audio
        audio_size = os.path.getsize(audio_path)
        log(f"  Audio file size: {audio_size} bytes")
        if audio_size == 0:
            raise RuntimeError("Audio file is empty")

        # 4. Audio duration
        audio_duration = get_audio_duration(audio_path)
        log(f"  Audio duration: {audio_duration:.1f}s")

        # 5. Fetch background video
        log("  Fetching background video from Pexels...")
        fetch_background_video(query, bg_path)
        time.sleep(API_SLEEP_S)

        if not subtitles:
            # ── No-subtitles path: background + audio only ──
            audio_delay = MIN_AUDIO_DELAY_S
            video_duration = audio_delay + audio_duration + EXTRA_DURATION_S
            log(f"  No subtitles mode — video: {video_duration:.1f}s (delay: {audio_delay:.2f}s)")

            output_filename = f"verse_{index:03d}_{surah}_{ayah}.mp4"
            output_path = os.path.join(out_dir, output_filename)
            log("  Composing video (no subtitles) with FFmpeg...")
            compose_video_no_subtitles(bg_path, audio_path, output_path, audio_duration,
                                       video_duration, audio_delay_s=audio_delay)
        else:
            # ── Subtitles path: Whisper timing + text overlays ──

            # 6. Fetch word segments from Quran.com (fallback timing reference)
            chunk_timings = None
            verse_timestamps = None

            log("  Fetching word-level segments from Quran.com...")
            _, ts = fetch_word_segments(surah, ayah, ayah_end, reciter)
            if ts:
                verse_timestamps = ts
            elif reciter not in QURANCOM_RECITER_IDS:
                time.sleep(API_SLEEP_S)
                log(f"  Fetching reference timing from {FALLBACK_RECITER}...")
                _, ref_ts = fetch_word_segments(surah, ayah, ayah_end, FALLBACK_RECITER)
                if ref_ts:
                    verse_timestamps = ref_ts
                    log("  Got reference timestamps for proportional timing")
                else:
                    log("  No timestamps available, using equal-division timing")

            # 7. Whisper transcription for exact word-level timing
            audio_delay = AUDIO_DELAY_S  # fallback
            whisper_segments, speech_onset = transcribe_word_timestamps(audio_path)
            if whisper_segments:
                audio_delay = max(0.0, MIN_AUDIO_DELAY_S + CHUNK_ANTICIPATION_S - speech_onset)
                log(f"  Dynamic audio delay: {audio_delay:.3f}s (speech onset: {speech_onset:.3f}s)")

            video_duration = audio_delay + audio_duration + EXTRA_DURATION_S
            log(f"  Video duration: {video_duration:.1f}s (delay: {audio_delay:.2f}s)")
            time.sleep(API_SLEEP_S)

            # 8. Split text into chunks and build timings
            chunks = split_into_chunks(arabic)
            num_text_words = len(arabic.split())

            if whisper_segments:
                chunk_timings = build_whisper_chunk_timings(
                    whisper_segments, num_text_words
                )
                log(f"  Rendering {len(chunks)} chunk overlays with Whisper timing...")
            elif verse_timestamps:
                chunk_timings = build_proportional_chunk_timings(
                    verse_timestamps, ayah, ayah_end, audio_duration, num_text_words
                )
                if chunk_timings:
                    log(f"  Rendering {len(chunks)} chunk overlays with proportional timing...")
                else:
                    log(f"  Rendering {len(chunks)} chunk overlays (~{WORDS_PER_CHUNK} words each)...")
            else:
                log(f"  Rendering {len(chunks)} chunk overlays (~{WORDS_PER_CHUNK} words each)...")

            chunk_paths = []
            for ci, chunk in enumerate(chunks):
                chunk_dest = os.path.join(tmpdir, f"chunk_{ci:02d}.png")
                render_chunk_overlay(chunk, surah_name, surah_name_ar, surah, ayah, ayah_end, chunk_dest)
                chunk_paths.append(chunk_dest)

            # 9. Compose final video
            output_filename = f"verse_{index:03d}_{surah}_{ayah}.mp4"
            output_path = os.path.join(out_dir, output_filename)
            log("  Composing final video with FFmpeg...")
            compose_video(bg_path, chunk_paths, audio_path, output_path, audio_duration, video_duration,
                          chunk_timings=chunk_timings, audio_delay_s=audio_delay)

        # 10. Verify audio in output
        verify_video_has_audio(output_path)

        log(f"  Done -> {output_filename}")
        return output_path

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Planned reel ─────────────────────────────────────────────────────────────

def render_plan(plan_path, subtitles=True):
    """Render a planned reel from its reel_plan.json into the plan's directory.

    Builds a verse dict from the plan, renders it via process_verse with the
    plan directory as the output directory, and writes the caption sidecars
    beside the mp4. Never reads or writes state.json.
    """
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    verse = {
        "surah": plan["surah"],
        "ayah": plan["ayah"],
        "ayah_end": plan["ayah_end"],
        "name": plan["name"],
        "reciter": plan["reciter"],
        "scenery_query": plan["scenery_query"],
    }

    plan_dir = os.path.dirname(os.path.abspath(plan_path))
    os.makedirs(plan_dir, exist_ok=True)

    if verse["ayah"] == verse["ayah_end"]:
        ref = f"{verse['surah']}:{verse['ayah']}"
    else:
        ref = f"{verse['surah']}:{verse['ayah']}-{verse['ayah_end']}"
    log(f"Planned reel: {verse['name']} ({ref}) -> {plan_dir}")

    output_path = process_verse(verse, 1, 1, subtitles=subtitles, output_dir=plan_dir)

    from captions import build_caption, build_youtube_title, build_youtube_description
    sidecars = {
        "caption.txt": build_caption(verse),
        "youtube_title.txt": build_youtube_title(verse),
        "youtube_description.txt": build_youtube_description(verse),
    }
    for filename, content in sidecars.items():
        with open(os.path.join(plan_dir, filename), "w", encoding="utf-8") as f:
            f.write(content + "\n")
    log(f"  Wrote caption sidecars: {', '.join(sidecars)}")
    log(f"  Reel: {output_path}")
    save_log()
    return output_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Quran verse videos")
    parser.add_argument("--test", action="store_true", help="Generate only the first verse")
    parser.add_argument("--verse", type=int, help="Generate only verse N (1-indexed)")
    parser.add_argument("--no-subtitles", action="store_true",
                        help="Generate video with background + audio only (no text overlays)")
    parser.add_argument("--plan", metavar="PATH",
                        help="Render a planned reel from its reel_plan.json (never touches state.json)")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found on PATH.")
        sys.exit(1)
    if not shutil.which("ffprobe"):
        print("ERROR: ffprobe not found on PATH.")
        sys.exit(1)
    if not os.environ.get("PEXELS_API_KEY"):
        print("ERROR: PEXELS_API_KEY environment variable is not set.")
        print("Get a free API key at https://www.pexels.com/api/")
        sys.exit(1)
    if not args.no_subtitles:
        for font_path in (ARABIC_FONT_PATH, ENGLISH_FONT_PATH):
            if not os.path.isfile(font_path):
                print(f"ERROR: Font not found: {font_path}")
                sys.exit(1)

    if args.plan:
        try:
            render_plan(args.plan, subtitles=not args.no_subtitles)
        except Exception as e:
            log(f"ERROR: {e}")
            save_log()
            sys.exit(1)
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_verses = load_verses()
    total_all = len(all_verses)
    log(f"Loaded {total_all} verses from {VERSES_FILE}")

    state = load_state()
    use_subtitles = not args.no_subtitles
    update_state = False

    if args.test:
        to_generate = [(0, all_verses[0])]
        log("--test mode: generating only the first verse")
    elif args.verse is not None:
        if args.verse < 1 or args.verse > total_all:
            print(f"ERROR: --verse must be between 1 and {total_all}")
            sys.exit(1)
        idx = args.verse - 1
        to_generate = [(idx, all_verses[idx])]
        log(f"--verse mode: generating only verse {args.verse}")
    else:
        start_idx = state["next_index"] % total_all
        to_generate = []
        for offset in range(total_all):
            idx = (start_idx + offset) % total_all
            to_generate.append((idx, all_verses[idx]))
        update_state = True
        log(f"Resuming from verse {start_idx + 1} (state.json next_index={start_idx})")

    total = len(to_generate)
    successes = 0
    failures = []

    for count, (idx, verse) in enumerate(to_generate, start=1):
        try:
            if process_verse(verse, count, total, subtitles=use_subtitles):
                successes += 1
                if update_state:
                    state["next_index"] = (idx + 1) % total_all
                    save_state(state)
        except Exception as e:
            name = verse.get("name", f"{verse['surah']}:{verse['ayah']}")
            log(f"  ERROR processing {name}: {e}")
            failures.append(name)

    log("\n" + "=" * 60)
    log(f"COMPLETE: {successes}/{total} videos generated successfully")
    if failures:
        log(f"FAILED ({len(failures)}):")
        for name in failures:
            log(f"  - {name}")
    log(f"Output directory: {OUTPUT_DIR}")

    save_log()


if __name__ == "__main__":
    main()
