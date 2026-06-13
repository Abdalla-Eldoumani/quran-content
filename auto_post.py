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
from captions import build_caption, build_youtube_title, build_youtube_description, _verse_ref

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "state.json")
STATE_TMP = STATE_FILE + ".tmp"
LOG_FILE = os.path.join(OUTPUT_DIR, "auto_post.log")
GRAPH_API_VERSION = "v25.0"
GRAPH_API = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

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
            state = json.load(f)
        # Ensure next_post_index exists (backward compat)
        if "next_post_index" not in state:
            state["next_post_index"] = state.get("next_index", 0)
        return state
    return {"next_index": 0, "next_post_index": 0, "history": []}


def save_state(state):
    with open(STATE_TMP, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(STATE_TMP, STATE_FILE)


def post_to_instagram(video_path, caption, dry_run=False):
    """Post a Reel to Instagram via the Meta resumable upload flow.

    Creates a REELS container with upload_type=resumable, uploads the file bytes
    to the rupload.facebook.com uri the container returns, then polls and
    publishes. The access token is sent only in request data/headers and is
    never logged; error responses are truncated in case they echo context.
    """
    import requests
    token = os.environ.get("META_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    if not token or not ig_user_id:
        logger.error("Instagram: META_ACCESS_TOKEN or IG_USER_ID not set")
        return False
    if dry_run:
        logger.info("Instagram: DRY RUN - would create a resumable REELS container, "
                    "upload the file to rupload.facebook.com, poll status, and publish")
        return True
    # Fail fast with a clear message on an expired or invalid token.
    if requests.get(f"{GRAPH_API}/me", params={"access_token": token}, timeout=10).status_code != 200:
        logger.error("Instagram: token invalid or expired (Graph code 190). Re-run setup_meta.py")
        return False
    # 1. Create a resumable Reel container.
    logger.info("Instagram: creating resumable Reel container...")
    resp = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media",
        data={"media_type": "REELS", "upload_type": "resumable",
              "caption": caption, "access_token": token},
        timeout=30,
    )
    if resp.status_code != 200:
        logger.error(f"Instagram: container creation failed ({resp.status_code}): {resp.text[:300]}")
        return False
    container = resp.json()
    container_id = container.get("id")
    upload_uri = container.get("uri")
    if not container_id or not upload_uri:
        logger.error(f"Instagram: missing container id or upload uri: {resp.text[:300]}")
        return False
    logger.info(f"  Container ID: {container_id}")
    # 2. Upload the file bytes to the resumable endpoint.
    file_size = os.path.getsize(video_path)
    logger.info(f"Instagram: uploading {file_size} bytes to the resumable endpoint...")
    with open(video_path, "rb") as f:
        up = requests.post(
            upload_uri,
            headers={"Authorization": f"OAuth {token}",
                     "offset": "0", "file_size": str(file_size)},
            data=f.read(), timeout=300,
        )
    if up.status_code != 200:
        logger.error(f"Instagram: file upload failed ({up.status_code}): {up.text[:300]}")
        return False
    # 3. Poll for readiness (hard cap of 30 polls).
    for _ in range(30):
        time.sleep(10)
        poll = requests.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code", "access_token": token}, timeout=10,
        )
        status = poll.json().get("status_code", "")
        logger.info(f"  Container status: {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            logger.error(f"Instagram: container {container_id} error: {poll.text[:300]}")
            return False
    else:
        logger.error(f"Instagram: container {container_id} not FINISHED after 30 polls; retry later")
        return False
    # 4. Publish.
    logger.info("Instagram: publishing Reel...")
    pub = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token}, timeout=30,
    )
    if pub.status_code != 200:
        logger.error(f"Instagram: publish failed ({pub.status_code}): {pub.text[:300]}")
        return False
    logger.info(f"Instagram: published (ID: {pub.json().get('id', '?')})")
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
        logger.error(f"Facebook: upload failed ({resp.status_code}): {resp.text[:300]}")
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


