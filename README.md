# IGCC Instagram Daily Poster

Every day this designs a branded IGCC image from the content calendar and posts it to the IGCC
Instagram Business account. It runs on
GitHub Actions, so you don't need a server or a computer left switched on.

```
calendar.json ──► poster.py renders a 1080×1350 image ──► committed to the repo (public URL)
                                                       ──► Instagram Graph API publishes it
```

## Files

| File | What it is |
|---|---|
| `config.json` | Brand name, handle, website, colours, timezone, default hashtags |
| `calendar.json` | What to post on each date. If a date is empty, a post from the `evergreen` list is used |
| `assets/` | IGCC logos and the facet watermark |
| `photos/` | Your own photos for the `photo` template |
| `illustrations.py` | The line-art illustrations |
| `fonts/bold.ttf`, `fonts/regular.ttf` | Your brand fonts (optional) |
| `canva/` | Finished designs exported from Canva, named `YYYY-MM-DD.png`. If a file exists for a date, it is posted instead of the generated image |
| `output/posts/` | Images that have been posted, plus a `.posted.json` record for each |
| `.github/workflows/instagram-daily-post.yml` | The daily schedule |

## 1. Prepare Instagram (one-time)

1. In the Instagram app, open **Settings → Account type and tools** and switch to a **Business** account.
2. Create a **Facebook Page** for your business, or use an existing one, and link it to the
   Instagram account: on the Page, open **Settings → Linked accounts → Instagram**.
3. Open **business.facebook.com** (Meta Business Suite) and make sure the Page and the Instagram
   account are both in your business portfolio.

## 2. Create a Meta app and get credentials (one-time)

1. Go to **developers.facebook.com → My Apps → Create app**, choose the **Business** type and
   connect it to your business portfolio.
2. In the app, add the **Instagram** product (the *Instagram API with Facebook Login* setup).
3. Get a token that never expires by creating a **System User**:
   - In **Business Settings → Users → System users**, click **Add** and give it the *Admin* role.
   - Click **Assign assets**, add your Facebook Page and Instagram account, and give it full control.
   - Click **Generate new token**, select your app, set the expiry to **Never**, and tick
     `instagram_basic`, `instagram_content_publish`, `pages_show_list` and `pages_read_engagement`.
   - Copy the token. This is your **IG_ACCESS_TOKEN**.
4. Find your **IG_USER_ID**, the Instagram Business Account ID. In the
   [Graph API Explorer](https://developers.facebook.com/tools/explorer/), paste the token and run
   `me/accounts?fields=name,instagram_business_account`. The `instagram_business_account.id`
   value is your ID.

> Keep the token secret. Never paste it into code, a chat or a commit.

## 3. Add the credentials to GitHub

In this repository, open **Settings → Secrets and variables → Actions → New repository secret**
and add two secrets:

- `IG_USER_ID`
- `IG_ACCESS_TOKEN`

## 4. Brand it and plan your content

- Edit `config.json`: brand name, `@handle`, website, colours (hex codes), `timezone` (`Asia/Kolkata`) and default hashtags.
- Drop your logo into `assets/logo.png`.
- Fill `calendar.json` with one entry per date. There are four templates: `quote`, `tip`, `announcement` and `photo`.

```jsonc
"2026-12-01": { "template": "quote", "text": "…", "author": "…", "caption": "…" }
"2026-12-02": { "template": "tip", "label": "TIP OF THE DAY", "title": "…", "text": "…", "caption": "…" }
"2026-12-03": { "template": "announcement", "title": "…", "text": "…", "cta": "Visit {website}", "caption": "…" }
```

### Illustrations and photos

- Tip and announcement posts can carry a line-art illustration in IGCC light blue. Add
  `"illustration": "diamond"`. The options are `diamond`, `brilliance`, `loupe`, `report` and `scale`.
- To post your **own photos** (lab, instruments, stones, team), put them in `photos/` and use the
  `photo` template:

```json
"2026-12-01": { "template": "photo", "photo": "photos/lab-microscope.jpg", "label": "INSIDE OUR LAB",
                "title": "Every stone, examined in detail", "text": "…", "caption": "…" }
```

  The photo fills the top half and fades into the IGCC navy, with the text below it.
  Landscape or square photos at least 1080px wide work best.

Optional for any entry: `"hashtags": ["#extra", "#tags"]`. These are added to the defaults.
Captions can use `{brand}`, `{handle}`, `{website}`, `{date}` and `{weekday}`.

## 5. Preview before anything goes live

```bash
pip install -r requirements.txt
python poster.py preview --days 14                 # next 14 days -> output/preview/
python poster.py preview --date 2026-12-01 --days 31
```

Each image gets a matching `.txt` file containing the caption that will be posted.

## 6. Go live

- The schedule runs from the `main` branch, which this repo already uses.
- The posting time is the `cron:` line in the workflow, written in UTC. It's currently
  `27 3 * * *`, which is about 9:00 AM IST. To work out another time, subtract 5h30m from IST.
- To test straight away, open the **Actions** tab, choose **Instagram daily post**, click **Run workflow**,
  and enter a date. It posts for real.
- Every post is recorded in `output/posts/DATE.posted.json`, so a day is never posted twice.

## Notes

- The repository must stay **public**: Instagram downloads the image from its public GitHub URL.
  If you make the repo private, the images need a different host (for example, Cloudinary or S3).
- Instagram allows up to 50 API posts per 24 hours. One a day is well within that.
- This tool publishes feed photo posts. Carousels, Reels and Stories can be added later.
