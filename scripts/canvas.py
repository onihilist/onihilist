#!/usr/bin/env python3
"""A tiny SVG canvas whose text is drawn as glyph outlines.

GitHub shows README images through a proxy that has none of our fonts, so every
character is converted to a reusable <path>. The SVGs then look the same on every
machine, with no <text>, <image> or <script> elements.
"""
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = Path(os.environ.get("FONT_CACHE", ROOT / ".cache" / "fonts"))
FONT_BASE_URL = "https://raw.githubusercontent.com/google/fonts/47d54ca1ebb14fd864695f1d39dc734f39017c33/ofl/"
FONT_SOURCES = {
    "JetBrainsMono.ttf": "jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
    "SourceSerif4.ttf": "sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf",
    "NotoSansJP.ttf": "notosansjp/NotoSansJP%5Bwght%5D.ttf",
    "NotoSansSymbols2.ttf": "notosanssymbols2/NotoSansSymbols2-Regular.ttf",
    "NotoSansSymbols.ttf": "notosanssymbols/NotoSansSymbols%5Bwght%5D.ttf",
}
FONT_SPECS = {
    "mono": ("JetBrainsMono.ttf", {"wght": 480}),
    "bold": ("JetBrainsMono.ttf", {"wght": 700}),
    "serif": ("SourceSerif4.ttf", {"wght": 500, "opsz": 40}),
    "jp": ("NotoSansJP.ttf", {"wght": 480}),
    "symbol": ("NotoSansSymbols2.ttf", None),
    "symbol1": ("NotoSansSymbols.ttf", {"wght": 400}),
}

# Taken from the header photo: maple crimson, vermilion, burnt orange, temple-wall white
# and near-black shadows. Light theme is white paper with red ink, dark theme is black
# lacquer with vermilion and orange. Roles, not hues, are used everywhere else
# (the role names are historical: "blue" is the directory colour, "lilac" the prompt user...).
PALETTE = {
    "light": dict(paper="#fbf8f5", panel="#f2ebe6", text="#1f1414", muted="#8a7671", line="#e9dcd5",
                  blue="#7b0a0c", lilac="#be100f", gold="#c9661c", leaf="#e0402a", mint="#d9661f",
                  red="#be100f", tag="#be100f", ink="#fff7f2", shadow="#d8c3ba",
                  accent=("#7b0a0c", "#d9381e", "#f29a4a"), lights=("#e2483a", "#f2a03a", "#9fc1c4")),
    "dark": dict(paper="#0e0a0a", panel="#181111", text="#f6f1ec", muted="#a8948e", line="#33221f",
                 blue="#ffd6c2", lilac="#ff6b4f", gold="#f5b04a", leaf="#ef5a3a", mint="#f5a04a",
                 red="#ef4a3a", tag="#d9381e", ink="#fff7f2", shadow="#000000",
                 accent=("#be100f", "#f07a3a", "#fde9d8"), lights=("#e2483a", "#f2a03a", "#9fc1c4")),
}

DURATION = 16  # seconds of one typing loop


def num(value):
    return f"{value:.3f}".rstrip("0").rstrip(".")


class Font:
    def __init__(self, filename, location):
        path = FONT_DIR / filename
        if not path.exists():
            FONT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Downloading {filename} from pinned Google Fonts sources", flush=True)
            request = Request(FONT_BASE_URL + FONT_SOURCES[filename], headers={"User-Agent": "profile-readme/1.0"})
            with urlopen(request, timeout=120) as response:
                data = response.read()
            temporary = path.with_suffix(".part")
            temporary.write_bytes(data)
            temporary.replace(path)
        self.tt = TTFont(path, lazy=True)
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt["head"].unitsPerEm
        self.glyphs = self.tt.getGlyphSet(location=location) if location else self.tt.getGlyphSet()


FONTS = {}


def resolve(char, family="mono"):
    for key in dict.fromkeys([family, "mono", "jp", "symbol", "symbol1"]):
        if key not in FONTS:
            FONTS[key] = Font(*FONT_SPECS[key])
        font = FONTS[key]
        if ord(char) in font.cmap:
            return key, font, font.cmap[ord(char)]
    raise ValueError(f"No glyph for {char!r} (U+{ord(char):04X})")