def find_unposted_videos(state):
    """Find all videos in OUTPUT_DIR that haven't been successfully posted, sorted by name."""
    if not os.path.isdir(OUTPUT_DIR):
        return []
    posted_files = {
        h.get("video") for h in state.get("history", [])
        if h.get("video") and any(h.get("platforms", {}).values())
    }
    mp4s = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4") and f not in posted_files]
    mp4s.sort()
    return [os.path.join(OUTPUT_DIR, f) for f in mp4s]


def post_one_video(video_path, verse, state, total, platform=None, dry_run=False,
                    advance_post_only=False):
    """Post a single video to platforms. Updates state and saves it.

    Returns True if at least one platform succeeded.
    """
    index = verse["_index"]  # 0-based index set by caller

    caption = build_caption(verse)
    yt_title = build_youtube_title(verse)
    yt_desc = build_youtube_description(verse)
    logger.info(f"Caption:\n{caption}")

    results = {}
    post_meta = platform is None or platform == "meta"
    post_youtube = platform is None or platform == "youtube"

    if post_meta:
        try:
            results["instagram"] = post_to_instagram(video_path, caption, dry_run=dry_run)
        except Exception as e:
            logger.error(f"Instagram: {e}")
            results["instagram"] = False

    if post_meta:
        try:
            results["facebook"] = post_to_facebook(video_path, caption, dry_run=dry_run)
        except Exception as e:
            logger.error(f"Facebook: {e}")
            results["facebook"] = False

    if post_youtube:
        try:
            results["youtube"] = post_to_youtube(video_path, yt_title, yt_desc, dry_run=dry_run)
        except Exception as e:
            logger.error(f"YouTube: {e}")
            results["youtube"] = False

    # Update state
    any_succeeded = any(results.values())
    state["history"].append({
        "index": index,
        "date": datetime.date.today().isoformat(),
        "video": os.path.basename(video_path),
        "platforms": results,
        "error": None,
    })
    state["history"] = state["history"][-100:]
    if any_succeeded:
        if advance_post_only:
            state["next_post_index"] = (index + 1) % total
        else:
            state["next_index"] = (index + 1) % total
            state["next_post_index"] = state["next_index"]
    save_state(state)

    # Summary
    summary = ", ".join(f"{p}: {'OK' if s else 'FAILED'}" for p, s in results.items())
    logger.info(f"Results: {summary}")
    return any_succeeded


