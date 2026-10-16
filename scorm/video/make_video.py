"""Render the "Le phishing en 2 minutes" awareness video.

Runs inside the vidi-scorm-video image (see Dockerfile / build.sh):
  python3 make_video.py <out_dir>
Produces <out_dir>/phishing.mp4, phishing.vtt (French subtitles) and phishing-poster.jpg.

Each scene is a list of narration segments. Every segment is synthesised separately
(piper, French voice) so the visual elements attached to it appear exactly when the
narrator starts talking about them, and the subtitles share the same timing.
"""

import math
import os
import re
import subprocess
import sys
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 25
PIPER = ["/opt/piper/bin/piper", "-m", "/voices/fr_FR-siwis-medium.onnx"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

BG = (13, 27, 45)
CARD = (24, 42, 66)
INK = (236, 241, 247)
MUTED = (148, 166, 189)
ACCENT = (56, 189, 178)
ALERT = (239, 83, 80)
WARN = (255, 179, 0)
OK = (102, 187, 106)
PAPER = (250, 251, 253)
PAPER_INK = (33, 41, 54)

SEGMENT_GAP = 0.35  # silence between two narration segments
SCENE_LEAD = 0.5  # silence before the first segment of a scene
SCENE_TAIL = 0.9  # silence after the last segment of a scene
FADE = 0.45  # element reveal duration
TTS_FIXES = [(r"\be-mails\b", "imèles"), (r"\be-mail\b", "imèle")]

_fonts = {}


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_M if mono else FONT_B if bold else FONT, size)
    return _fonts[key]


def wrap(text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        cand = f"{line} {word}".strip()
        if fnt.getlength(cand) <= width:
            line = cand
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def text_block(d, xy, text, fnt, fill, width, spacing=1.3, anchor_center=False):
    x, y = xy
    for line in wrap(text, fnt, width):
        if anchor_center:
            d.text((x - fnt.getlength(line) / 2, y), line, font=fnt, fill=fill)
        else:
            d.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size * spacing
    return y


def ease(a):
    return 1 - (1 - a) ** 3


def reveal(img, t, start, draw_fn):
    """Draw an element that fades in and slides up from `start` (seconds)."""
    a = (t - start) / FADE
    if a <= 0:
        return
    if a >= 1:
        draw_fn(ImageDraw.Draw(img), 0)
        return
    a = ease(a)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), int((1 - a) * 24))
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    img.alpha_composite(layer)


def heading(d, text, dy=0, color=ACCENT):
    d.rectangle((80, 70 + dy, 88, 118 + dy), fill=color)
    d.text((108, 66 + dy), text, font=font(44, bold=True), fill=INK)


