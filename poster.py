"""Daily Instagram poster: renders a branded image from calendar.json and publishes it
through the Instagram Graph API.

Commands
  python poster.py preview [--date D] [--days N]   render images locally (no posting)
  python poster.py render  [--date D]               render the post image for one day
  python poster.py publish [--date D] --image-url URL
                                                    publish that day's post (image must be public)
  python poster.py check                            verify the access token / account ID

--date accepts YYYY-MM-DD or "today" (default), using the timezone in config.json.
Credentials come from environment variables: IG_USER_ID and IG_ACCESS_TOKEN.
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from illustrations import ILLUSTRATIONS

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
POSTS = OUTPUT / "posts"
PREVIEW = OUTPUT / "preview"
CANVA = ROOT / "canva"  # finished designs exported from Canva, named YYYY-MM-DD.png/.jpg

SYSTEM_FONTS = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
}


# ----------------------------------------------------------------------------- config

def load_json(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return json.load(f)


def resolve_date(value, tz):
    if value in (None, "today"):
        return datetime.now(ZoneInfo(tz)).date()
    if value == "tomorrow":
        return datetime.now(ZoneInfo(tz)).date() + timedelta(days=1)
    return date.fromisoformat(value)


def entry_for(day, calendar):
    """The calendar entry for a day, or a rotating evergreen post if none is planned."""
    key = day.isoformat()
    if key in calendar.get("days", {}):
        return dict(calendar["days"][key]), "calendar"
    pool = calendar.get("evergreen") or []
    if not pool:
        return None, None
    return dict(pool[day.toordinal() % len(pool)]), "evergreen"


def fill(text, cfg, day):
    brand = cfg["brand"]
    return (text or "").format(
        brand=brand.get("name", ""),
        handle=brand.get("handle", ""),
        website=brand.get("website", ""),
        date=day.strftime("%d %B %Y"),
        weekday=day.strftime("%A"),
    )


def build_caption(entry, cfg, day):
    caption = fill(entry.get("caption", ""), cfg, day).strip()
    tags = list(cfg.get("default_hashtags", [])) + list(entry.get("hashtags", []))
    seen, unique = set(), []
    for t in tags:
        t = t if t.startswith("#") else "#" + t
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
    if unique:
        caption = f"{caption}\n\n{' '.join(unique)}" if caption else " ".join(unique)
    return caption[:2200]  # Instagram caption limit


# ----------------------------------------------------------------------------- drawing

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Painter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.W, self.H = cfg.get("image_size", [1080, 1350])
        self.c = {k: hex_rgb(v) for k, v in cfg["colors"].items()}
        self.margin = int(self.W * 0.09)

    def font(self, kind, size):
        candidates = [ROOT / self.cfg.get("fonts", {}).get(kind, "")] + [Path(p) for p in SYSTEM_FONTS[kind]]
        for p in candidates:
            if p.is_file():
                return ImageFont.truetype(str(p), size)
        return ImageFont.load_default(size=size)

    @staticmethod
    def wrap(draw, text, font, max_width):
        lines = []
        for para in text.split("\n"):
            words, line = para.split(), ""
            for w in words:
                trial = f"{line} {w}".strip()
                if draw.textlength(trial, font=font) <= max_width or not line:
                    line = trial
                else:
                    lines.append(line)
                    line = w
            lines.append(line)
        return lines

    def fit(self, draw, text, kind, max_width, max_height, start, minimum=28, spacing=1.25):
        """Largest font size at which text wraps inside the box."""
        size = start
        while True:
            f = self.font(kind, size)
            lines = self.wrap(draw, text, f, max_width)
            height = int(len(lines) * size * spacing)
            widest = max((draw.textlength(l, font=f) for l in lines), default=0)
            if (height <= max_height and widest <= max_width) or size <= minimum:
                return f, lines, size
            size -= 4

    def block(self, draw, lines, font, size, y, color, align="center", spacing=1.25):
        for line in lines:
            w = draw.textlength(line, font=font)
            x = (self.W - w) / 2 if align == "center" else self.margin
            draw.text((x, y), line, font=font, fill=color)
            y += int(size * spacing)
        return y

    def canvas(self, entry=None):
        top, bottom = self.c["background"], self.c.get("background_end", self.c["background"])
        img = Image.new("RGB", (self.W, self.H), top)
        d = ImageDraw.Draw(img)
        for y in range(self.H):
            t = y / (self.H - 1)
            d.line([(0, y), (self.W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        if not (entry and (entry.get("illustration") or entry.get("photo"))):
            self.watermark(img)
        return img

    def art(self, name, size):
        if name not in ILLUSTRATIONS:
            raise ValueError(f"Unknown illustration '{name}'. Options: {', '.join(ILLUSTRATIONS)}")
        return ILLUSTRATIONS[name](size, self.c["accent"] + (255,))

    def pill(self, d, text, y):
        lf = self.font("bold", 32)
        lw = d.textlength(text, font=lf)
        d.rounded_rectangle([self.margin, y, self.margin + lw + 56, y + 70], radius=35, fill=self.c["accent"])
        d.text((self.margin + 28, y + 16), text, font=lf, fill=self.c["background"])

    def watermark(self, img):
        """Large faint brand emblem bleeding off the bottom-right corner."""
        wm = self.cfg["brand"].get("watermark")
        if not wm or not (ROOT / wm).is_file():
            return
        mark = Image.open(ROOT / wm).convert("RGBA")
        size = int(self.W * 0.95)
        mark = mark.resize((size, size), Image.LANCZOS)
        alpha = mark.getchannel("A").point(lambda v: int(v * self.cfg["brand"].get("watermark_opacity", 0.08)))
        tinted = Image.new("RGBA", mark.size, self.c["accent"] + (0,))
        tinted.putalpha(alpha)
        img.paste(tinted, (int(self.W * 0.42), int(self.H * 0.5)), tinted)

    def frame(self, img, day):
        """Brand header and footer shared by every template."""
        d = ImageDraw.Draw(img)
        m, brand = self.margin, self.cfg["brand"]
        header_y = int(self.H * 0.055)

        logo_path = ROOT / brand.get("logo", "")
        if brand.get("logo") and logo_path.is_file():
            logo = Image.open(logo_path).convert("RGBA")
            h = brand.get("logo_height", 64)
            logo = logo.resize((int(logo.width * h / logo.height), h), Image.LANCZOS)
            img.paste(logo, (m, header_y), logo)
        else:
            d.text((m, header_y + 12), brand.get("name", "").upper(), font=self.font("bold", 34), fill=self.c["text"])

        date_font = self.font("regular", 28)
        date_txt = day.strftime("%d %b %Y").upper()
        d.text((self.W - m - d.textlength(date_txt, font=date_font), header_y + 24), date_txt,
               font=date_font, fill=self.c["muted"])

        foot_y = self.H - int(self.H * 0.085)
        d.rectangle([m, foot_y - 30, m + 80, foot_y - 24], fill=self.c["accent"])
        foot_font = self.font("regular", 30)
        d.text((m, foot_y), brand.get("handle", ""), font=foot_font, fill=self.c["muted"])
        site = brand.get("website", "")
        d.text((self.W - m - d.textlength(site, font=foot_font), foot_y), site, font=foot_font, fill=self.c["muted"])

    # --- templates -----------------------------------------------------------

    def quote(self, entry, day):
        img = self.canvas()
        d = ImageDraw.Draw(img)
        inner = self.W - 2 * self.margin
        mark = self.font("bold", 260)
        d.text((self.margin - 10, int(self.H * 0.15)), "\u201C", font=mark, fill=self.c["accent"])

        text = fill(entry.get("text", ""), self.cfg, day)
        f, lines, size = self.fit(d, text, "bold", inner, int(self.H * 0.42), 84)
        h = int(len(lines) * size * 1.25)
        y = int(self.H * 0.52 - h / 2)
        y = self.block(d, lines, f, size, y, self.c["text"], align="left")
        if entry.get("author"):
            d.text((self.margin, y + 30), "\u2014 " + fill(entry["author"], self.cfg, day),
                   font=self.font("regular", 40), fill=self.c["accent"])
        self.frame(img, day)
        return img

    def tip(self, entry, day):
        img = self.canvas(entry)
        d = ImageDraw.Draw(img)
        inner = self.W - 2 * self.margin
        y = int(self.H * 0.2)

        self.pill(d, fill(entry.get("label", "TIP OF THE DAY"), self.cfg, day).upper(), y)
        y += 130

        title = fill(entry.get("title", ""), self.cfg, day)
        f, lines, size = self.fit(d, title, "bold", inner, int(self.H * 0.3), 96)
        y = self.block(d, lines, f, size, y, self.c["text"], align="left", spacing=1.15)
        y += 40
        d.rectangle([self.margin, y, self.margin + 120, y + 8], fill=self.c["accent"])
        y += 60

        body = fill(entry.get("text", ""), self.cfg, day)
        bottom = int(self.H * 0.87)
        if body:
            space = bottom - y
            f, lines, size = self.fit(d, body, "regular", inner, space, 44, minimum=34, spacing=1.4)
            y = self.block(d, lines, f, size, y, self.c["muted"], align="left", spacing=1.4)
        if entry.get("illustration"):
            size = min(bottom - y - 20, 560)
            if size >= 170:
                art = self.art(entry["illustration"], size)
                img.paste(art, (self.W - self.margin - size + 30, bottom - size), art)
        self.frame(img, day)
        return img

    def announcement(self, entry, day):
        img = self.canvas(entry)
        d = ImageDraw.Draw(img)
        inner = self.W - 2 * self.margin

        title = fill(entry.get("title", ""), self.cfg, day)
        tf, tlines, tsize = self.fit(d, title, "bold", inner, int(self.H * 0.32), 140, spacing=1.1)
        body = fill(entry.get("text", ""), self.cfg, day)
        bf, blines, bsize = self.fit(d, body, "regular", inner, int(self.H * 0.18), 52, spacing=1.35) if body else (None, [], 0)
        cta = fill(entry.get("cta", ""), self.cfg, day)

        art_size = 260 if entry.get("illustration") else 0
        total = art_size + len(tlines) * tsize * 1.1 + 50 + len(blines) * bsize * 1.35 + (150 if cta else 0)
        y = int(self.H * 0.55 - total / 2)
        if art_size:
            art = self.art(entry["illustration"], art_size)
            img.paste(art, ((self.W - art_size) // 2, y - 20), art)
            y += art_size
        y = self.block(d, tlines, tf, tsize, y, self.c["text"], spacing=1.1) + 50
        if blines:
            y = self.block(d, blines, bf, bsize, y, self.c["muted"], spacing=1.35)
        if cta:
            cf = self.font("bold", 40)
            cw = d.textlength(cta, font=cf)
            x0 = (self.W - cw) / 2 - 50
            d.rounded_rectangle([x0, y + 50, x0 + cw + 100, y + 150], radius=50, fill=self.c["accent"])
            d.text((x0 + 50, y + 75), cta, font=cf, fill=self.c["background"])
        self.frame(img, day)
        return img

    def photo(self, entry, day):
        """Your own photo across the top, label/title/text below."""
        img = self.canvas(entry)
        path = ROOT / entry.get("photo", "")
        if not entry.get("photo") or not path.is_file():
            raise FileNotFoundError(f"Photo not found for {day}: {entry.get('photo')}")
        ph_h = int(self.H * 0.56)
        photo = ImageOps.fit(Image.open(path).convert("RGB"), (self.W, ph_h), Image.LANCZOS)
        # darken the top so the logo stays readable
        top_shade = Image.new("L", (1, ph_h))
        for yy in range(ph_h):
            top_shade.putpixel((0, yy), int(200 * max(0.0, 1 - yy / (ph_h * 0.35))))
        dark = Image.new("RGB", (self.W, ph_h), self.c["background"])
        photo = Image.composite(dark, photo, top_shade.resize((self.W, ph_h)))
        # fade the bottom of the photo into the background
        mask = Image.new("L", (1, ph_h))
        for yy in range(ph_h):
            t = yy / ph_h
            mask.putpixel((0, yy), int(255 * min(1.0, max(0.0, (1 - t) / 0.4))))
        img.paste(photo, (0, 0), mask.resize((self.W, ph_h)))

        d = ImageDraw.Draw(img)
        inner = self.W - 2 * self.margin
        y = ph_h - 40
        if entry.get("label"):
            self.pill(d, fill(entry["label"], self.cfg, day).upper(), y)
            y += 105
        title = fill(entry.get("title", ""), self.cfg, day)
        if title:
            f, lines, size = self.fit(d, title, "bold", inner, 190, 76)
            y = self.block(d, lines, f, size, y, self.c["text"], align="left", spacing=1.15) + 20
        body = fill(entry.get("text", ""), self.cfg, day)
        if body:
            f, lines, size = self.fit(d, body, "regular", inner, int(self.H * 0.87) - y, 42, spacing=1.4)
            self.block(d, lines, f, size, y, self.c["muted"], align="left", spacing=1.4)
        self.frame(img, day)
        return img

    def render(self, entry, day):
        template = entry.get("template", "tip")
        if template not in ("quote", "tip", "announcement", "photo"):
            raise ValueError(f"Unknown template '{template}' for {day}")
        return getattr(self, template)(entry, day)


def render_day(day, cfg, calendar, folder):
    entry, source = entry_for(day, calendar)
    if entry is None:
        print(f"{day}: nothing planned and no evergreen posts - skipping")
        return None, None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day.isoformat()}.jpg"
    designed = next((f for ext in ("png", "jpg", "jpeg") if (f := CANVA / f"{day.isoformat()}.{ext}").exists()), None)
    if designed:
        # A Canva design exists for this day: post it instead of drawing one.
        source = f"Canva: {designed.name}"
        image = ImageOps.exif_transpose(Image.open(designed)).convert("RGB")
        # Instagram rejects anything taller than 4:5, so trim it to the configured size (centre crop).
        image = ImageOps.fit(image, tuple(cfg.get("image_size", (1080, 1350))), Image.LANCZOS)
    else:
        image = Painter(cfg).render(entry, day)
    image.save(path, "JPEG", quality=92)  # Instagram requires JPEG
    caption = build_caption(entry, cfg, day)
    path.with_suffix(".txt").write_text(caption, encoding="utf-8")
    print(f"{day}: rendered {entry.get('template')} ({source}) -> {path.relative_to(ROOT)}")
    return path, caption


# ----------------------------------------------------------------------------- Instagram API

class Instagram:
    def __init__(self, version):
        self.user_id = os.environ.get("IG_USER_ID", "").strip()
        self.token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
        if not self.user_id or not self.token:
            sys.exit("IG_USER_ID and IG_ACCESS_TOKEN environment variables are required.")
        self.base = f"https://graph.facebook.com/{version}"

    def call(self, method, path, **params):
        params["access_token"] = self.token
        r = requests.request(method, f"{self.base}/{path}", params=params if method == "GET" else None,
                             data=params if method != "GET" else None, timeout=60)
        body = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in body:
            err = body.get("error", {})
            raise RuntimeError(f"Instagram API error ({r.status_code}): {err.get('message', r.text)}")
        return body

    def account(self):
        return self.call("GET", self.user_id, fields="username,name,media_count")

    def publish(self, image_url, caption):
        container = self.call("POST", f"{self.user_id}/media", image_url=image_url, caption=caption)["id"]
        for _ in range(30):  # wait until Instagram has fetched and processed the image
            status = self.call("GET", container, fields="status_code,status").get("status_code")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Media container {container} failed with status {status}")
            time.sleep(5)
        else:
            raise RuntimeError("Timed out waiting for Instagram to process the image")
        media_id = self.call("POST", f"{self.user_id}/media_publish", creation_id=container)["id"]
        return self.call("GET", media_id, fields="permalink").get("permalink", media_id)


# ----------------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["preview", "render", "publish", "check"])
    ap.add_argument("--date", default="today")
    ap.add_argument("--days", type=int, default=7, help="preview: number of days to render")
    ap.add_argument("--image-url", help="publish: public URL of the rendered image")
    args = ap.parse_args()

    cfg, calendar = load_json("config.json"), load_json("calendar.json")
    day = resolve_date(args.date, cfg.get("timezone", "UTC"))

    if args.command == "preview":
        for i in range(args.days):
            render_day(day + timedelta(days=i), cfg, calendar, PREVIEW)
        print(f"Open the images in {PREVIEW.relative_to(ROOT)}/ to review them.")

    elif args.command == "render":
        if (POSTS / f"{day.isoformat()}.posted.json").exists():
            print(f"{day}: already published - nothing to render")
            sys.exit(0)
        path, _ = render_day(day, cfg, calendar, POSTS)
        if path is None:
            sys.exit(0)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"date={day.isoformat()}\nimage={path.relative_to(ROOT)}\n")

    elif args.command == "publish":
        log = POSTS / f"{day.isoformat()}.posted.json"
        if log.exists():
            print(f"{day}: already published ({json.loads(log.read_text())['permalink']}) - skipping")
            return
        if not args.image_url:
            sys.exit("--image-url is required for publish")
        caption_file = POSTS / f"{day.isoformat()}.txt"
        caption = caption_file.read_text(encoding="utf-8") if caption_file.exists() else build_caption(entry_for(day, calendar)[0], cfg, day)
        permalink = Instagram(cfg.get("graph_api_version", "v23.0")).publish(args.image_url, caption)
        log.write_text(json.dumps({"date": day.isoformat(), "permalink": permalink,
                                   "published_at": datetime.utcnow().isoformat() + "Z"}, indent=2))
        print(f"{day}: published -> {permalink}")

    elif args.command == "check":
        info = Instagram(cfg.get("graph_api_version", "v23.0")).account()
        print(f"Connected to @{info.get('username')} ({info.get('media_count')} posts). Credentials work.")


if __name__ == "__main__":
    main()
