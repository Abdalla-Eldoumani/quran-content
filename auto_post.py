#!/usr/bin/env python3
"""
Automated daily Quran video posting pipeline.

Generates one video per day using generate_videos.py and posts it to
Instagram (Reel), Facebook (Page video), and YouTube (Short).

Usage:
  python3 auto_post.py                    # Full pipeline: generate + post
  python3 auto_post.py --generate-only    # Generate video only
  python3 auto_post.py --post-only        # Post last generated video
  python3 auto_post.py --dry-run          # Simulate everything
  python3 auto_post.py --platform meta    # Post to Meta (IG+FB) only
  python3 auto_post.py --platform youtube # Post to YouTube only
"""

import argparse
import datetime
import json
import logging
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from generate_videos import OUTPUT_DIR, load_verses, process_verse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "state.json")
STATE_TMP = STATE_FILE + ".tmp"
LOG_FILE = os.path.join(OUTPUT_DIR, "auto_post.log")
GRAPH_API = "https://graph.facebook.com/v21.0"

RECITER_NAMES = {
    "ar.alafasy": "Mishary Rashid al-Afasy",
    "ar.husary": "Mahmoud Khaleel al-Husary",
    "ar.minshawi": "Muhammad Siddiq al-Minshawi",
    "ar.muhammadayyoub": "Muhammad Ayyub",
    "ar.abdurrahmaansudais": "Abdul Rahman As-Sudais",
}

logger = logging.getLogger("auto_post")


def setup_logging():
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"next_index": 0, "history": []}