def pill(d, x, y, text, fg, bg, size=24):
    f = font(size, bold=True)
    w = f.getlength(text) + 36
    d.rounded_rectangle((x, y, x + w, y + size + 22), radius=(size + 22) // 2, fill=bg)
    d.text((x + 18, y + 9), text, font=f, fill=fg)
    return w


def badge(d, cx, cy, n, color=ALERT, r=22):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    f = font(int(r * 1.1), bold=True)
    s = str(n)
    d.text((cx - f.getlength(s) / 2, cy - f.size * 0.62), s, font=f, fill=(255, 255, 255))


def envelope(d, cx, cy, w, color, dy=0):
    h = w * 0.66
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2 + dy, cx + w / 2, cy + h / 2 + dy
    d.rounded_rectangle((x0, y0, x1, y1), radius=10, outline=color, width=8)
    d.line((x0 + 8, y0 + 8, cx, cy + dy + 10, x1 - 8, y0 + 8), fill=color, width=8, joint="curve")


def hook(d, cx, top, length, color, dy=0):
    """A fishing line ending with a hook, hanging from `top`."""
    bottom = top + length + dy
    d.line((cx, top, cx, bottom), fill=color, width=5)
    r = 26
    d.arc((cx - 2 * r, bottom - r, cx, bottom + r), 0, 180, fill=color, width=7)
    d.polygon([(cx - 2 * r - 4, bottom), (cx - 2 * r + 10, bottom), (cx - 2 * r + 3, bottom - 22)], fill=color)


# --------------------------------------------------------------------------- scenes


def scene_title(img, t, s):
    d = ImageDraw.Draw(img)
    pulse = (math.sin(t * 2.2) + 1) / 2
    hook(d, 640, 0, 150, WARN, dy=int(pulse * 12))
    reveal(img, t, s[0], lambda d, dy: envelope(d, 610, 290, 190, INK, dy))
    reveal(
        img, t, s[0] + 0.3,
        lambda d, dy: d.text((640 - font(76, True).getlength("Le phishing") / 2, 400 + dy),
                             "Le phishing", font=font(76, True), fill=INK),
    )
    reveal(
        img, t, s[1],
        lambda d, dy: text_block(d, (640, 505 + dy), "Le reconnaître en 2 minutes",
                                 font(34), MUTED, 1000, anchor_center=True),
    )
    reveal(
        img, t, s[1] + 0.4,
        lambda d, dy: text_block(d, (640, 580 + dy), "REPÉRER  ·  VÉRIFIER  ·  SIGNALER",
                                 font(26, True), ACCENT, 1000, anchor_center=True),
    )


def scene_definition(img, t, s):
    reveal(img, t, s[0], lambda d, dy: heading(d, "Qu'est-ce que le phishing ?", dy))
    reveal(
        img, t, s[0] + 0.3,
        lambda d, dy: text_block(d, (108, 150 + dy),
                                 "Un attaquant se fait passer pour quelqu'un de confiance.",
                                 font(32), INK, 1060),
    )
    who = ["Votre banque", "Un fournisseur", "Le service informatique", "Votre direction"]
    x = 108
    for i, label in enumerate(who):
        reveal(img, t, s[1] + i * 0.55, lambda d, dy, x=x, label=label: pill(d, x, 230 + dy, label, BG, WARN))
        x += font(24, True).getlength(label) + 36 + 18
    goals = [("Cliquer", "sur un lien piégé"), ("Ouvrir", "une pièce jointe infectée"), ("Saisir", "ses identifiants")]
    for i, (big, small) in enumerate(goals):
        x0 = 108 + i * 360

        def card(d, dy, x0=x0, big=big, small=small, i=i):
            d.rounded_rectangle((x0, 340 + dy, x0 + 330, 560 + dy), radius=18, fill=CARD)
            badge(d, x0 + 46, 392 + dy, i + 1, ALERT)
            d.text((x0 + 30, 440 + dy), big, font=font(40, True), fill=INK)
            text_block(d, (x0 + 30, 495 + dy), small, font(24), MUTED, 280)

        reveal(img, t, s[2] + 0.9 + i * 0.7, card)
    reveal(
        img, t, s[2],
        lambda d, dy: d.text((108, 300 + dy), "Son objectif : vous faire…", font=font(26, True), fill=ACCENT),
    )


EMAIL_BOX = (80, 150, 760, 650)


def draw_email(d, dy=0):
    x0, y0, x1, y1 = EMAIL_BOX
    y0 += dy
    y1 += dy
    d.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=PAPER)
    d.rounded_rectangle((x0, y0, x1, y0 + 44), radius=14, fill=(226, 231, 238))
    d.rectangle((x0, y0 + 30, x1, y0 + 44), fill=(226, 231, 238))
    for i, c in enumerate([(239, 83, 80), (255, 179, 0), (102, 187, 106)]):
        d.ellipse((x0 + 18 + i * 24, y0 + 15, x0 + 32 + i * 24, y0 + 29), fill=c)
    f, fb = font(21), font(21, True)
    d.text((x0 + 28, y0 + 64), "De :", font=fb, fill=PAPER_INK)
    d.text((x0 + 90, y0 + 64), "Support Informatique <support@monentreprise-helpdesk.com>", font=font(18), fill=PAPER_INK)
    d.text((x0 + 28, y0 + 98), "À :", font=fb, fill=PAPER_INK)
    d.text((x0 + 90, y0 + 98), "vous@monentreprise.fr", font=f, fill=PAPER_INK)
    d.text((x0 + 28, y0 + 132), "Objet :", font=fb, fill=PAPER_INK)
    d.text((x0 + 120, y0 + 132), "URGENT – Votre mot de passe expire", font=fb, fill=(183, 28, 28))
    d.line((x0 + 28, y0 + 172, x1 - 28, y0 + 172), fill=(214, 219, 226), width=2)
    y = y0 + 192
    d.text((x0 + 28, y), "Cher utilisateur,", font=f, fill=PAPER_INK)
    y = text_block(
        d, (x0 + 28, y + 40),
        "Votre mot de passe expire aujourd'hui. Sans action de votre part dans l'heure, "
        "votre compte sera définitivement bloqué.",
        f, PAPER_INK, x1 - x0 - 56,
    )
    bx, by = x0 + 28, y + 18
    d.rounded_rectangle((bx, by, bx + 350, by + 52), radius=8, fill=(25, 118, 210))
    d.text((bx + 20, by + 14), "Conserver mon mot de passe", font=font(19, True), fill=(255, 255, 255))
    d.text((x0 + 28, by + 80), "L'équipe Support", font=f, fill=PAPER_INK)


