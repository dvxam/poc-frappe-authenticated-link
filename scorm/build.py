#!/usr/bin/env python3
"""Package every course under courses/ as a SCORM 1.2 zip in dist/.

For each courses/<name>/:
  - copies the course files + shared/ (player) into build/<name>/ (handy for local preview),
  - writes imsmanifest.xml (single SCO, launch = start.html, see LAUNCH, mastery from <body data-mastery>),
  - zips it to dist/<name>.zip,
  - runs the same content checks Frappe LMS applies on upload, so a package is
    never rejected there for an inline handler or an eval().

Standard library only:  python3 scorm/build.py
"""

import html
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COURSES, SHARED = ROOT / "courses", ROOT / "shared"
BUILD, DIST = ROOT / "build", ROOT / "dist"

# Mirrors lms.lms.api.check_for_malicious_code (Frappe LMS).
FRAPPE_SUSPICIOUS = [
    r'on(click|load|mouseover|error|submit|focus|blur|change|keyup|keydown|keypress|resize)=".*?"',
    r'<script.*?src=["\']http',
    r"eval\(",
    r"Function\(",
    r"(btoa|atob)\(",
    r"<!ENTITY",
    r"<\?xml-stylesheet .*?>",
]
STORED = {".mp4", ".jpg", ".jpeg", ".png", ".webp", ".zip"}  # already compressed

# Launch file inside the package. Not index.html: Frappe's nginx rewrites ".../<chapter>/index.html"
# to ".../<chapter>" (no trailing slash), so every relative URL (shared/player.css, media/…) would
# resolve one folder too high and 403. ".../<chapter>/start.html" only loses its extension
# (".../<chapter>/start"), which keeps relative URLs inside the package folder.
LAUNCH = "start.html"

MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{ident}" version="1.0"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="{ident}-org">
    <organization identifier="{ident}-org">
      <title>{title}</title>
      <item identifier="{ident}-item" identifierref="{ident}-sco" isvisible="true">
        <title>{title}</title>
        <adlcp:masteryscore>{mastery}</adlcp:masteryscore>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="{ident}-sco" type="webcontent" adlcp:scormtype="sco" href="{launch}">
{files}
    </resource>
  </resources>
</manifest>
"""


def fail(msg):
    sys.exit(f"error: {msg}")


def build(course: Path) -> Path:
    stage = BUILD / course.name
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(course, stage)
    shutil.copytree(SHARED, stage / "shared")

    index = (stage / "index.html").read_text(encoding="utf-8")
    (stage / "index.html").rename(stage / LAUNCH)
    title = re.search(r"<title>(.*?)</title>", index, re.S)
    mastery = re.search(r'data-mastery="(\d+)"', index)
    if not title or not mastery:
        fail(f"{course.name}: index.html needs a <title> and <body data-mastery>")

    # Every local src/href referenced by the page must ship in the package.
    for ref in re.findall(r'(?:src|href|poster)="([^"#:]+)"', index):
        if not (stage / ref).is_file():
            fail(f"{course.name}: index.html references missing file {ref}")

    files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file())
    (stage / "imsmanifest.xml").write_text(
        MANIFEST.format(
            ident=f"vidi-{course.name}",
            title=html.escape(html.unescape(title.group(1).strip())),
            mastery=mastery.group(1),
            launch=LAUNCH,
            files="\n".join(f'      <file href="{html.escape(f)}"/>' for f in files),
        ),
        encoding="utf-8",
    )

    for p in stage.rglob("*"):
        if p.suffix in {".html", ".js", ".xml"}:
            text = p.read_text(encoding="utf-8", errors="ignore")
            for pat in FRAPPE_SUSPICIOUS:
                if re.search(pat, text):
                    fail(f"{p.relative_to(BUILD)} matches Frappe LMS upload filter {pat!r}")

    DIST.mkdir(exist_ok=True)
    out = DIST / f"{course.name}.zip"
    with zipfile.ZipFile(out, "w") as zf:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                method = zipfile.ZIP_STORED if p.suffix.lower() in STORED else zipfile.ZIP_DEFLATED
                zf.write(p, p.relative_to(stage).as_posix(), compress_type=method)
    return out


def main():
    courses = sorted(p for p in COURSES.iterdir() if (p / "index.html").is_file())
    if not courses:
        fail("no course found in courses/")
    for course in courses:
        out = build(course)
        print(f"{out.relative_to(ROOT.parent)}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
