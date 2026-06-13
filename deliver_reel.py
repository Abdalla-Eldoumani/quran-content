#!/usr/bin/env python3
"""Email a rendered planned reel and its caption for review.

Takes a reel directory (the output of `generate_videos.py --plan`), uses
caption.txt as the email body, and attaches the mp4 when it is under the
attachment size limit, otherwise notes the local path instead. Configuration
comes from environment variables only; no credential is ever printed.
"""

import argparse
import io
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import make_msgid

# Fix Windows console encoding for any non-ASCII output.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Constants ────────────────────────────────────────────────────────────────

REQUIRED_ENV = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "DELIVER_TO")
SIZE_LIMIT_BYTES = 22 * 1024 * 1024  # attach below this; note the path at or above


# ── Reel directory helpers ───────────────────────────────────────────────────

def find_mp4(reel_dir):
    """Return the single mp4 in the reel directory, or None."""
    mp4s = sorted(f for f in os.listdir(reel_dir) if f.lower().endswith(".mp4"))
    return os.path.join(reel_dir, mp4s[0]) if mp4s else None


def build_subject(reel_dir):
    """Build the email subject from reel_plan.json, falling back to the dir name."""
    plan_path = os.path.join(reel_dir, "reel_plan.json")
    if os.path.isfile(plan_path):
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)
            surah, ayah, ayah_end = plan["surah"], plan["ayah"], plan["ayah_end"]
            ref = f"{surah}:{ayah}" if ayah == ayah_end else f"{surah}:{ayah}-{ayah_end}"
            return f"Planned reel: {plan['name']} ({ref})"
        except (OSError, ValueError, KeyError):
            pass
    return f"Planned reel: {os.path.basename(os.path.normpath(reel_dir))}"


# ── Email assembly and send ──────────────────────────────────────────────────

def build_message(reel_dir, smtp_user, deliver_to):
    """Build the EmailMessage. Attaches the mp4 under the size limit, else notes its path."""
    caption_path = os.path.join(reel_dir, "caption.txt")
    if not os.path.isfile(caption_path):
        raise FileNotFoundError(f"caption.txt not found in {reel_dir}")
    with open(caption_path, "r", encoding="utf-8") as f:
        body = f.read()

    mp4_path = find_mp4(reel_dir)
    if not mp4_path:
        raise FileNotFoundError(f"no mp4 found in {reel_dir}")
    size = os.path.getsize(mp4_path)

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = deliver_to
    msg["Subject"] = build_subject(reel_dir)
    msg["Message-ID"] = make_msgid()

    if size < SIZE_LIMIT_BYTES:
        msg.set_content(body)
        with open(mp4_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="video", subtype="mp4",
                               filename=os.path.basename(mp4_path))
        attached = True
    else:
        size_mb = size / (1024 * 1024)
        note = (f"\n\nVideo is {size_mb:.1f}MB, over the {SIZE_LIMIT_BYTES // (1024 * 1024)}MB "
                f"attachment limit. Find it locally at:\n{os.path.abspath(mp4_path)}")
        msg.set_content(body + note)
        attached = False

    return msg, attached, size


def send_message(msg, host, port, user, password):
    """Send the message over SMTP with STARTTLS. Returns the Message-ID on success."""
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
    return msg["Message-ID"]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Email a rendered planned reel for review")
    parser.add_argument("reel_dir", help="the reel directory produced by generate_videos.py --plan")
    args = parser.parse_args()

    if not os.path.isdir(args.reel_dir):
        print(f"ERROR: not a directory: {args.reel_dir}")
        sys.exit(1)

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"ERROR: missing environment variable(s): {', '.join(missing)}")
        sys.exit(1)

    host = os.environ["SMTP_HOST"]
    try:
        port = int(os.environ["SMTP_PORT"])
    except ValueError:
        print("ERROR: SMTP_PORT must be an integer")
        sys.exit(1)
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    deliver_to = os.environ["DELIVER_TO"]

    try:
        msg, attached, size = build_message(args.reel_dir, user, deliver_to)
    except (FileNotFoundError, OSError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    size_mb = size / (1024 * 1024)
    if attached:
        print(f"Attaching {os.path.basename(args.reel_dir)} mp4 ({size_mb:.1f}MB) to {deliver_to}")
    else:
        print(f"Video is {size_mb:.1f}MB (over limit); sending caption with local path only to {deliver_to}")

    try:
        message_id = send_message(msg, host, port, user, password)
    except (smtplib.SMTPException, OSError) as e:
        print(f"ERROR: SMTP delivery failed: {str(e)[:300]}")
        sys.exit(1)

    print(f"Delivered. Message-ID: {message_id}")


if __name__ == "__main__":
    main()
