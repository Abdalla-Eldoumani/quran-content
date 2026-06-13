#!/usr/bin/env python3
"""
One-time setup for Meta (Instagram + Facebook) API access.

Exchanges a short-lived user token for a permanent page access token,
then saves it to .env as META_ACCESS_TOKEN.

Prerequisites:
  1. Create a Meta App at developers.facebook.com
  2. Add Instagram Graph API and Pages API products
  3. Generate a short-lived user token in Graph API Explorer
  4. Fill in META_SHORT_TOKEN, META_APP_ID, META_APP_SECRET in .env
"""

import sys

try:
    import requests
    from dotenv import load_dotenv, set_key
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests python-dotenv")
    sys.exit(1)

import os

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
GRAPH_API = "https://graph.facebook.com/v21.0"


def main():
    load_dotenv(ENV_PATH)

    app_id = os.environ.get("META_APP_ID", "").strip()
    app_secret = os.environ.get("META_APP_SECRET", "").strip()
    short_token = os.environ.get("META_SHORT_TOKEN", "").strip()

    if not all([app_id, app_secret, short_token]):
        print("ERROR: Missing required .env variables.")
        print("Set META_APP_ID, META_APP_SECRET, and META_SHORT_TOKEN in .env")
        print("Get a short-lived token from Graph API Explorer:")
        print("  https://developers.facebook.com/tools/explorer/")
        sys.exit(1)

    # Step 1: Exchange short token for long-lived user token
    print("Exchanging short token for long-lived token...")
    resp = requests.get(
        f"{GRAPH_API}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"ERROR: Token exchange failed ({resp.status_code})")
        print(f"Response: {resp.text[:300]}")
        print("\nCheck that META_APP_ID, META_APP_SECRET, and META_SHORT_TOKEN are correct.")
        sys.exit(1)

    long_token = resp.json()["access_token"]
    print("  Long-lived user token obtained.")

    # Step 2: Get page access token (permanent)
    print("Fetching page access token...")
    resp = requests.get(
        f"{GRAPH_API}/me/accounts",
        params={"access_token": long_token},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"ERROR: Failed to fetch pages ({resp.status_code})")
        print(f"Response: {resp.text[:300]}")
        sys.exit(1)

    pages = resp.json().get("data", [])
    if not pages:
        print("ERROR: No pages found. Make sure your Facebook account manages a Page")
        print("and the token has pages_show_list and pages_read_engagement permissions.")
        sys.exit(1)

    if len(pages) == 1:
        page = pages[0]
    else:
        print(f"\nFound {len(pages)} pages:")
        for i, p in enumerate(pages, 1):
            print(f"  {i}. {p['name']} (ID: {p['id']})")
        choice = input(f"Select page (1-{len(pages)}): ").strip()
        page = pages[int(choice) - 1]

    page_token = page["access_token"]
    page_id = page["id"]
    print(f"  Page: {page['name']} (ID: {page_id})")

    # Step 3: Save to .env
    set_key(ENV_PATH, "META_ACCESS_TOKEN", page_token)
    set_key(ENV_PATH, "FB_PAGE_ID", page_id)
    print("  Saved META_ACCESS_TOKEN and FB_PAGE_ID to .env")

    # Step 4: Get Instagram Business Account ID
    print("Fetching Instagram Business Account ID...")
    resp = requests.get(
        f"{GRAPH_API}/{page_id}",
        params={
            "fields": "instagram_business_account",
            "access_token": page_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"WARNING: Could not fetch IG account ({resp.status_code})")
        print("You'll need to set IG_USER_ID manually in .env")
    else:
        ig_data = resp.json().get("instagram_business_account")
        if ig_data:
            ig_user_id = ig_data["id"]
            set_key(ENV_PATH, "IG_USER_ID", ig_user_id)
            print(f"  Saved IG_USER_ID={ig_user_id} to .env")
        else:
            print("WARNING: No Instagram Business Account linked to this Page.")
            print("Connect one in Facebook Page Settings > Instagram.")

    # Step 5: Test token
    print("\nTesting token...")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    if not ig_user_id:
        load_dotenv(ENV_PATH, override=True)
        ig_user_id = os.environ.get("IG_USER_ID", "")

    if ig_user_id:
        resp = requests.get(
            f"{GRAPH_API}/{ig_user_id}",
            params={"fields": "username", "access_token": page_token},
            timeout=10,
        )
        if resp.status_code == 200:
            username = resp.json().get("username", "unknown")
            print(f"\nSETUP COMPLETE. Instagram account: @{username}")
        else:
            print(f"WARNING: Token test failed ({resp.status_code}): {resp.text[:300]}")
            print("The token was saved but may not work. Re-run setup if posting fails.")
    else:
        print("\nSETUP PARTIALLY COMPLETE.")
        print("META_ACCESS_TOKEN and FB_PAGE_ID saved.")
        print("Set IG_USER_ID manually in .env for Instagram posting.")

    print("\nNext steps:")
    print("  1. Copy META_ACCESS_TOKEN, IG_USER_ID, FB_PAGE_ID to GitHub Secrets")
    print("  2. Test with: python3 auto_post.py --dry-run --platform meta")


if __name__ == "__main__":
    main()