# Highlight rectangles on the email (absolute coordinates, matching draw_email).
_X, _Y = EMAIL_BOX[0], EMAIL_BOX[1]
HL = {
    "from": [(_X + 84, _Y + 58, EMAIL_BOX[2] - 14, _Y + 92)],
    "urgency": [(_X + 112, _Y + 126, _X + 560, _Y + 162), (_X + 18, _Y + 226, EMAIL_BOX[2] - 18, _Y + 318)],
    "link": [(_X + 18, _Y + 322, _X + 388, _Y + 394)],
    "generic": [(_X + 18, _Y + 186, _X + 210, _Y + 220)],
}
FLAGS = [
    ("from", "Expéditeur douteux", "Le domaine n'est pas celui de l'entreprise"),
    ("urgency", "Urgence, menace", "« dans l'heure », « bloqué »"),
    ("link", "Lien trompeur", "L'adresse réelle mène ailleurs"),
    ("generic", "Ton impersonnel", "« Cher utilisateur », demande inhabituelle"),
]


def scene_email(img, t, s):
    reveal(img, t, s[0], lambda d, dy: heading(d, "Exemple : repérez les signaux", dy, ALERT))
    reveal(img, t, s[0] + 0.4, lambda d, dy: draw_email(d, dy))
    for i, (key, title, sub) in enumerate(FLAGS):
        start = s[i + 1]
        box = HL[key]

        def mark(d, dy, box=box, i=i):
            for b in box:
                d.rounded_rectangle(b, radius=8, outline=ALERT, width=4)
            badge(d, box[0][2], box[0][1], i + 1, r=18)

        reveal(img, t, start, mark)

        def label(d, dy, i=i, title=title, sub=sub):
            y = 160 + i * 124 + dy
            d.rounded_rectangle((800, y, 1200, y + 114), radius=14, fill=CARD)
            badge(d, 838, y + 34, i + 1, r=20)
            d.text((872, y + 18), title, font=font(26, True), fill=INK)
            text_block(d, (822, y + 60), sub, font(18), MUTED, 360)

        reveal(img, t, start + 0.2, label)
    # Hover tooltip revealing the real URL of the button.
    if t >= s[3] + 0.8:

        def tip(d, dy):
            link = HL["link"][0]
            x, y = link[0] + 90, link[3] + 6 + dy
            d.polygon([(x + 30, y), (x + 44, y + 14), (x + 16, y + 14)], fill=(33, 33, 33))
            d.rounded_rectangle((x, y + 14, x + 520, y + 54), radius=8, fill=(33, 33, 33))
            d.text((x + 14, y + 24), "http://monentreprise.login-verif.co/reset", font=font(19, mono=True), fill=WARN)
            # mouse cursor
            cx, cy = link[0] + 200, link[1] + 34
            d.polygon([(cx, cy), (cx, cy + 30), (cx + 8, cy + 23), (cx + 14, cy + 36), (cx + 19, cy + 33),
                       (cx + 13, cy + 21), (cx + 23, cy + 21)], fill=(255, 255, 255), outline=(0, 0, 0))

        reveal(img, t, s[3] + 0.8, tip)