class Canvas:
    def __init__(self, theme, height, width=788, user="me", host="localhost"):
        self.theme, self.p = theme, PALETTE[theme]
        self.w, self.h = width, height
        self.user, self.host = user, host
        self.body, self.styles, self.defs, self.overlay = [], [], {}, []

    # -- primitives -------------------------------------------------------
    def add(self, markup):
        self.body.append(markup)

    def style(self, css):
        self.styles.append(css)

    def color(self, role):
        return self.p.get(role, role)

    def rect(self, x, y, w, h, fill, rx=0, extra=""):
        self.add(f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" rx="{num(rx)}" fill="{self.color(fill)}"{extra}/>')

    def line(self, x1, y1, x2, color="line", width=1, extra=""):
        self.add(f'<path d="M{num(x1)} {num(y1)}H{num(x2)}" fill="none" stroke="{self.color(color)}" stroke-width="{width}"{extra}/>')

    # -- text as outlines --------------------------------------------------
    def glyph(self, char, x, y, size, family="mono"):
        key, font, name = resolve(char, family)
        scale = size / font.upm
        gid = f'{key}-{re.sub(r"[^a-zA-Z0-9_-]", "_", name)}-{int(size * 10)}'
        if gid not in self.defs:
            pen = SVGPathPen(font.glyphs, ntos=num)
            font.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, 0, 0)))
            self.defs[gid] = f'<path id="{gid}" d="{pen.getCommands()}"/>'
        advance = font.glyphs[name].width * scale
        if not char.strip():
            return "", advance
        return f'<use href="#{gid}" x="{num(x)}" y="{num(y)}"/>', advance

    def measure(self, text, size, family="mono"):
        return sum(self.glyph(char, 0, 0, size, family)[1] for char in str(text))

    def text(self, text, x, y, size=12, fill="text", anchor="start", family="mono", extra=""):
        text = str(text)
        if anchor == "middle":
            x -= self.measure(text, size, family) / 2
        elif anchor == "end":
            x -= self.measure(text, size, family)
        uses = []
        for char in text:
            use, advance = self.glyph(char, x, y, size, family)
            uses.append(use)
            x += advance
        self.add(f'<g fill="{self.color(fill)}"{extra}>{"".join(uses)}</g>')

    def capture_text(self, *args, **kwargs):
        self.text(*args, **kwargs)
        return self.body.pop()

    # -- terminal pieces ---------------------------------------------------
    def prompt(self, command, x, y, size=10, typed=False):
        cw = size * .6
        for label, color, family in [(f"{self.user}@{self.host}", "lilac", "bold"), ("➜", "mint", "mono"), ("~", "blue", "mono")]:
            self.text(label, x, y, size, color, family=family)
            x += self.measure(label, size, family) + cw
        if typed:
            self.typed(command, x, y, size)
        else:
            self.text(command, x, y, size, "text")

    def typed(self, command, x, y, size, accent="leaf"):
        """Type the command one key at a time, hold it, then clear and start over."""
        cw = size * .6
        end = DURATION * .81
        pct = lambda seconds: f"{seconds / DURATION * 100:.3f}%"
        for index, char in enumerate(command):
            start = .6 + index * .065
            cls = f"key-{index}"
            self.style(f'@keyframes {cls}{{0%,{pct(start)}{{opacity:0}}{pct(start + .01)},{pct(end)}{{opacity:1}}{pct(end + .01)},100%{{opacity:0}}}}.{cls}{{opacity:0;animation:{cls} {DURATION}s step-end infinite}}')
            use, _ = self.glyph(char, x + index * cw, y, size)
            if use:
                self.add(f'<g class="{cls} motion" fill="{self.color("text")}">{use}</g>')
            cursor_end = start + .065 if index + 1 < len(command) else end
            cursor = f"cur-{index}"
            self.style(f'@keyframes {cursor}{{0%,{pct(start)}{{opacity:0}}{pct(start + .01)},{pct(cursor_end)}{{opacity:1}}{pct(cursor_end + .01)},100%{{opacity:0}}}}.{cursor}{{opacity:0;animation:{cursor} {DURATION}s step-end infinite}}')
            self.add(f'<g class="{cursor} motion"><rect class="cursor" x="{num(x + (index + 1) * cw + 1)}" y="{num(y - size + 2)}" width="{num(cw)}" height="{num(size + 2)}" fill="{self.color(accent)}"/></g>')
        self.add(f'<g class="reduced">{self.capture_text(command, x, y, size, "text")}</g>')

    def window(self, title, right=None):
        """Rounded terminal window with a soft shadow and three pastel lights."""
        x, y, w, h, bar = 10, 10, self.w - 20, self.h - 20, 34
        self.defs["window-shadow"] = f'<filter id="window-shadow" x="-6%" y="-8%" width="112%" height="125%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="{self.color("shadow")}" flood-opacity="{.22 if self.theme == "light" else .5}"/></filter>'
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{self.color("paper")}" filter="url(#window-shadow)"/>')
        self.add(f'<path d="M{x} {y + bar}V{y + 12}a12 12 0 0 1 12-12H{x + w - 12}a12 12 0 0 1 12 12V{y + bar}Z" fill="{self.color("panel")}"/>')
        self.add(f'<path d="M{x} {y + bar}H{x + w}" stroke="{self.color("line")}"/>')
        for cx, color in zip([30, 50, 70], self.p["lights"]):
            self.add(f'<circle cx="{cx}" cy="27" r="5" fill="{color}"/>')
        self.text(title, self.w / 2, 31, 11, "muted", "middle")
        if right:
            self.text(right, self.w - 34, 30, 8, "muted", "end")
        # A thin crimson-to-orange stripe under the title bar, drawn last so photos don't cover it.
        start, middle, end = self.p["accent"]
        self.defs["accent"] = (f'<linearGradient id="accent" gradientUnits="userSpaceOnUse" x1="{x}" y1="0" x2="{x + w}" y2="0">'
                               f'<stop offset="0" stop-color="{start}"/><stop offset=".55" stop-color="{middle}"/><stop offset="1" stop-color="{end}"/></linearGradient>')
        self.overlay.append(f'<rect x="{x}" y="{y + bar}" width="{w}" height="2" fill="url(#accent)"/>')
        self.overlay.append(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="11.5" fill="none" stroke="{self.color("line")}"/>')

    def finish(self, title):
        css = "".join(self.styles)
        css += ('.cursor{animation:blink 1s step-end infinite}.reduced{display:none}'
                '@keyframes blink{50%{opacity:0}}'
                '@media(prefers-reduced-motion:reduce){*{animation:none!important}.motion{display:none!important}.reduced{display:inline!important}}')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(self.w)}" height="{num(self.h)}" viewBox="0 0 {num(self.w)} {num(self.h)}" role="img" aria-label="{escape(title)}">'
                f'<title>{escape(title)}</title><style>{css}</style><defs>{"".join(self.defs.values())}</defs>'
                f'{"".join(self.body)}{"".join(self.overlay)}</svg>\n')