def save_state(state):
    with open(STATE_TMP, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(STATE_TMP, STATE_FILE)


def _verse_ref(verse):
    s, a, e = verse["surah"], verse["ayah"], verse["ayah_end"]
    return f"{s}:{a}" if a == e else f"{s}:{a}-{e}"


def build_caption(verse):
    ref = _verse_ref(verse)
    reciter = RECITER_NAMES.get(verse["reciter"], verse["reciter"])
    return (
        f"{verse['name']} | {ref}\n\n"
        f"Recited by Sheikh {reciter}\n\n"
        f"May Allah grant us understanding of His words.\n\n"
        f"#Quran #QuranRecitation #Islam #Muslim #DailyQuran "
        f"#IslamicReminder #QuranVerses #Dawah #SadaqahJariyah"
    )


def build_youtube_title(verse):
    return f"{verse['name']} | {_verse_ref(verse)} | Quran Recitation #Shorts"


def build_youtube_description(verse):
    ref = _verse_ref(verse)
    reciter = RECITER_NAMES.get(verse["reciter"], verse["reciter"])
    return f"{verse['name']} | {ref}\n\nRecited by Sheikh {reciter}\n\nMay Allah grant us understanding of His words."


def upload_to_temp_host(video_path):
    """Upload video to a public URL for Meta API. Returns URL or None."""
    import requests
    # Try 0x0.st first
    try:
        logger.info("Uploading to 0x0.st...")
        with open(video_path, "rb") as f:
            resp = requests.post("https://0x0.st", files={"file": f}, timeout=120)
        if resp.status_code == 200:
            url = resp.text.strip()
            logger.info(f"  Uploaded: {url}")
            return url
        logger.warning(f"  0x0.st returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"  0x0.st failed: {e}")
    # Fallback to file.io
    try:
        logger.info("Trying file.io as fallback...")
        with open(video_path, "rb") as f:
            resp = requests.post("https://file.io", files={"file": f}, timeout=120)
        if resp.status_code == 200:
            url = resp.json()["link"]
            logger.info(f"  Uploaded: {url}")
            return url
        logger.warning(f"  file.io returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"  file.io failed: {e}")
    return None


def post_to_instagram(video_url, caption, dry_run=False):
    """Post a Reel to Instagram via Meta Graph API."""
    import requests
    token = os.environ.get("META_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    if not token or not ig_user_id:
        logger.error("Instagram: META_ACCESS_TOKEN or IG_USER_ID not set")
        return False
    if dry_run:
        logger.info("Instagram: DRY RUN — would create Reel container")
        return True
    # Check token validity
    if requests.get(f"{GRAPH_API}/me", params={"access_token": token}, timeout=10).status_code != 200:
        logger.error("Instagram: Token invalid. Re-run setup_meta.py")
        return False
    # Create media container
    logger.info("Instagram: Creating Reel container...")
    resp = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media",
        data={"media_type": "REELS", "video_url": video_url,
              "caption": caption, "access_token": token},
        timeout=30,
    )
    if resp.status_code != 200:
        logger.error(f"Instagram: Container creation failed: {resp.text}")
        return False
    container_id = resp.json()["id"]
    logger.info(f"  Container ID: {container_id}")
    # Poll for readiness (up to 5 minutes)
    for _ in range(30):
        time.sleep(10)
        resp = requests.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code", "access_token": token}, timeout=10,
        )
        status = resp.json().get("status_code", "")
        logger.info(f"  Container status: {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            logger.error(f"Instagram: Container error: {resp.text}")
            return False
    else:
        logger.error("Instagram: Container timed out after 5 minutes")
        return False
    # Publish
    logger.info("Instagram: Publishing Reel...")
    resp = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token}, timeout=30,
    )
    if resp.status_code != 200:
        logger.error(f"Instagram: Publish failed: {resp.text}")
        return False
    logger.info(f"Instagram: Published (ID: {resp.json().get('id', '?')})")
    return True


def post_to_facebook(video_path, caption, dry_run=False):
    """Post a video to Facebook Page."""
    import requests
    token = os.environ.get("META_ACCESS_TOKEN", "")
    page_id = os.environ.get("FB_PAGE_ID", "")
    if not token or not page_id:
        logger.error("Facebook: META_ACCESS_TOKEN or FB_PAGE_ID not set")
        return False
    if dry_run:
        logger.info("Facebook: DRY RUN — would upload video to Page")
        return True
    logger.info("Facebook: Uploading video to Page...")
    with open(video_path, "rb") as f:
        resp = requests.post(
            f"{GRAPH_API}/{page_id}/videos", files={"file": f},
            data={"description": caption, "access_token": token}, timeout=300,
        )
    if resp.status_code != 200:
        logger.error(f"Facebook: Upload failed: {resp.text}")
        return False
    logger.info(f"Facebook: Posted (ID: {resp.json().get('id', '?')})")
    return True


def post_to_youtube(video_path, title, description, dry_run=False):
    """Upload a Short to YouTube via Data API v3."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
    if not all([client_id, client_secret, refresh_token]):
        logger.error("YouTube: Missing YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, or YOUTUBE_REFRESH_TOKEN")
        return False
    if dry_run:
        logger.info("YouTube: DRY RUN — would upload Short")
        return True
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.error("YouTube: Missing google-api-python-client or google-auth")
        return False
    logger.info("YouTube: Uploading Short...")
    creds = Credentials(
        token=None, refresh_token=refresh_token,
        client_id=client_id, client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title, "description": description,
                "tags": ["Quran", "Islam", "Recitation", "Shorts"],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        },
        media_body=MediaFileUpload(video_path, mimetype="video/mp4", resumable=True),
    )
    response = request.execute()
    video_id = response.get("id", "?")
    logger.info(f"YouTube: Uploaded (ID: {video_id}, https://youtu.be/{video_id})")
    return True


def find_last_video():
    """Find the most recently generated video in OUTPUT_DIR."""
    if not os.path.isdir(OUTPUT_DIR):
        return None
    mp4s = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4")]
    if not mp4s:
        return None
    mp4s.sort(key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)), reverse=True)
    return os.path.join(OUTPUT_DIR, mp4s[0])


def main():
    parser = argparse.ArgumentParser(description="Automated Quran video posting pipeline")
    parser.add_argument("--generate-only", action="store_true", help="Generate video only, don't post")
    parser.add_argument("--post-only", action="store_true", help="Post last generated video")
    parser.add_argument("--dry-run", action="store_true", help="Simulate everything")
    parser.add_argument("--platform", choices=["meta", "youtube"], help="Target specific platform")
    args = parser.parse_args()

    setup_logging()
    logger.info("=" * 60)
    logger.info("Quran Auto-Post Pipeline")
    logger.info("=" * 60)

    state = load_state()
    verses = load_verses()
    total = len(verses)
    index = state["next_index"] % total
    verse = verses[index]
    logger.info(f"Verse {index + 1}/{total}: {verse['name']} ({_verse_ref(verse)})")
    logger.info(f"Reciter: {verse['reciter']}")

    # Generate or locate video
    video_path = None
    if args.post_only:
        video_path = find_last_video()
        if not video_path:
            logger.error("No video found in output/. Run without --post-only first.")
            sys.exit(2)
        logger.info(f"Using existing video: {video_path}")
    elif args.dry_run:
        logger.info("DRY RUN: Skipping video generation")
        video_path = find_last_video()
    else:
        logger.info("Generating video...")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            result = process_verse(verse, index + 1, total)
            if result:
                video_path = result
                logger.info(f"Video generated: {video_path}")
            else:
                logger.error("Video generation returned no path")
                sys.exit(2)
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            sys.exit(2)

    if args.generate_only:
        logger.info("--generate-only: Skipping posting")
        state["next_index"] = (index + 1) % total
        save_state(state)
        logger.info(f"State updated: next_index={state['next_index']}")
        sys.exit(0)

    # Build captions
    caption = build_caption(verse)
    yt_title = build_youtube_title(verse)
    yt_desc = build_youtube_description(verse)
    logger.info(f"Caption:\n{caption}")

    # Post to platforms
    results = {}
    post_meta = args.platform is None or args.platform == "meta"
    post_youtube = args.platform is None or args.platform == "youtube"

    # Upload to temp host for Instagram (needs public URL)
    video_url = None
    if post_meta and video_path and not args.dry_run:
        video_url = upload_to_temp_host(video_path)
        if not video_url:
            logger.warning("Could not upload to temp host — Instagram posting will fail")

    if post_meta:
        try:
            if args.dry_run or video_url:
                results["instagram"] = post_to_instagram(
                    video_url or "https://example.com/dry-run.mp4", caption, dry_run=args.dry_run)
            else:
                logger.error("Instagram: No public video URL available")
                results["instagram"] = False
        except Exception as e:
            logger.error(f"Instagram: {e}")
            results["instagram"] = False

    if post_meta and video_path:
        try:
            results["facebook"] = post_to_facebook(video_path, caption, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"Facebook: {e}")
            results["facebook"] = False

    if post_youtube and video_path:
        try:
            results["youtube"] = post_to_youtube(video_path, yt_title, yt_desc, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"YouTube: {e}")
            results["youtube"] = False

    # Update state
    state["history"].append({
        "index": index,
        "date": datetime.date.today().isoformat(),
        "platforms": results,
        "error": None,
    })
    state["history"] = state["history"][-100:]
    state["next_index"] = (index + 1) % total
    save_state(state)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    summary = ", ".join(f"{p}: {'OK' if s else 'FAILED'}" for p, s in results.items())
    logger.info(f"Results: {summary}")
    logger.info(f"State updated: next_index={state['next_index']}")

    if args.dry_run:
        logger.info("DRY RUN complete.")
        sys.exit(0)
    elif not results:
        logger.info("No platforms were targeted.")
        sys.exit(0)
    elif any(results.values()):
        sys.exit(0)
    else:
        logger.error("All platforms failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
