# Automated Daily Posting — Setup Guide

Set up a GitHub Actions workflow that generates one Quran verse video per day and posts it to Instagram, Facebook, and YouTube.

**Total cost: $0.** Everything uses free-tier services.

**Setup time:** ~1 hour (one-time).

---

## How it works

```
Every day at a scheduled time:

  GitHub Actions runner spins up
    → Checks out your repo
    → Reads state.json to find which verse is next
    → Generates a video (scenery + Arabic text + recitation audio)
    → Posts it as an Instagram Reel via Meta Graph API
    → Posts it as a Facebook video via Meta Graph API
    → Uploads it as a YouTube Short via YouTube Data API
    → Saves progress to state.json
    → Commits and pushes state.json back to the repo
    → Shuts down

Total runtime: ~5 minutes per day.
GitHub Actions free tier: 2,000 minutes/month.
You'll use ~150 minutes/month. Well within limits.
```

---

## Prerequisites

Before starting, make sure you have:

- A GitHub account (free)
- An Instagram account set to **Professional** (Creator or Business) — free, switch in Settings → Account
- A Facebook Page linked to your Instagram account
- A YouTube channel (any Google account has one)
- A Pexels API key (you already have this if you've been generating videos)

---

## Step 1: Create a Meta Developer App

This gives you API access to post Reels to Instagram and videos to Facebook.

1. Go to **https://developers.facebook.com** and log in with the Facebook account that owns your Page
2. Click **Create App**
3. Select **Business** as the app type
4. Name it anything (e.g., "Quran Daily Posts") and click **Create**
5. In the app dashboard, click **Add Product** on the left sidebar
6. Add **Facebook Login for Business** (click Set Up)
7. Add **Instagram Graph API** (click Set Up)
8. Go to **App Settings → Basic** (left sidebar)
9. Copy your **App ID** and **App Secret** — save them somewhere safe

### Get your access token

10. Go to **Graph API Explorer**: https://developers.facebook.com/tools/explorer/
11. In the top-right dropdown, select your app
12. Click **Generate Access Token**
13. A Facebook login popup appears — approve all requested permissions:
    - `pages_show_list`
    - `pages_read_engagement`
    - `pages_manage_posts`
    - `instagram_basic`
    - `instagram_content_publish`
14. Copy the token that appears — this is your **short-lived user token** (expires in ~1 hour)

### Find your Page ID and Instagram User ID

15. In Graph API Explorer, paste this into the query field and click Submit:
    ```
    GET /me/accounts
    ```
16. Find your Facebook Page in the results. Copy the **id** field — this is your **FB_PAGE_ID**

17. Now query:
    ```
    GET /{your_page_id}?fields=instagram_business_account
    ```
18. Copy the **id** inside `instagram_business_account` — this is your **IG_USER_ID**

### Convert to a long-lived token

19. Create a `.env` file in your project root with these values:
    ```
    META_APP_ID=your_app_id
    META_APP_SECRET=your_app_secret
    META_SHORT_TOKEN=the_token_from_step_14
    IG_USER_ID=from_step_18
    FB_PAGE_ID=from_step_16
    ```

20. Run the setup script:
    ```bash
    python3 setup_meta.py
    ```
    This exchanges your short-lived token for a **permanent page access token** and saves it as `META_ACCESS_TOKEN` in your `.env` file.

21. If it prints your Instagram username, you're good. If it shows an error, double-check that your Instagram is linked to your Facebook Page and that you approved all permissions.

---

## Step 2: Set up YouTube API

This gives you access to upload Shorts to your YouTube channel.

1. Go to **https://console.cloud.google.com**
2. Click **Select a project** → **New Project** → name it (e.g., "Quran Shorts") → **Create**
3. In the left sidebar, go to **APIs & Services → Library**
4. Search for **YouTube Data API v3** → click it → click **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **Create Credentials → OAuth Client ID**
7. If prompted to configure the consent screen:
   - User type: **External** → Create
   - App name: anything → your email as support email → your email as developer contact
   - Scopes: skip for now → Save
   - Test users: add your own Gmail address → Save
8. Back in Credentials, click **Create Credentials → OAuth Client ID**
9. Application type: **Desktop app** → name it anything → **Create**
10. Copy the **Client ID** and **Client Secret**

11. Add them to your `.env`:
    ```
    YOUTUBE_CLIENT_ID=your_client_id
    YOUTUBE_CLIENT_SECRET=your_client_secret
    ```

12. Run the setup script:
    ```bash
    python3 setup_youtube.py
    ```
    This opens a browser for Google OAuth. Sign in, approve access, and the script saves your `YOUTUBE_REFRESH_TOKEN` to `.env`.

13. If it prints your channel name, you're good.

### Important: YouTube's private upload policy

YouTube API projects created after July 2020 default all uploads to **private** until you pass a compliance audit. This means your first uploads will be private even if the code says "public."

To fix this:
1. Go to **Google Cloud Console → APIs & Services → YouTube Data API v3**
2. Look for a **Compliance** or **Audit** section
3. Fill out the questionnaire (it asks what your app does — say "uploads educational Islamic content to my own channel")
4. Wait for approval (usually 1-3 business days)

Until then, your videos upload as private. You can manually set them to public in YouTube Studio. After audit approval, they'll upload as public automatically.

---

## Step 3: Push to GitHub

1. Create a **private** repository on GitHub (your API tokens will be in the secrets, but still keep it private)

2. Push your project:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

3. Go to your repo on GitHub → **Settings → Secrets and variables → Actions**

4. Add each of these as a **Repository Secret** (click "New repository secret" for each):

   | Secret name | Value |
   |---|---|
   | `PEXELS_API_KEY` | Your Pexels API key |
   | `META_ACCESS_TOKEN` | The permanent page token from setup_meta.py |
   | `IG_USER_ID` | Your Instagram Business Account ID |
   | `FB_PAGE_ID` | Your Facebook Page ID |
   | `YOUTUBE_CLIENT_ID` | Your YouTube OAuth Client ID |
   | `YOUTUBE_CLIENT_SECRET` | Your YouTube OAuth Client Secret |
   | `YOUTUBE_REFRESH_TOKEN` | The refresh token from setup_youtube.py |

5. Go to **Settings → Actions → General** → under "Workflow permissions," select **Read and write permissions** and check **Allow GitHub Actions to create and approve pull requests** → Save. (This lets the workflow commit state.json updates.)

---

## Step 4: Enable the workflow

1. Go to your repo → **Actions** tab
2. You should see the "Daily Quran Post" workflow
3. Click **Enable workflow** if prompted
4. To test it immediately: click **Run workflow → Run workflow**
5. Watch the run. If it succeeds, check your Instagram, Facebook, and YouTube for the new post.

The workflow runs daily at 2 PM UTC by default (8 AM Calgary time). To change the schedule, edit the `cron` line in `.github/workflows/daily_post.yml`:

```yaml
# Some examples:
cron: '0 14 * * *'   # 2 PM UTC (default)
cron: '0 6 * * *'    # 6 AM UTC
cron: '30 17 * * *'  # 5:30 PM UTC
```

Use https://crontab.guru to build your preferred schedule.

---

## Step 5: Verify and monitor

After the first successful run:

- **Instagram**: Check your profile for the new Reel
- **Facebook**: Check your Page for the new video
- **YouTube**: Check YouTube Studio for the new Short (may be private until audit passes)
- **state.json**: Should show `next_index: 1` and a history entry

To monitor ongoing runs:
- Go to your repo → **Actions** tab → you'll see each daily run with its status
- If a run fails, click into it to see the error logs
- GitHub sends email notifications for failed workflows by default

---

## Troubleshooting

**"Instagram container status is ERROR"**
- The video might be too large or in an unsupported format. Check that it's H.264 MP4, under 100MB, and under 90 seconds.
- ERROR is usually transient processing. The script uploads the file directly through Meta's resumable endpoint (no public URL), polls up to 30 times, and aborts without publishing on ERROR. Retry once before investigating.

**"Meta token invalid"**
- Page access tokens from the page token flow should be permanent, but if yours stops working, re-run `setup_meta.py` to get a fresh one. Then update the `META_ACCESS_TOKEN` secret in GitHub.

**"YouTube upload quota exceeded"**
- The free YouTube API quota allows ~6 uploads per day (each upload costs ~1,600 units out of a 10,000 daily quota). One upload per day is well within limits.
- If you've been testing heavily, wait until the quota resets (midnight Pacific time).

**"YouTube video uploaded as private"**
- Complete the compliance audit in Google Cloud Console (see Step 2 above).
- Or manually set videos to public in YouTube Studio until the audit passes.

**"Pexels returned no results"**
- The script has a fallback query ("ocean waves aerial"). If that also fails, the Pexels API might be temporarily down. The workflow will retry the next day.

**"GitHub Actions workflow not running"**
- Go to Actions tab and make sure the workflow is enabled
- Check that the repo has Actions enabled (Settings → Actions → General)
- Scheduled workflows may be disabled if the repo has no activity for 60 days — push a commit to re-enable

---

## Planned reel delivery (optional)

The planned-reel workflow (see the README) emails a finished reel to you for review with `deliver_reel.py`, which reads five SMTP variables from the environment or `.env`. The committed `.env.example` does not list them, so add them to your `.env`:

```
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=
DELIVER_TO=
```

- `SMTP_HOST` - mail server hostname, for example `smtp.gmail.com`
- `SMTP_PORT` - the STARTTLS port, usually `587`
- `SMTP_USER` - the sending account's address
- `SMTP_PASS` - an app password for that account (for Gmail, create one under Google Account, Security, App passwords), never the login password
- `DELIVER_TO` - the address that receives the reel for review

`deliver_reel.py` attaches the mp4 when it is under 22MB and otherwise emails the caption with the file's local path. These variables are used only for local review delivery, not by the daily GitHub Actions pipeline.

---

## What this costs

| Service | Free tier | Your usage | Cost |
|---|---|---|---|
| GitHub Actions | 2,000 min/month | ~150 min/month | $0 |
| Pexels API | 200 req/hour | ~5 req/day | $0 |
| AlQuran Cloud API | Unlimited | ~5 req/day | $0 |
| Quran.com API | Unlimited | ~1 req/day | $0 |
| Meta Graph API | Unlimited | 1 post/day | $0 |
| YouTube Data API | 10,000 units/day | ~1,600 units/day | $0 |
| **Total** | | | **$0** |

---

## Maintaining long-term

With 1,282 verses in `verses.json`, the system loops through all of them before repeating. At one video per day, that's about **3.5 years** before any verse repeats.

The only maintenance you might need:
- If Meta changes their API (rare, they version it) — update the API version in auto_post.py
- If YouTube token expires (shouldn't with a refresh token, but check if uploads start failing)
- If you want to add more verses — edit `generate_verses_json.py` and regenerate
- If you want to change reciters or scenery — same, edit the generator and re-run

Beyond that, the pipeline runs daily with no intervention needed.