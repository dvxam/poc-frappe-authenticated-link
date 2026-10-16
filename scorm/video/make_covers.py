"""Render the course cover images (Frappe LMS course card / chapter illustrations).

Runs inside the vidi-scorm-video image, like make_video.py:
  python3 make_covers.py <out_dir>
Produces cover-course.png + cover-01-phishing.png, cover-02-mots-de-passe.png,
cover-03-reflexes-quotidien.png (1280x720, same palette as the video).
Drawn at 2x then downscaled, for smooth edges.
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, S = 1280, 720, 2  # S = supersampling factor
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BG_TOP, BG_BOTTOM = (16, 34, 56), (8, 18, 31)
INK = (236, 241, 247)
MUTED = (148, 166, 189)
ACCENT = (56, 189, 178)
ALERT = (239, 83, 80)
WARN = (255, 179, 0)
OK = (102, 187, 106)
CARD = (27, 48, 75)


def f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size * S)


def s(*v):
    return tuple(x * S for x in v)


def background():
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    for y in range(H * S):
        t = y / (H * S)
        d.line((0, y, W * S, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    # dotted grid, fading towards the left where the text sits
    for gx in range(0, W, 32):
        for gy in range(0, H, 32):
            a = max(0, min(1, (gx - 420) / 500))
            if a > 0:
                c = tuple(int(bg + (80 - bg) * a * 0.35) for bg in BG_TOP)
                d.ellipse(s(gx - 1.5, gy - 1.5, gx + 1.5, gy + 1.5), fill=c)
    return img


def glow(img, cx, cy, r, color, strength=0.55):
    layer = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(layer).ellipse(s(cx - r, cy - r, cx + r, cy + r), fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(r * S * 0.45))
    return Image.blend(img, Image.composite(layer, img, layer.convert("L")), strength)


def shield(d, cx, cy, w, fill, outline=None):
    h = w * 1.18
    top = cy - h / 2
    pts = [(cx, top), (cx + w / 2, top + h * 0.14), (cx + w / 2, top + h * 0.48)]
    # curved bottom: sample a quadratic curve to the tip on each side
    right = [(cx + w / 2 * (1 - t) ** 1.6, top + h * 0.48 + (h * 0.52) * t ** 0.9) for t in [i / 20 for i in range(1, 21)]]
    left = [(cx - x + cx, y) for x, y in reversed(right)]
    poly = pts + right + left + [(cx - w / 2, top + h * 0.48), (cx - w / 2, top + h * 0.14)]
    d.polygon([s(x, y) for x, y in poly], fill=fill, outline=outline)


def padlock(d, cx, cy, w, body, shackle, keyhole):
    bw, bh = w, w * 0.78
    sw = w * 0.62
    d.arc(s(cx - sw / 2, cy - bh / 2 - sw * 0.72, cx + sw / 2, cy - bh / 2 + sw * 0.28), 180, 360, fill=shackle, width=int(w * 0.13 * S))
    for x in (cx - sw / 2, cx + sw / 2):
        d.line(s(x, cy - bh / 2 - sw * 0.22, x, cy - bh / 2 + 4), fill=shackle, width=int(w * 0.13 * S))
    d.rounded_rectangle(s(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), radius=int(w * 0.14 * S), fill=body)
    r = w * 0.09
    d.ellipse(s(cx - r, cy - r * 1.6, cx + r, cy + r * 0.4), fill=keyhole)
    d.polygon([s(cx - r * 0.55, cy), s(cx + r * 0.55, cy), s(cx + r * 0.8, cy + bh * 0.26), s(cx - r * 0.8, cy + bh * 0.26)], fill=keyhole)


def envelope(d, cx, cy, w, fill, line):
    h = w * 0.64
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    k = w / 330  # stroke sizes are tuned for w=330
    d.rounded_rectangle(s(x0, y0, x1, y1), radius=int(16 * k * S), fill=fill)
    d.line([s(x0 + 10 * k, y0 + 12 * k), s(cx, cy + h * 0.08), s(x1 - 10 * k, y0 + 12 * k)], fill=line,
           width=max(2, int(9 * k * S)), joint="curve")


def hook(d, cx, top, bottom, color):
    d.line(s(cx, top, cx, bottom), fill=color, width=int(6 * S))
    r = 34
    d.arc(s(cx - 2 * r, bottom - r, cx, bottom + r), 0, 180, fill=color, width=int(9 * S))
    d.polygon([s(cx - 2 * r - 6, bottom), s(cx - 2 * r + 12, bottom), s(cx - 2 * r + 3, bottom - 30)], fill=color)


def laptop(d, cx, cy, w, frame, screen):
    h = w * 0.6
    k = w / 360  # sizes are tuned for w=360
    d.rounded_rectangle(s(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=int(14 * k * S), fill=frame)
    d.rounded_rectangle(s(cx - w / 2 + 16 * k, cy - h / 2 + 16 * k, cx + w / 2 - 16 * k, cy + h / 2 - 12 * k),
                        radius=int(6 * k * S), fill=screen)
    d.rounded_rectangle(s(cx - w * 0.62, cy + h / 2, cx + w * 0.62, cy + h / 2 + 22 * k), radius=int(11 * k * S), fill=frame)
    d.rounded_rectangle(s(cx - w * 0.1, cy + h / 2, cx + w * 0.1, cy + h / 2 + 8 * k), radius=int(4 * k * S), fill=screen)


def check(d, cx, cy, r, bg, fg):
    d.ellipse(s(cx - r, cy - r, cx + r, cy + r), fill=bg)
    d.line([s(cx - r * 0.45, cy + r * 0.02), s(cx - r * 0.1, cy + r * 0.38), s(cx + r * 0.48, cy - r * 0.36)], fill=fg, width=int(r * 0.22 * S), joint="curve")


def chip(d, x, y, text, fg, bg):
    fnt = f(20, True)
    w = fnt.getlength(text) / S + 32
    d.rounded_rectangle(s(x, y, x + w, y + 40), radius=20 * S, fill=bg)
    d.text(s(x + 16, y + 8), text, font=fnt, fill=fg)
    return w


def title_block(d, eyebrow, title_lines, subtitle, chips):
    d.text(s(80, 150), eyebrow.upper(), font=f(20, True), fill=ACCENT)
    y = 190
    size = 56  # shrink long titles so they never run into the illustration
    while max(f(size, True).getlength(l) for l in title_lines) / S > 640:
        size -= 2
    for line in title_lines:
        d.text(s(76, y), line, font=f(size, True), fill=INK)
        y += int(size * 1.22)
    y += (56 - size) * 2
    d.rectangle(s(80, y + 18, 150, y + 24), fill=ACCENT)
    y += 50
    for line in subtitle:
        d.text(s(80, y), line, font=f(25), fill=MUTED)
        y += 36
    x = 80
    for text, fg, bg in chips:
        x += chip(d, x, y + 28, text, fg, bg) + 12


def finish(img, path):
    img.resize((W, H), Image.LANCZOS).save(path, optimize=True)


# --------------------------------------------------------------------------- covers


def cover_course(out):
    img = glow(background(), 960, 360, 260, (20, 110, 110))
    d = ImageDraw.Draw(img)
    # orbiting small icons around a big shield
    for ang, color in [(-150, ALERT), (-35, WARN), (85, OK)]:
        a = math.radians(ang)
        x, y = 960 + 245 * math.cos(a), 360 + 215 * math.sin(a)
        d.ellipse(s(x - 46, y - 46, x + 46, y + 46), fill=CARD)
        d.ellipse(s(x - 46, y - 46, x + 46, y + 46), outline=color, width=4 * S)
        if color == ALERT:
            envelope(d, x, y, 52, INK, CARD)
        elif color == WARN:
            for i in range(4):
                d.ellipse(s(x - 27 + i * 18 - 5, y - 5, x - 27 + i * 18 + 5, y + 5), fill=INK)
        else:
            laptop(d, x, y - 6, 46, INK, CARD)
    d.arc(s(960 - 245, 360 - 215, 960 + 245, 360 + 215), 0, 360, fill=(45, 75, 105), width=2 * S)
    shield(d, 960, 360, 250, ACCENT)
    shield(d, 960, 364, 214, (22, 120, 116))
    padlock(d, 960, 385, 104, INK, INK, (22, 120, 116))
    title_block(
        d, "Formation obligatoire", ["Sensibilisation", "à la cybersécurité"],
        ["Les réflexes essentiels pour protéger", "vos données et celles de l'entreprise."],
        [("Phishing", BG_BOTTOM, ALERT), ("Mots de passe", BG_BOTTOM, WARN), ("Au quotidien", BG_BOTTOM, OK)],
    )
    finish(img, os.path.join(out, "cover-course.png"))


def cover_phishing(out):
    img = glow(background(), 960, 400, 240, (120, 40, 40), 0.45)
    d = ImageDraw.Draw(img)
    hook(d, 990, 0, 215, WARN)
    envelope(d, 965, 390, 330, INK, (60, 78, 104))
    # red warning badge
    d.ellipse(s(1080, 250, 1180, 350), fill=ALERT)
    fnt = f(64, True)
    d.text(s(1130 - fnt.getlength("!") / S / 2, 258), "!", font=fnt, fill=(255, 255, 255))
    # fake link bar
    d.rounded_rectangle(s(780, 560, 1180, 606), radius=10 * S, fill=CARD)
    d.text(s(798, 572), "monentreprise.fr.", font=f(18), fill=MUTED)
    d.text(s(798 + f(18).getlength("monentreprise.fr.") / S, 572), "login-verif.co", font=f(18, True), fill=ALERT)
    title_block(
        d, "Module 1", ["Reconnaître et", "déjouer le phishing"],
        ["Repérer les signaux d'alerte, lire une URL,", "réagir : Stop · Vérifier · Signaler."],
        [("Vidéo", BG_BOTTOM, ALERT), ("Exercices", INK, CARD), ("Quiz", INK, CARD)],
    )
    finish(img, os.path.join(out, "cover-01-phishing.png"))


def cover_passwords(out):
    img = glow(background(), 960, 360, 240, (120, 90, 10), 0.4)
    d = ImageDraw.Draw(img)
    padlock(d, 960, 330, 230, WARN, INK, BG_BOTTOM)
    # password field with dots + MFA phone
    d.rounded_rectangle(s(790, 520, 1130, 584), radius=14 * S, fill=CARD)
    for i in range(9):
        x = 822 + i * 30
        d.ellipse(s(x - 8, 544, x + 8, 560), fill=INK)
    d.rounded_rectangle(s(1150, 470, 1222, 600), radius=14 * S, fill=INK)
    d.rounded_rectangle(s(1158, 488, 1214, 582), radius=6 * S, fill=CARD)
    check(d, 1186, 535, 20, OK, CARD)
    title_block(
        d, "Module 2", ["Mots de passe et", "double authentification"],
        ["Phrases de passe, gestionnaire,", "MFA : verrouillez vos accès."],
        [("Testeur", BG_BOTTOM, WARN), ("Exercices", INK, CARD), ("Quiz", INK, CARD)],
    )
    finish(img, os.path.join(out, "cover-02-mots-de-passe.png"))


def cover_daily(out):
    img = glow(background(), 960, 360, 250, (30, 100, 50), 0.45)
    d = ImageDraw.Draw(img)
    laptop(d, 960, 350, 360, INK, CARD)
    shield(d, 960, 340, 110, OK)
    check(d, 960, 336, 30, OK, CARD)
    # small icons: wifi + usb
    cx, cy = 790, 580
    for r in (16, 32, 48):
        d.arc(s(cx - r, cy - r, cx + r, cy + r), 225, 315, fill=ACCENT, width=6 * S)
    d.ellipse(s(cx - 6, cy - 6, cx + 6, cy + 6), fill=ACCENT)
    ux, uy = 1130, 560
    d.rounded_rectangle(s(ux - 18, uy - 10, ux + 18, uy + 46), radius=6 * S, fill=MUTED)
    d.rectangle(s(ux - 11, uy - 28, ux + 11, uy - 10), fill=MUTED)
    d.line(s(ux - 32, uy - 32, ux + 32, uy + 50), fill=ALERT, width=7 * S)
    title_block(
        d, "Module 3", ["Les bons réflexes", "cyber au quotidien"],
        ["Poste de travail, données, déplacements,", "IA : les gestes qui protègent."],
        [("Situations", BG_BOTTOM, OK), ("Quiz", INK, CARD)],
    )
    finish(img, os.path.join(out, "cover-03-reflexes-quotidien.png"))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "covers"
    os.makedirs(out, exist_ok=True)
    for fn in (cover_course, cover_phishing, cover_passwords, cover_daily):
        fn(out)