def run_direct(args):
    """Post one specific file through the platform functions, touching no state.

    Caption, title, and description come from the flags, falling back to the
    sidecars beside the video (caption.txt, youtube_title.txt,
    youtube_description.txt). state.json is never read or written.
    """
    video_path = args.video
    if not os.path.isfile(video_path):
        logger.error(f"Video not found: {video_path}")
        sys.exit(2)
    reel_dir = os.path.dirname(os.path.abspath(video_path))

    def read_sidecar(name):
        path = os.path.join(reel_dir, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return None

    if args.caption_file:
        if not os.path.isfile(args.caption_file):
            logger.error(f"Caption file not found: {args.caption_file}")
            sys.exit(2)
        with open(args.caption_file, "r", encoding="utf-8") as f:
            caption = f.read().strip()
    else:
        caption = read_sidecar("caption.txt")
    if not caption:
        logger.error("No caption: pass --caption-file or place caption.txt beside the video")
        sys.exit(2)

    title = args.title or read_sidecar("youtube_title.txt") or caption.splitlines()[0]
    description = read_sidecar("youtube_description.txt") or caption

    post_meta = args.platform is None or args.platform == "meta"
    post_youtube = args.platform is None or args.platform == "youtube"

    logger.info(f"Direct post: {os.path.basename(video_path)} (no state.json changes)")
    logger.info(f"Caption:\n{caption}")

    results = {}
    if post_meta:
        try:
            results["instagram"] = post_to_instagram(video_path, caption, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"Instagram: {e}")
            results["instagram"] = False
        try:
            results["facebook"] = post_to_facebook(video_path, caption, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"Facebook: {e}")
            results["facebook"] = False
    if post_youtube:
        try:
            results["youtube"] = post_to_youtube(video_path, title, description, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"YouTube: {e}")
            results["youtube"] = False

    summary = ", ".join(f"{p}: {'OK' if s else 'FAILED'}" for p, s in results.items())
    logger.info(f"Results: {summary}")
    if args.dry_run:
        logger.info("DRY RUN complete.")
    sys.exit(0 if any(results.values()) or args.dry_run else 1)


def main():
    parser = argparse.ArgumentParser(description="Automated Quran video posting pipeline")
    parser.add_argument("--generate-only", action="store_true", help="Generate video only, don't post")
    parser.add_argument("--post-only", action="store_true", help="Post last generated video")
    parser.add_argument("--post-all", action="store_true", help="Post all unposted videos in output/")
    parser.add_argument("--dry-run", action="store_true", help="Simulate everything")
    parser.add_argument("--platform", choices=["meta", "youtube"], help="Target specific platform")
    parser.add_argument("--video", help="Post a specific mp4 directly, with no state.json changes")
    parser.add_argument("--caption-file", help="Caption file for --video (defaults to caption.txt beside the video)")
    parser.add_argument("--title", help="YouTube title for --video (defaults to youtube_title.txt or the caption's first line)")
    args = parser.parse_args()

    setup_logging()
    logger.info("=" * 60)
    logger.info("Quran Auto-Post Pipeline")
    logger.info("=" * 60)

    # ── Direct mode: post one specific file, no state.json access ──
    if args.video:
        run_direct(args)

    state = load_state()
    verses = load_verses()
    total = len(verses)

    # ── Post-all mode: post every unposted video in output/ ──
    if args.post_all:
        unposted = find_unposted_videos(state)
        if not unposted:
            logger.info("No unposted videos found in output/.")
            sys.exit(0)
        logger.info(f"Found {len(unposted)} unposted video(s)")

        successes = 0
        failures = 0
        for i, video_path in enumerate(unposted, start=1):
            post_index = state["next_post_index"] % total
            verse = verses[post_index]
            verse["_index"] = post_index
            logger.info("")
            logger.info(f"[{i}/{len(unposted)}] Posting: {verse['name']} ({_verse_ref(verse)})")
            logger.info(f"  Video: {os.path.basename(video_path)}")

            if post_one_video(video_path, verse, state, total,
                              platform=args.platform, dry_run=args.dry_run,
                              advance_post_only=True):
                successes += 1
            else:
                failures += 1

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"Posted {successes}/{len(unposted)} videos ({failures} failed)")
        sys.exit(0 if successes > 0 else 1)

    # ── Post-only mode: post the latest unposted video ──
    if args.post_only:
        post_index = state["next_post_index"] % total
        verse = verses[post_index]
        verse["_index"] = post_index
        logger.info(f"Post verse {post_index + 1}/{total}: {verse['name']} ({_verse_ref(verse)})")
        logger.info(f"Reciter: {verse['reciter']}")

        video_path = find_last_video()
        if not video_path:
            logger.error("No video found in output/. Run without --post-only first.")
            sys.exit(2)
        video_filename = os.path.basename(video_path)
        posted_files = {
            h.get("video") for h in state.get("history", [])
            if h.get("video") and any(h.get("platforms", {}).values())
        }
        if video_filename in posted_files:
            logger.error(f"Video already posted: {video_filename}. Generate a new one first.")
            sys.exit(0)
        logger.info(f"Using existing video: {video_path}")

        ok = post_one_video(video_path, verse, state, total,
                            platform=args.platform, dry_run=args.dry_run,
                            advance_post_only=True)
        if args.dry_run:
            logger.info("DRY RUN complete.")
        sys.exit(0 if ok or args.dry_run else 1)

    # ── Generate (and optionally post) mode ──
    index = state["next_index"] % total
    verse = verses[index]
    verse["_index"] = index
    logger.info(f"Verse {index + 1}/{total}: {verse['name']} ({_verse_ref(verse)})")
    logger.info(f"Reciter: {verse['reciter']}")

    video_path = None
    if args.dry_run:
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

    ok = post_one_video(video_path, verse, state, total,
                        platform=args.platform, dry_run=args.dry_run)
    if args.dry_run:
        logger.info("DRY RUN complete.")
    sys.exit(0 if ok or args.dry_run else 1)


if __name__ == "__main__":
    main()
