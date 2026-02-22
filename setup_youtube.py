#!/usr/bin/env python3
"""
One-time setup for YouTube Data API v3 access.

Runs the OAuth 2.0 flow to obtain a refresh token, then saves it to .env
as YOUTUBE_REFRESH_TOKEN.

Prerequisites:
  1. Create a project in Google Cloud Console
  2. Enable YouTube Data API v3
  3. Create OAuth 2.0 credentials (Desktop app type)
  4. Fill in YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env
  5. OAuth consent screen: add your own email as a Test User
     (APIs & Services > OAuth consent screen > Test users > Add users)
     Without this, you'll get "Error 403: access_denied" even as the project owner.
"""

import sys

try:
    from dotenv import load_dotenv, set_key
except ImportError:
    print("Missing python-dotenv. Install with: pip install python-dotenv")
    sys.exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    print("Missing Google API packages. Install with:")
    print("  pip install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

import os

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    load_dotenv(ENV_PATH)

    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("ERROR: Missing required .env variables.")
        print("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env")
        print("\nTo get these:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop application)")
        print("  3. Copy Client ID and Client Secret to .env")
        sys.exit(1)

    # Build client config for the OAuth flow
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    # Run OAuth flow
    print("Starting OAuth flow...")
    print("A browser window will open for Google authorization.")
    print("NOTE: If you get 'Error 403: access_denied', add your email")
    print("as a Test User in Google Cloud Console:")
    print("  APIs & Services > OAuth consent screen > Test users > Add users\n")

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0)

    if not credentials.refresh_token:
        print("ERROR: No refresh token received.")
        print("This can happen if you've already authorized this app.")
        print("Revoke access at https://myaccount.google.com/permissions")
        print("then re-run this script.")
        sys.exit(1)

    # Save refresh token
    set_key(ENV_PATH, "YOUTUBE_REFRESH_TOKEN", credentials.refresh_token)
    print("Saved YOUTUBE_REFRESH_TOKEN to .env")

    # Test by fetching channel info
    print("\nTesting credentials...")
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        resp = youtube.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            channel_name = items[0]["snippet"]["title"]
            print(f"Authenticated as: {channel_name}")
        else:
            print("WARNING: No YouTube channel found for this account.")
            print("Create a channel at https://www.youtube.com/create_channel")
    except Exception as e:
        print(f"WARNING: Channel test failed: {e}")
        print("The refresh token was saved and may still work for uploads.")

    # Compliance warning
    print("\n" + "=" * 60)
    print("IMPORTANT: YouTube API Compliance Audit")
    print("=" * 60)
    print("""
If your API project was created after July 28, 2020, uploaded
videos will default to PRIVATE until you pass a compliance audit.

To request an audit:
  1. Go to Google Cloud Console
  2. APIs & Services > YouTube Data API v3
  3. Click "Compliance" in the left sidebar
  4. Fill out the audit form

Until the audit passes, videos will upload successfully but
remain private. This is a YouTube policy, not a bug.
""")

    print("Next steps:")
    print("  1. Copy YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,")
    print("     and YOUTUBE_REFRESH_TOKEN to GitHub Secrets")
    print("  2. Test with: python3 auto_post.py --dry-run --platform youtube")


if __name__ == "__main__":
    main()