def scene_variants(img, t, s):
    reveal(img, t, s[0], lambda d, dy: heading(d, "Pas seulement par e-mail", dy, WARN))
    cards = [
        ("SMS", "Smishing", "Faux colis, fausse amende, faux remboursement…"),
        ("Téléphone", "Vishing", "Faux technicien, faux conseiller bancaire…"),
        ("Ciblé", "Fraude au président", "Un faux dirigeant exige un virement urgent et confidentiel."),
    ]
    for i, (chip, title, sub) in enumerate(cards):
        x0 = 80 + i * 380

        def card(d, dy, x0=x0, chip=chip, title=title, sub=sub):
            d.rounded_rectangle((x0, 190 + dy, x0 + 350, 560 + dy), radius=20, fill=CARD)
            pill(d, x0 + 28, 222 + dy, chip, BG, WARN)
            d.text((x0 + 28, 300 + dy), title, font=font(34 if len(title) < 12 else 26, True), fill=INK)
            text_block(d, (x0 + 28, 370 + dy), sub, font(24), MUTED, 300)

        reveal(img, t, s[i + 1], card)
    reveal(
        img, t, s[3] + 1.5,
        lambda d, dy: text_block(d, (640, 600 + dy), "Mêmes ressorts : confiance, urgence, secret.",
                                 font(28, True), ACCENT, 1100, anchor_center=True),
    )


def scene_reflexes(img, t, s):
    reveal(img, t, s[0], lambda d, dy: heading(d, "Les 3 bons réflexes", dy, OK))
    steps = [
        ("STOP", ALERT, "Je ne clique pas, je n'ouvre rien, je ne réponds pas."),
        ("VÉRIFIER", WARN, "Je contacte l'expéditeur par un autre canal connu."),
        ("SIGNALER", OK, "Je transfère le message au service sécurité."),
    ]
    for i, (word, color, sub) in enumerate(steps):
        x0 = 80 + i * 380

        def step(d, dy, x0=x0, word=word, color=color, sub=sub, i=i):
            d.rounded_rectangle((x0, 180 + dy, x0 + 350, 560 + dy), radius=20, fill=CARD)
            d.rounded_rectangle((x0, 180 + dy, x0 + 350, 196 + dy), radius=8, fill=color)
            d.ellipse((x0 + 130, 230 + dy, x0 + 220, 320 + dy), outline=color, width=6)
            f = font(44, True)
            d.text((x0 + 175 - f.getlength(str(i + 1)) / 2, 248 + dy), str(i + 1), font=f, fill=color)
            fw = font(38, True)
            d.text((x0 + 175 - fw.getlength(word) / 2, 350 + dy), word, font=fw, fill=INK)
            text_block(d, (x0 + 175, 420 + dy), sub, font(23), MUTED, 300, anchor_center=True)

        reveal(img, t, s[i + 1], step)


