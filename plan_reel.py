#!/usr/bin/env python3
"""Plan a themed Quran reel.

Matches a theme slug or a free-text topic to candidate passages from the
hand-verified theme index, lists them with their reference and verified status,
and (once measured) writes a reel_plan.json the renderer consumes.

Plan mode never reads or writes state.json. All recitation audio, text, and
translation come from the verified APIs at runtime; this module holds no
religious text.
"""

import argparse
import io
import os
import sys
import time

# Fix Windows console encoding for non-ASCII output (passage titles, markers).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

import theme_lib
from generate_videos import ALQURAN_API_BASE, API_SLEEP_S, get_audio_duration

# ── Constants ────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache", "audio")
DEFAULT_RECITER = "ar.minshawi"
DEFAULT_MAX_SECONDS = 59


# ── Candidate resolution ─────────────────────────────────────────────────────

def passage_ref(passage):
    """Format a passage's surah:ayah[-ayah_end] reference."""
    surah, ayah, ayah_end = passage["surah"], passage["ayah"], passage["ayah_end"]
    return f"{surah}:{ayah}" if ayah == ayah_end else f"{surah}:{ayah}-{ayah_end}"


def resolve_candidates(themes, theme_slug=None, topic=None, list_unverified=False):
    """Return a list of (theme, passage) candidates for the chosen selector.

    Exactly one selector is expected: a theme slug, a free-text topic, or the
    list-unverified flag.
    """
    if list_unverified:
        return [
            (theme, passage)
            for theme in themes
            for passage in theme["passages"]
            if not passage["verified"]
        ]
    if theme_slug:
        for theme in themes:
            if theme["slug"] == theme_slug:
                return [(theme, passage) for passage in theme["passages"]]
        raise ValueError(f"no theme with slug '{theme_slug}'")
    if topic:
        return theme_lib.search(themes, topic)
    return []


# ── Audio measurement ────────────────────────────────────────────────────────

def audio_cache_path(reciter, surah, ayah):
    """Local cache path for one ayah's recitation mp3."""
    return os.path.join(CACHE_DIR, reciter, f"{surah}_{ayah}.mp3")


def _download_ayah_audio(surah, ayah, reciter, dest):
    """Download one ayah's mp3 from AlQuran Cloud to dest (same endpoints as the renderer)."""
    meta_url = f"{ALQURAN_API_BASE}/ayah/{surah}:{ayah}/{reciter}"
    resp = requests.get(meta_url, timeout=30)
    resp.raise_for_status()
    audio_url = resp.json()["data"].get("audio")
    if not audio_url:
        raise RuntimeError(f"no audio available for {surah}:{ayah} under {reciter}")
    audio_resp = requests.get(audio_url, timeout=60)
    audio_resp.raise_for_status()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(audio_resp.content)
    if os.path.getsize(dest) == 0:
        os.remove(dest)
        raise RuntimeError(f"downloaded audio for {surah}:{ayah} is empty")


def measure_passage(surah, ayah, ayah_end, reciter):
    """Measure per-ayah recitation durations for a passage, caching mp3s on disk.

    Returns (per_ayah_durations, total_seconds). Each ayah's mp3 is downloaded
    once into cache/audio/<reciter>/<surah>_<ayah>.mp3 and reused on later runs;
    only cache misses hit the network, paced by API_SLEEP_S. Raises RuntimeError
    if any ayah's audio is missing or empty (the caller treats this as NO AUDIO).
    """
    durations = []
    for ayah_num in range(ayah, ayah_end + 1):
        cache_path = audio_cache_path(reciter, surah, ayah_num)
        if not (os.path.exists(cache_path) and os.path.getsize(cache_path) > 0):
            _download_ayah_audio(surah, ayah_num, reciter, cache_path)
            time.sleep(API_SLEEP_S)
        durations.append(get_audio_duration(cache_path))
    return durations, sum(durations)


# ── Candidate table ──────────────────────────────────────────────────────────

def print_candidates(candidates):
    """Print a numbered table of candidates: name, theme, reference, status."""
    if not candidates:
        print("No matching passages.")
        return
    print(f"{'#':>2}  {'passage':<40}  {'theme':<26}  {'ref':<10}  status")
    print("-" * 96)
    for i, (theme, passage) in enumerate(candidates, start=1):
        status = "verified" if passage["verified"] else "UNVERIFIED"
        print(f"{i:>2}  {passage['name'][:40]:<40}  {theme['slug'][:26]:<26}  "
              f"{passage_ref(passage):<10}  {status}")


# ── Main ─────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(description="Plan a themed Quran reel")
    parser.add_argument("--theme", help="theme slug to list passages for")
    parser.add_argument("--topic", help="free-text topic to match against keywords and names")
    parser.add_argument("--reciter", default=DEFAULT_RECITER, help="reciter id (default ar.minshawi)")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS,
                        help="maximum total video length in seconds (default 59)")
    parser.add_argument("--translation", action=argparse.BooleanOptionalAction, default=True,
                        help="render the English translation overlay (default on)")
    parser.add_argument("--scenery", help="override the background scenery query")
    parser.add_argument("--pick", type=int, metavar="N", help="write a reel plan for candidate N")
    parser.add_argument("--list-unverified", action="store_true",
                        help="list every unverified passage across all themes")
    return parser


def main():
    args = build_parser().parse_args()

    if not (args.theme or args.topic or args.list_unverified):
        print("ERROR: choose one of --theme, --topic, or --list-unverified.")
        sys.exit(1)

    themes = theme_lib.load_themes()
    candidates = resolve_candidates(
        themes, theme_slug=args.theme, topic=args.topic,
        list_unverified=args.list_unverified,
    )
    print_candidates(candidates)


if __name__ == "__main__":
    main()
