"""Line-art illustrations in the style of the IGCC emblem (thin facet lines).

Each function draws onto a transparent square of `size` px in `color` and returns an RGBA image.
Drawing happens at 4x and is scaled down for smooth lines.
"""

import math

from PIL import Image, ImageDraw

SS = 4  # supersampling factor


def _canvas(size):
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), size * SS


def _done(img, size):
    return img.resize((size, size), Image.LANCZOS)


def _diamond_profile(d, x0, y0, w, color, lw):
    """Side view of a round brilliant diamond. Returns the culet point."""
    P = lambda fx, fy: (x0 + fx * w, y0 + fy * w)
    crown, girdle, pav = 0.16, 0.03, 0.43
    table = [P(0.22, 0), P(0.78, 0)]
    gt = [P(0, crown), P(1, crown)]
    gb = [P(0, crown + girdle), P(1, crown + girdle)]
    culet = P(0.5, crown + girdle + pav)

    d.line([table[0], table[1], gt[1], gb[1], culet, gb[0], gt[0], table[0]], fill=color, width=lw, joint="curve")
    d.line([gt[0], gt[1]], fill=color, width=lw)
    d.line([gb[0], gb[1]], fill=color, width=lw)
    # crown facets: zig-zag between table edge and girdle
    top = [0.22, 0.36, 0.5, 0.64, 0.78]
    bot = [0, 0.14, 0.29, 0.43, 0.57, 0.71, 0.86, 1]
    for i, fx in enumerate(top):
        for gx in bot:
            if abs(gx - fx) <= 0.23 and not (fx in (0.22, 0.78) and abs(gx - fx) > 0.2):
                d.line([P(fx, 0), P(gx, crown)], fill=color, width=lw)
    # pavilion mains to culet and lower-girdle facets
    for gx in (0.14, 0.32, 0.5, 0.68, 0.86):
        d.line([P(gx, crown + girdle), culet], fill=color, width=lw)
    for gx in (0.07, 0.93):
        mid = P(0.5 + (gx - 0.5) * 0.3, crown + girdle + pav * 0.7)
        d.line([P(gx, crown + girdle), mid], fill=color, width=lw)
    return culet


def diamond(size, color):
    img, d, S = _canvas(size)
    lw = max(2, S // 170)
    w = S * 0.86
    _diamond_profile(d, (S - w) / 2, S * 0.24, w, color, lw)
    return _done(img, size)


def brilliance(size, color):
    """Diamond with light entering and returning through the table."""
    img, d, S = _canvas(size)
    lw = max(2, S // 170)
    w = S * 0.62
    x0, y0 = (S - w) / 2, S * 0.46
    _diamond_profile(d, x0, y0, w, color, lw)
    cx = S / 2
    for i, ang in enumerate(range(-60, 61, 20)):
        a = math.radians(ang - 90)
        r0, r1 = S * 0.1, S * (0.28 if i % 2 else 0.34)
        sx, sy = cx, y0 - S * 0.03
        d.line([(sx + r0 * math.cos(a), sy + r0 * math.sin(a)),
                (sx + r1 * math.cos(a), sy + r1 * math.sin(a))], fill=color, width=lw * (2 if i % 2 == 0 else 1))
    # sparkles
    for (fx, fy, r) in ((0.16, 0.2, 0.035), (0.84, 0.26, 0.03), (0.12, 0.62, 0.025)):
        x, y, rr = S * fx, S * fy, S * r
        d.line([(x - rr, y), (x + rr, y)], fill=color, width=lw)
        d.line([(x, y - rr), (x, y + rr)], fill=color, width=lw)
    return _done(img, size)


def loupe(size, color):
    """Jeweller's loupe examining a diamond."""
    img, d, S = _canvas(size)
    lw = max(2, S // 170)
    cx, cy, r = S * 0.42, S * 0.42, S * 0.3
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw * 4)
    d.ellipse([cx - r * 0.86, cy - r * 0.86, cx + r * 0.86, cy + r * 0.86], outline=color, width=lw)
    a = math.radians(45)
    hx0, hy0 = cx + r * math.cos(a), cy + r * math.sin(a)
    hx1, hy1 = cx + S * 0.62 * math.cos(a), cy + S * 0.62 * math.sin(a)
    d.line([(hx0, hy0), (hx1, hy1)], fill=color, width=lw * 9)
    w = r * 1.15
    _diamond_profile(d, cx - w / 2, cy - w * 0.32, w, color, lw)
    return _done(img, size)


def report(size, color):
    """A grading report / certificate with a diamond and a seal."""
    img, d, S = _canvas(size)
    lw = max(2, S // 170)
    x0, y0, x1, y1 = S * 0.18, S * 0.08, S * 0.82, S * 0.92
    d.rounded_rectangle([x0, y0, x1, y1], radius=S * 0.03, outline=color, width=lw * 2)
    d.line([(x0 + S * 0.06, y0 + S * 0.09), (x1 - S * 0.06, y0 + S * 0.09)], fill=color, width=lw * 3)
    w = S * 0.26
    _diamond_profile(d, S / 2 - w / 2, y0 + S * 0.16, w, color, lw)
    y = y0 + S * 0.42
    for i in range(6):
        d.line([(x0 + S * 0.06, y), (x0 + S * 0.06 + S * 0.16, y)], fill=color, width=lw)
        d.line([(x0 + S * 0.27, y), (x1 - S * 0.06 - (S * 0.08 if i % 2 else 0), y)], fill=color, width=lw)
        y += S * 0.055
    sx, sy, sr = x1 - S * 0.12, y1 - S * 0.1, S * 0.07
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], outline=color, width=lw * 2)
    for k in range(8):
        a = math.radians(k * 45)
        d.line([(sx, sy), (sx + sr * 0.8 * math.cos(a), sy + sr * 0.8 * math.sin(a))], fill=color, width=lw)
    return _done(img, size)


def scale(size, color):
    """Balance scale with a diamond on one pan - for carat weight."""
    img, d, S = _canvas(size)
    lw = max(2, S // 170)
    cx = S / 2
    d.line([(cx, S * 0.18), (cx, S * 0.82)], fill=color, width=lw * 4)
    d.line([(cx - S * 0.18, S * 0.84), (cx + S * 0.18, S * 0.84)], fill=color, width=lw * 5)
    d.ellipse([cx - S * 0.03, S * 0.13, cx + S * 0.03, S * 0.19], outline=color, width=lw * 2)
    bx, tilt = S * 0.36, S * 0.05
    left, right = (cx - bx, S * 0.24 + tilt), (cx + bx, S * 0.24 - tilt)
    d.line([left, right], fill=color, width=lw * 3)
    for (px, top) in (left, right):
        pan_y = top + S * 0.26
        d.line([(px, top), (px - S * 0.11, pan_y)], fill=color, width=lw)
        d.line([(px, top), (px + S * 0.11, pan_y)], fill=color, width=lw)
        d.chord([px - S * 0.13, pan_y - S * 0.06, px + S * 0.13, pan_y + S * 0.06], 0, 180, outline=color, width=lw * 2)
    w = S * 0.16
    _diamond_profile(d, left[0] - w / 2, left[1] + S * 0.26 - w * 0.62, w, color, lw)
    return _done(img, size)


ILLUSTRATIONS = {
    "diamond": diamond,
    "brilliance": brilliance,
    "loupe": loupe,
    "report": report,
    "scale": scale,
}