def scene_clicked(img, t, s):
    reveal(img, t, s[0], lambda d, dy: heading(d, "Vous avez cliqué ? Agissez vite.", dy, WARN))
    items = [
        (s[1], "Prévenez immédiatement le support informatique"),
        (s[1] + 2.6, "Changez votre mot de passe si vous l'avez saisi"),
        (s[2], "Signaler n'est jamais une faute : cela limite les dégâts"),
    ]
    for i, (start, text) in enumerate(items):

        def row(d, dy, i=i, text=text):
            y = 190 + i * 125 + dy
            d.rounded_rectangle((108, y, 1172, y + 100), radius=16, fill=CARD)
            d.ellipse((136, y + 26, 184, y + 74), fill=OK)
            d.line((148, y + 50, 158, y + 61, 174, y + 39), fill=BG, width=6)
            d.text((214, y + 32), text, font=font(30), fill=INK)

        reveal(img, t, start, row)


def scene_outro(img, t, s):
    d = ImageDraw.Draw(img)
    reveal(
        img, t, s[0],
        lambda d, dy: text_block(d, (640, 200 + dy), "En cas de doute", font(40), MUTED, 1100, anchor_center=True),
    )
    words = [("STOP", ALERT), ("VÉRIFIER", WARN), ("SIGNALER", OK)]
    f = font(66, True)
    sep = 60
    total = sum(f.getlength(w) for w, _ in words) + sep * 2
    x = 640 - total / 2
    for i, (w, c) in enumerate(words):
        reveal(img, t, s[0] + 1.3 + i * 0.6, lambda d, dy, x=x, w=w, c=c: d.text((x, 280 + dy), w, font=f, fill=c))
        x += f.getlength(w) + sep
    reveal(
        img, t, s[1],
        lambda d, dy: text_block(d, (640, 450 + dy), "Vous êtes le meilleur rempart contre le phishing.",
                                 font(34, True), INK, 1100, anchor_center=True),
    )


SCENES = [
    (scene_title, [
        "Le phishing, ou hameçonnage, est la première porte d'entrée des cyberattaques en entreprise.",
        "En deux minutes, apprenez à le reconnaître.",
    ]),
    (scene_definition, [
        "Le principe est simple : un attaquant se fait passer pour quelqu'un de confiance.",
        "Votre banque, un fournisseur, le service informatique, ou même votre direction.",
        "Son objectif : vous faire cliquer sur un lien, ouvrir une pièce jointe, ou saisir vos identifiants.",
    ]),
    (scene_email, [
        "Prenons un exemple. Ce message semble venir du support informatique.",
        "Premier signal : l'adresse de l'expéditeur. Le domaine n'est pas celui de l'entreprise.",
        "Deuxième signal : l'urgence. On vous presse d'agir dans l'heure, sinon votre compte sera bloqué.",
        "Troisième signal : le lien. En le survolant sans cliquer, on découvre une adresse qui n'a rien à voir.",
        "Enfin, une formule impersonnelle et une demande inhabituelle doivent vous alerter.",
    ]),
    (scene_variants, [
        "Attention, le phishing ne passe pas que par e-mail.",
        "Par SMS, on parle de smishing : faux colis, fausse amende, faux remboursement.",
        "Par téléphone, c'est le vishing : un faux technicien, ou un faux conseiller bancaire.",
        "Et l'attaque peut être ciblée : un faux dirigeant qui réclame un virement urgent et confidentiel.",
    ]),
    (scene_reflexes, [
        "Face à un message suspect, adoptez trois réflexes.",
        "Stop : ne cliquez pas, n'ouvrez rien, ne répondez pas.",
        "Vérifiez : contactez l'expéditeur par un autre canal, avec un numéro que vous connaissez déjà.",
        "Signalez : transférez le message au service sécurité, ou utilisez le bouton de signalement.",
    ]),
    (scene_clicked, [
        "Et si vous avez déjà cliqué ? Pas de panique, mais agissez vite.",
        "Prévenez immédiatement le support informatique, et changez votre mot de passe si vous l'avez saisi.",
        "Signaler rapidement n'est jamais une faute : c'est ce qui permet de limiter les dégâts.",
    ]),
    (scene_outro, [
        "Retenez bien : en cas de doute, stop, vérifiez, signalez.",
        "Vous êtes le meilleur rempart contre le phishing.",
    ]),
]


