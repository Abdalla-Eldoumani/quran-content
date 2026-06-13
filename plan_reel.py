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
import datetime
import io
import json
import os
import re
import sys
import time

# Fix Windows console encoding for non-ASCII output (passage titles, markers).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

import theme_lib
from generate_videos import (
    ALQURAN_API_BASE,
    API_SLEEP_S,
    AUDIO_DELAY_S,
    EXTRA_DURATION_S,
    get_audio_duration,
)
from generate_verses_json import SCENERY_QUERIES

# ── Constants ────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache", "audio")
REELS_DIR = os.path.join(SCRIPT_DIR, "output", "reels")
DEFAULT_RECITER = "ar.minshawi"
DEFAULT_MAX_SECONDS = 59
LEAD_IN_OUTRO_S = AUDIO_DELAY_S + EXTRA_DURATION_S  # lead-in (1.5) + outro (3.0)


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


# ── Budget gate ──────────────────────────────────────────────────────────────

def audio_budget(max_seconds):
    """Maximum recitation seconds that still fit under max_seconds."""
    return max_seconds - LEAD_IN_OUTRO_S


def evaluate_candidate(passage, reciter, max_seconds):
    """Measure a candidate and classify it against the budget.

    Returns a dict: total (float or None), durations (list or None),
    over_budget (bool), no_audio (bool), verified (bool).
    """
    result = {"total": None, "durations": None, "over_budget": False,
              "no_audio": False, "verified": passage["verified"]}
    try:
        durations, total = measure_passage(
            passage["surah"], passage["ayah"], passage["ayah_end"], reciter)
    except Exception:
        result["no_audio"] = True
        return result
    result["durations"] = durations
    result["total"] = total
    result["over_budget"] = total > audio_budget(max_seconds)
    return result


# ── Candidate table ──────────────────────────────────────────────────────────

def print_candidates(candidates, reciter, max_seconds):
    """Measure each candidate and print a numbered table with budget status.

    Returns the per-candidate evaluation dicts, aligned with the input order.
    """
    if not candidates:
        print("No matching passages.")
        return []
    print(f"Reciter: {reciter}  |  audio budget: {audio_budget(max_seconds):.1f}s "
          f"(max video {max_seconds:.0f}s)")
    print(f"{'#':>2}  {'passage':<34}  {'theme':<22}  {'ref':<9}  {'audio':>7}  status")
    print("-" * 92)
    evaluations = []
    for i, (theme, passage) in enumerate(candidates, start=1):
        ev = evaluate_candidate(passage, reciter, max_seconds)
        evaluations.append(ev)
        if ev["no_audio"]:
            audio_col, flags = "--", ["NO AUDIO"]
        else:
            audio_col = f"{ev['total']:.1f}s"
            flags = ["verified" if ev["verified"] else "UNVERIFIED"]
            if ev["over_budget"]:
                flags.append("OVER BUDGET")
        print(f"{i:>2}  {passage['name'][:34]:<34}  {theme['slug'][:22]:<22}  "
              f"{passage_ref(passage):<9}  {audio_col:>7}  {', '.join(flags)}")
    return evaluations


# ── Pick and write plan ──────────────────────────────────────────────────────

def _slugify(name):
    """Lowercase, hyphenate a passage name for use in a directory slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "passage"


def choose_scenery(passage, override):
    """Return the scenery query: the override if given, else a rotation by reference."""
    if override:
        return override
    idx = (passage["surah"] + passage["ayah"] + passage["ayah_end"]) % len(SCENERY_QUERIES)
    return SCENERY_QUERIES[idx]


def do_pick(candidates, index, reciter, max_seconds, translation, scenery):
    """Write reel_plan.json for candidate `index`, or refuse with a named reason."""
    if index < 1 or index > len(candidates):
        print(f"ERROR: --pick {index} is out of range (1..{len(candidates)}).")
        sys.exit(1)
    theme, passage = candidates[index - 1]
    ev = evaluate_candidate(passage, reciter, max_seconds)

    reasons = []
    if not passage["verified"]:
        reasons.append("passage is UNVERIFIED; confirm the standalone reading and set "
                       "verified to true in themes.json first")
    if ev["no_audio"]:
        reasons.append(f"no audio available for reciter {reciter}")
    elif ev["over_budget"]:
        reasons.append(f"OVER BUDGET: audio {ev['total']:.1f}s exceeds the "
                       f"{audio_budget(max_seconds):.1f}s budget for a {max_seconds:.0f}s video "
                       "(choose a shorter passage or a faster reciter)")
    if reasons:
        print(f"ERROR: cannot pick '{passage['name']}' ({passage_ref(passage)}):")
        for reason in reasons:
            print(f"  - {reason}")
        sys.exit(1)

    plan = {
        "surah": passage["surah"],
        "ayah": passage["ayah"],
        "ayah_end": passage["ayah_end"],
        "name": passage["name"],
        "theme": theme["slug"],
        "reciter": reciter,
        "scenery_query": choose_scenery(passage, scenery),
        "translation": translation,
        "per_ayah_durations": [round(d, 3) for d in ev["durations"]],
        "audio_total_s": round(ev["total"], 3),
        "budget_s": max_seconds,
        "created": datetime.date.today().isoformat(),
    }
    out_dir = os.path.join(
        REELS_DIR,
        f"{passage['surah']}_{passage['ayah']}_{passage['ayah_end']}_{_slugify(passage['name'])}",
    )
    os.makedirs(out_dir, exist_ok=True)
    plan_path = os.path.join(out_dir, "reel_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    print(f"Wrote {plan_path}")
    print(f"  Passage: {passage['name']} ({passage_ref(passage)}), reciter {reciter}, "
          f"audio {ev['total']:.1f}s, translation {'on' if translation else 'off'}")
    if passage["ayah"] == 1:
        print("  Note: passage starts at ayah 1; the recitation may include the basmala, "
              "so the first ayah's translation can appear during it.")
    print(f"  Render with: python3 generate_videos.py --plan {plan_path}")


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

    if not re.match(r"^[A-Za-z0-9._-]+$", args.reciter):
        print("ERROR: --reciter must be an edition id such as ar.minshawi "
              "(letters, digits, dot, dash, underscore only).")
        sys.exit(1)

    if not (args.theme or args.topic or args.list_unverified):
        print("ERROR: choose one of --theme, --topic, or --list-unverified.")
        sys.exit(1)

    themes = theme_lib.load_themes()
    try:
        candidates = resolve_candidates(
            themes, theme_slug=args.theme, topic=args.topic,
            list_unverified=args.list_unverified,
        )
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not candidates:
        print("No matching passages.")
        sys.exit(0)

    if args.pick is not None:
        do_pick(candidates, args.pick, args.reciter, args.max_seconds,
                args.translation, args.scenery)
    else:
        print_candidates(candidates, args.reciter, args.max_seconds)


if __name__ == "__main__":
    main()