# --------------------------------------------------------------------------- audio


def tts(text, path):
    say = text
    for pat, rep in TTS_FIXES:
        say = re.sub(pat, rep, say)
    subprocess.run(PIPER + ["-f", path], input=say.encode(), check=True, capture_output=True)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate(), w.getparams()


def build_timeline(tmp):
    """Synthesise every segment; return scenes with absolute timings and the audio track."""
    timeline, cues, clips = [], [], []
    t, params = 0.0, None
    for si, (fn, segments) in enumerate(SCENES):
        start = t
        t += SCENE_LEAD
        seg_starts = []
        for gi, text in enumerate(segments):
            path = os.path.join(tmp, f"s{si}_{gi}.wav")
            dur, params = tts(text, path)
            seg_starts.append(t - start)
            clips.append((t, path))
            cues.append((t, t + dur, text))
            t += dur + SEGMENT_GAP
        t += SCENE_TAIL - SEGMENT_GAP
        timeline.append((start, t, fn, seg_starts))
    return timeline, cues, clips, params, t


def write_audio(clips, params, total, path):
    rate, width = params.framerate, params.sampwidth * params.nchannels
    buf = bytearray(int(total * rate) * width)
    for at, clip in clips:
        with wave.open(clip) as w:
            data = w.readframes(w.getnframes())
        off = int(at * rate) * width
        buf[off:off + len(data)] = data
    with wave.open(path, "wb") as out:
        out.setparams(params)
        out.writeframes(bytes(buf))


def vtt_time(x):
    h, rem = divmod(x, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for i, (a, b, text) in enumerate(cues, 1):
            f.write(f"{i}\n{vtt_time(a)} --> {vtt_time(b)}\n{text}\n\n")


# --------------------------------------------------------------------------- video


def render_frame(timeline, t):
    img = Image.new("RGBA", (W, H), BG + (255,))
    for start, end, fn, seg_starts in timeline:
        if start <= t < end:
            local = t - start
            fn(img, local, seg_starts)
            # progress bar + fade to/from black at scene boundaries
            d = ImageDraw.Draw(img)
            d.rectangle((0, H - 6, int(W * t / timeline[-1][1]), H), fill=ACCENT)
            fade = min(1.0, local / 0.3, (end - t) / 0.3)
            if fade < 1:
                black = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - fade))))
                img.alpha_composite(black)
            break
    return img.convert("RGB")


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        timeline, cues, clips, params, total = build_timeline(tmp)
        if os.environ.get("PREVIEW"):
            # PREVIEW=1 → one PNG per scene, fully revealed, instead of the video.
            for i, (start, end, _fn, _segs) in enumerate(timeline):
                render_frame(timeline, end - 0.35).save(os.path.join(out_dir, f"preview-{i}.png"))
            return
        audio = os.path.join(tmp, "narration.wav")
        write_audio(clips, params, total, audio)
        write_vtt(cues, os.path.join(out_dir, "phishing.vtt"))
        print(f"duration: {total:.1f}s, {len(cues)} cues", flush=True)

        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
             "-i", audio,
             "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-shortest", "-movflags", "+faststart",
             os.path.join(out_dir, "phishing.mp4")],
            stdin=subprocess.PIPE,
        )
        n = int(total * FPS)
        for i in range(n):
            ff.stdin.write(render_frame(timeline, i / FPS).tobytes())
        ff.stdin.close()
        if ff.wait() != 0:
            sys.exit("ffmpeg failed")

        # Poster: the title scene once fully revealed.
        first = timeline[0]
        render_frame(timeline, first[3][-1] + 1.5).save(os.path.join(out_dir, "phishing-poster.jpg"), quality=85)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
