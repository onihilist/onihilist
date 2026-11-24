#!/usr/bin/env python3
"""Profile artwork: a Japanese landscape seen through a terminal window.

The header shows the photo set in profile.toml under a black veil, with maple
leaves falling over it. Without a photo it falls back to a drawn countryside:
a summer afternoon in the light theme, the same valley at night in the dark one.
"""
import base64
import calendar
from datetime import date, timedelta
from xml.sax.saxutils import escape

import pyfiglet

from canvas import ROOT, Canvas, num

CONTENT_X = 34
CONTENT_TOP = 70
HEADER_HEIGHT = 380

SCENE = {
    "light": dict(
        sky=[(0, "#e4f0f8"), (.55, "#f3f3ea"), (1, "#fbe6c8")],
        sun="#f5cd83", glow="#fbe1ad", cloud="#ffffff", cloud_shade="#e1ebf3", cloud_opacity=.94,
        far="#c4d4e4", mid="#a4c4b2", forest="#78a47e", hill="#b9d79b", hill_edge="#a2c886",
        paddy="#cde4ab", water="#d4e7ee", levee="#a5c58a", seedling="#86b56c", shimmer="#ffffff",
        pole="#7a6b61", wall="#f2e7d3", roof="#6c7d95", wood="#8b6a51", window="#9fb6cc", lamp_glow=0,
        fruit="#e2853f", torii="#c95b44", rail="#9b8f85", body="#f4ecdc", stripe="#5f9c83",
        train_window="#a6c4dc", train_roof="#8a96a3", wheel="#55525c", grass="#9ac57b", tuft="#7fae62",
        flowers=["#ffffff", "#f3c4cc", "#f6e39a"], leaf="#8cbd70", bird="#5d5862",
    ),
    "dark": dict(
        sky=[(0, "#0c1322"), (.6, "#172038"), (1, "#2a2c47")],
        moon="#f1e5c4", glow="#f1e5c4", cloud="#2a3450", cloud_shade="#222b43", cloud_opacity=.8,
        far="#222c46", mid="#1e3237", forest="#15271f", hill="#1d3325", hill_edge="#182b1f",
        paddy="#1f3628", water="#223049", levee="#294230", seedling="#3a5f45", shimmer="#f1e5c4",
        pole="#4b4659", wall="#3a3944", roof="#252b3c", wood="#2b2530", window="#f4d27e", lamp_glow=.5,
        fruit="#b5673d", torii="#a24c40", rail="#4a4958", body="#d8d1c1", stripe="#4c8a70",
        train_window="#f4d58c", train_roof="#5a6170", wheel="#26242c", grass="#1a2f21", tuft="#24402c",
        flowers=[], firefly="#e8f59c", star="#e7ecf8",
    ),
}

# Contribution levels as rice-paddy greens, and a little lilac train that rides the trail.
CELLS = {
    "light": ["#e9ece0", "#cfe0bb", "#a8c98d", "#7ea868", "#5a8550"],
    "dark": ["#1e2630", "#2b4733", "#3d6746", "#5c9263", "#8dc48d"],
}
TRAIN = {"light": ("#6f57ad", "#a28cd6"), "dark": ("#d3c4f4", "#9a83d6")}

ICONS = {
    "bluesky": '<path d="M7 6.2C5.6 3.6 3.2 1.8 1.9 2.4.8 2.9 1.2 6 2.4 7.1c1 .9 2.6 1 3.6.7-2.4.6-2.9 2.4-1.6 3.6 1.5 1.4 2.6-.6 2.6-2.4 0 1.8 1.1 3.8 2.6 2.4 1.3-1.2.8-3-1.6-3.6 1 .3 2.6.2 3.6-.7C12.8 6 13.2 2.9 12.1 2.4 10.8 1.8 8.4 3.6 7 6.2Z"/>',
    "telegram": '<path d="M13 1.5 1.2 6.4l4 1.4 1.4 4.4 2.2-2.6 3 2.2ZM5.2 7.8 13 1.5"/>',
    "cloud": '<path d="M4.2 11.5h6.3a2.8 2.8 0 0 0 .3-5.6A3.8 3.8 0 0 0 3.6 6.6a2.5 2.5 0 0 0 .6 4.9Z"/>',
    "mail": '<path d="M1.5 3h11v8h-11ZM1.5 3 7 7.5 12.5 3"/>',
}


def new_canvas(theme, height, cfg):
    return Canvas(theme, height, user=cfg["terminal"]["user"], host=cfg["terminal"]["host"])


# -- the valley ---------------------------------------------------------------

def circles(items, fill, extra=""):
    return "".join(f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(r)}" fill="{fill}"{extra}/>' for x, y, r in items)


def drifting(c, name, base_x, y, travel, duration, markup):
    """Place markup at base_x and let it drift right forever; it rests at base_x when motion is off."""
    start, end = -(base_x - travel[0]), travel[1] - base_x
    delay = -(base_x - travel[0]) / (travel[1] - travel[0]) * duration
    c.style(f'@keyframes {name}{{from{{transform:translateX({num(start)}px)}}to{{transform:translateX({num(end)}px)}}}}'
            f'.{name}{{animation:{name} {duration}s linear {num(delay)}s infinite}}')
    c.add(f'<g transform="translate({num(base_x)} {num(y)})"><g class="{name}">{markup}</g></g>')


def cloud(s, scale):
    puffs = [(-24 * scale, 2 * scale, 11 * scale), (-8 * scale, -7 * scale, 15 * scale), (12 * scale, -3 * scale, 13 * scale), (27 * scale, 4 * scale, 9 * scale)]
    body = circles(puffs, s["cloud"])
    body += f'<rect x="{num(-36 * scale)}" y="{num(2 * scale)}" width="{num(72 * scale)}" height="{num(12 * scale)}" rx="{num(6 * scale)}" fill="{s["cloud"]}"/>'
    body += f'<rect x="{num(-33 * scale)}" y="{num(9 * scale)}" width="{num(66 * scale)}" height="{num(5 * scale)}" rx="{num(2.5 * scale)}" fill="{s["cloud_shade"]}"/>'
    return f'<g opacity="{s["cloud_opacity"]}">{body}</g>'


def train(c, s):
    body = f'<rect x="0" y="-23" width="76" height="19" rx="3.5" fill="{s["body"]}"/>'
    body += f'<rect x="3" y="-26" width="70" height="4" rx="2" fill="{s["train_roof"]}"/>'
    body += f'<path d="M32-26 38-33 44-26M35-33H41" fill="none" stroke="{s["train_roof"]}" stroke-width="1.1"/>'
    body += f'<rect x="0" y="-10" width="76" height="3" fill="{s["stripe"]}"/>'
    body += f'<rect x="2" y="-5" width="72" height="2" fill="{s["train_roof"]}"/>'
    windows = "".join(f'<rect x="{7 + i * 13}" y="-20" width="9" height="6.5" rx="1"/>' for i in range(5))
    if c.theme == "dark":
        body += f'<g fill="{s["train_window"]}" opacity=".45" filter="url(#glow)">{windows}</g>'
    body += f'<g fill="{s["train_window"]}">{windows}</g>'
    body += f'<circle cx="74" cy="-8" r="1.3" fill="#f4d27e"/>'
    body += circles([(16, -2.4, 2.6), (60, -2.4, 2.6)], s["wheel"])
    return body


def clip_body(c):
    """Clip path for everything below the title bar, following the window's rounded corners."""
    bottom = c.h - 10
    c.defs["scene-clip"] = f'<clipPath id="scene-clip"><path d="M10 44H778V{bottom - 12}a12 12 0 0 1-12 12H22a12 12 0 0 1-12-12Z"/></clipPath>'
    return bottom


# Ink for text drawn over the darkened photo, whatever the README theme.
PHOTO_INK = dict(text="#f4efe8", muted="#cbc3b8", lilac="#d6c4f5", mint="#a9dcc1", blue="#b8d4ee", leaf="#f2b48a")
PHOTO_NAME = ("#fbe9cc", "#f5b78e", "#e9806c")
MAPLE = "M0-6 1.2-2.8 4.6-4.2 3.2-.9 6-.2 3.4 1.4 3.8 3.6.9 2.4 0 3-.9 2.4-3.8 3.6-3.4 1.4-6-.2-3.2-.9-4.6-4.2-1.2-2.8Z"


def photo(c, path, position, veil):
    """The photo, embedded as data (GitHub won't load external images inside an SVG), under a black veil."""
    bottom = clip_body(c)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    # Darkest behind the text, a little lighter at the bottom so the scene still breathes.
    c.defs["veil"] = (f'<linearGradient id="veil" x1="0" y1="44" x2="0" y2="{bottom}" gradientUnits="userSpaceOnUse">'
                      f'<stop offset="0" stop-opacity="{num(veil)}"/><stop offset=".6" stop-opacity="{num(veil)}"/><stop offset="1" stop-opacity="{num(veil * .65)}"/></linearGradient>')
    c.add('<g clip-path="url(#scene-clip)">')
    c.add(f'<image x="10" y="44" width="768" height="{bottom - 44}" preserveAspectRatio="{position} slice" href="data:{mime};base64,{data}"/>')
    c.add(f'<rect x="10" y="44" width="768" height="{bottom - 44}" fill="url(#veil)"/>')
    c.style('@keyframes fall{0%{transform:translate(0,-24px) rotate(0deg);opacity:0}10%,85%{opacity:.85}100%{transform:translate(-46px,240px) rotate(330deg);opacity:0}}'
            '.momiji{opacity:0;animation:fall 12s linear infinite}')
    colors = ["#e0503a", "#f07a3a", "#c93a2e", "#f2a33a"]
    for i, (x, y) in enumerate([(60, 60), (190, 120), (300, 50), (430, 150), (560, 70), (650, 130), (740, 60), (120, 200)]):
        color = colors[i % len(colors)]
        c.add(f'<g transform="translate({x} {y}) scale({num(.9 + i % 3 * .25)})"><g class="momiji motion" style="animation-duration:{11 + i % 4 * 2}s;animation-delay:-{num(i * 1.7)}s">'
              f'<path d="{MAPLE}" fill="{color}"/><path d="M0 3V6.5" stroke="{color}" stroke-width=".7"/></g></g>')
    c.add('</g>')


def valley(c):
    """Everything behind the header text, clipped to the window body."""
    s = SCENE[c.theme]
    bottom = clip_body(c)
    c.defs["glow"] = '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>'
    stops = "".join(f'<stop offset="{o}" stop-color="{color}"/>' for o, color in s["sky"])
    c.defs["sky"] = f'<linearGradient id="sky" x1="0" y1="44" x2="0" y2="330" gradientUnits="userSpaceOnUse">{stops}</linearGradient>'
    c.add('<g clip-path="url(#scene-clip)">')
    c.add(f'<rect x="10" y="44" width="768" height="{bottom - 44}" fill="url(#sky)"/>')

    # sun or moon, then the stars
    if c.theme == "light":
        c.add(f'<circle class="halo" cx="712" cy="94" r="36" fill="{s["glow"]}" opacity=".55"/><circle cx="712" cy="94" r="21" fill="{s["sun"]}"/>')
        c.style('.halo{animation:halo 7s ease-in-out infinite}@keyframes halo{50%{opacity:.25}}')
    else:
        c.defs["moon-cut"] = '<mask id="moon-cut" maskUnits="userSpaceOnUse" x="680" y="58" width="64" height="70"><rect x="680" y="58" width="64" height="70" fill="white"/><circle cx="721" cy="86" r="15.5" fill="black"/></mask>'
        c.add(f'<circle cx="712" cy="92" r="34" fill="{s["glow"]}" opacity=".07"/><circle cx="712" cy="92" r="17" fill="{s["moon"]}" mask="url(#moon-cut)"/>')
        stars = []
        for i in range(30):
            x, y = 24 + (i * 137) % 740, 52 + (i * 53) % 168
            if abs(x - 712) < 40 and abs(y - 92) < 40:
                continue
            r = .6 + (i % 3) * .35
            stars.append(f'<circle class="star" cx="{x}" cy="{y}" r="{num(r)}" fill="{s["star"]}" style="animation-duration:{3 + i % 4}s;animation-delay:-{num(i * .7)}s"/>')
        c.add("".join(stars))
        c.style('.star{animation:twinkle 4s ease-in-out infinite}@keyframes twinkle{50%{opacity:.2}}')

    # clouds drift slowly from left to right
    for i, (x, y, scale, duration) in enumerate([(150, 108, 1.0, 120), (520, 128, 1.25, 150), (330, 94, .7, 100), (650, 156, .9, 135), (40, 142, .8, 110)]):
        drifting(c, f"cloud-{i}", x, y, (-70, 860), duration, cloud(s, scale))

    # far mountains, the nearer hills and their woods
    c.add(f'<path d="M10 320V252C40 243 72 233 106 231C140 229 166 241 192 256C232 276 300 286 394 286C482 286 540 272 590 255C626 242 662 228 702 228C736 228 760 238 778 246V320Z" fill="{s["far"]}"/>')
    c.add(f'<path d="M10 320V280C60 270 110 266 160 272C230 280 300 294 394 294C470 294 520 286 570 280C630 272 690 266 740 272C760 274 770 276 778 278V320Z" fill="{s["mid"]}"/>')
    woods = [(24, 276, 10), (40, 271, 12), (58, 268, 11), (76, 267, 13), (94, 267, 11), (110, 268, 10), (124, 270, 8),
             (626, 276, 9), (642, 272, 11), (660, 269, 12), (678, 268, 10), (694, 267, 12), (712, 268, 10), (730, 270, 11), (748, 271, 9), (764, 272, 10)]
    c.add(circles(woods, s["forest"]))

    # a small torii at the edge of the woods
    c.add(f'<g fill="{s["torii"]}"><rect x="143" y="258" width="2.4" height="16"/><rect x="154.6" y="258" width="2.4" height="16"/>'
          f'<path d="M137 254.6Q150 257.4 163 254.6L162.4 257.6Q150 259.6 137.6 257.6Z"/><rect x="140.5" y="261" width="19" height="1.8"/><rect x="149.2" y="257.6" width="1.6" height="3.6"/></g>')

    # power poles and sagging wires, the most rural-Japan thing there is
    poles = [-130, 70, 270, 470, 700, 900]
    wires = []
    for a, b in zip(poles, poles[1:]):
        for dx in (-8, 8):
            wires.append(f'M{a + dx} 249Q{(a + b) / 2 + dx} 273 {b + dx} 249')
    c.add(f'<path d="{"".join(wires)}" fill="none" stroke="{s["pole"]}" stroke-width=".8"/>')
    for x in poles[1:-1]:
        c.add(f'<g fill="{s["pole"]}"><rect x="{x - 1.2}" y="244" width="2.4" height="62"/><rect x="{x - 11}" y="250" width="22" height="2"/></g>')
        c.add(circles([(x - 8, 249, 1.4), (x + 8, 249, 1.4)], s["pole"]))
    c.add(f'<rect x="471.5" y="262" width="6" height="8" rx="1" fill="{s["pole"]}"/>')
    if c.theme == "light":
        for x, y in [(326, 259.4), (342, 260.5)]:
            c.add(f'<g fill="{s["bird"]}"><ellipse cx="{x}" cy="{num(y - 2.6)}" rx="3.2" ry="2.3"/><circle cx="{num(x + 2.6)}" cy="{num(y - 4.9)}" r="1.6"/><path d="M{num(x - 3)} {num(y - 2.4)}l-3.2 2.2 .6-3Z"/></g>')

    # the near hill, a farmhouse and its persimmon tree
    c.add(f'<path d="M10 {bottom}V304C90 296 170 294 250 298C330 302 360 306 394 306C470 306 540 298 610 294C680 290 740 294 778 298V{bottom}Z" fill="{s["hill"]}"/>')
    c.add(f'<rect x="638.5" y="282" width="2.6" height="18" fill="{s["wood"]}"/>')
    c.add(circles([(640, 278, 10), (631, 283, 7), (649, 283, 7)], s["forest"]))
    c.add(circles([(636, 280, 1.6), (645, 284, 1.6), (631, 285, 1.6), (642, 274, 1.6)], s["fruit"]))
    if s["lamp_glow"]:
        c.add(f'<rect class="lamp" x="566" y="283" width="24" height="16" fill="{s["window"]}" opacity="{s["lamp_glow"]}" filter="url(#glow)"/>')
    c.add(f'<rect x="566" y="282" width="48" height="18" fill="{s["wall"]}"/>')
    c.add(f'<g fill="{s["wood"]}"><rect x="566" y="282" width="2" height="18"/><rect x="589" y="282" width="2" height="18"/><rect x="612" y="282" width="2" height="18"/>'
          f'<rect x="596" y="287" width="12" height="13"/><rect x="562" y="299" width="56" height="2.2"/></g>')
    c.add(f'<rect class="lamp" x="571" y="287" width="14" height="8" fill="{s["window"]}"/><path d="M578 287V295M571 291H585" stroke="{s["wood"]}" stroke-width=".8"/>')
    c.add(f'<path d="M554 284 573 266H607L626 284Z" fill="{s["roof"]}"/><path d="M571 266H609" stroke="{s["roof"]}" stroke-width="3" stroke-linecap="round"/>')
    c.style('.lamp{animation:lamp 9s ease-in-out infinite}@keyframes lamp{50%{opacity:.75}}')

    # rice paddies: green rows, water rows that catch the sky, levees in perspective
    for y, height, role in [(314, 6, "paddy"), (320, 2, "levee"), (322, 8, "water"), (330, 2, "levee"), (332, 7, "paddy"), (339, 2, "levee"), (341, 7, "water")]:
        c.add(f'<rect x="10" y="{y}" width="768" height="{height}" fill="{s[role]}"/>')
        if role == "paddy":
            c.add(f'<path d="M14 {y + 3}H778" stroke="{s["seedling"]}" stroke-width="2.4" stroke-dasharray="1.2 4.2"/>')
        elif role == "water":
            c.add(f'<path d="M12 {y + 4}H778" stroke="{s["seedling"]}" stroke-width="2" stroke-dasharray="1 6" opacity=".8"/>')
            c.add(f'<path class="shimmer" d="M10 {y + 2}H778" stroke="{s["shimmer"]}" stroke-width="1" stroke-dasharray="10 40" opacity=".6"/>')
    levees = "".join(f'M{num(394 + (x - 394) * .82)} 314L{x} 348' for x in [40, 180, 320, 470, 610, 750])
    c.add(f'<path d="{levees}" stroke="{s["levee"]}" stroke-width="1.6"/>')
    c.style('.shimmer{animation:shimmer 6s linear infinite}@keyframes shimmer{to{stroke-dashoffset:-50}}')

    # a one-car local train, then the grass in front of it
    c.add(f'<path d="M10 354H778" stroke="{s["rail"]}" stroke-width="1.4"/><path d="M10 356.5H778" stroke="{s["rail"]}" stroke-width="3" stroke-dasharray="2 7" opacity=".7"/>')
    c.style('@keyframes train{0%{transform:translateX(-390px)}70%,100%{transform:translateX(490px)}}.train{animation:train 30s linear -9.3s infinite}')
    c.add(f'<g transform="translate(300 354)"><g class="train">{train(c, s)}</g></g>')
    c.add(f'<path d="M10 {bottom}V359C80 355 160 357 240 356C330 355 420 359 520 357C620 355 700 356 778 358V{bottom}Z" fill="{s["grass"]}"/>')
    tufts = "".join(f'M{x} 366l2.2-7 1 7 2-5.2 1 5.2 1.8-6 .8 6' for x in [30, 96, 170, 238, 318, 402, 486, 560, 648, 722])
    c.add(f'<path d="{tufts}" fill="none" stroke="{s["tuft"]}" stroke-width="1"/>')
    for i, x in enumerate([44, 112, 252, 330, 498, 574, 662, 736]):
        if s["flowers"]:
            c.add(circles([(x, 362 - i % 2 * 2, 1.5)], s["flowers"][i % len(s["flowers"])]))

    # leaves on the breeze by day, fireflies by night
    if c.theme == "light":
        c.style('@keyframes breeze{0%{transform:translate(0,0) rotate(0deg);opacity:0}12%,85%{opacity:.9}100%{transform:translate(150px,44px) rotate(280deg);opacity:0}}.breeze{animation:breeze 11s ease-in-out infinite}')
        for i, (x, y) in enumerate([(70, 246), (236, 228), (418, 262), (548, 236), (684, 256), (322, 300)]):
            c.add(f'<g transform="translate({x} {y})"><g class="breeze" style="animation-duration:{10 + i % 3 * 2}s;animation-delay:-{num(i * 2.1)}s"><ellipse rx="3.2" ry="1.3" fill="{s["leaf"]}"/></g></g>')
    else:
        c.style('@keyframes fly{0%,100%{opacity:.1;transform:translate(0,0)}50%{opacity:1;transform:translate(6px,-8px)}}.fly{animation:fly 5s ease-in-out infinite}')
        for i in range(14):
            x, y = 40 + (i * 53) % 700, 262 + (i * 29) % 82
            c.add(f'<g transform="translate({x} {y})"><g class="fly" style="animation-duration:{4 + i % 4}s;animation-delay:-{num(i * 1.3)}s">'
                  f'<circle r="4.5" fill="{s["firefly"]}" opacity=".18"/><circle r="1.3" fill="{s["firefly"]}"/></g></g>')
    c.add('</g>')


def figlet_name(c, word, center, top, size=12, colors=None):
    rows = pyfiglet.figlet_format(word, font="ansi_shadow", width=200).rstrip().splitlines()
    cw, lh = size * .6, size * 1.32
    width = max(map(len, rows)) * cw
    left = center - width / 2
    start, middle, end = colors or (c.color("leaf"), c.color("blue"), c.color("lilac"))
    c.defs["name-gradient"] = (f'<linearGradient id="name-gradient" gradientUnits="userSpaceOnUse" x1="{num(left)}" y1="0" x2="{num(left + width)}" y2="0">'
                               f'<stop offset="0" stop-color="{start}"/><stop offset=".5" stop-color="{middle}"/><stop offset="1" stop-color="{end}"/></linearGradient>')
    blocks, shadows = [], []
    for row, line in enumerate(rows):
        for col, char in enumerate(line):
            x, y = left + col * cw, top + row * lh
            if char == "█":
                blocks.append(f'M{num(x)} {num(y)}h{num(cw + .08)}v{num(lh + .08)}h-{num(cw + .08)}Z')
            elif char != " ":
                use, _ = c.glyph(char, x, y + size * 1.02, size)
                shadows.append(use)
    c.add(f'<g fill="{c.color("muted")}" opacity=".72">{"".join(shadows)}</g>')
    c.add(f'<path d="{"".join(blocks)}" fill="url(#name-gradient)"/>')


def header(theme, cfg):
    h = cfg["header"]
    c = new_canvas(theme, HEADER_HEIGHT, cfg)
    c.window(f'{c.user}@{c.host}', h["chrome_right"])
    name_colors = None
    if h.get("photo"):
        photo(c, ROOT / h["photo"], h.get("photo_position", "xMidYMid"), h.get("veil", .6))
        c.p = dict(c.p, **PHOTO_INK)  # the title bar keeps the theme; text on the photo is always light
        name_colors = PHOTO_NAME
    else:
        valley(c)
    c.prompt(h["command"], CONTENT_X, CONTENT_TOP, 10, typed=True)
    figlet_name(c, h["name"], 394, 84, 12, name_colors)
    c.text(h["subtitle"], 394, 202, 11, "text", "middle")
    c.text(h["tagline"], 394, 228, 14, "text", "middle", "serif")
    return c.finish(f'{h["name"]} · {h["subtitle"]} · {h["tagline"]}')


# -- badges -------------------------------------------------------------------

def badge(icon, label, value, theme, cfg):
    c = new_canvas(theme, 32, cfg)
    left = 27 + c.measure(label, 11) + 10
    width = left + c.measure(value + " ↗", 11) + 23
    c.w = width
    c.rect(0, 0, width, 32, "panel", 4)
    c.add(f'<path d="M4 0H{num(left)}V32H4a4 4 0 0 1-4-4V4a4 4 0 0 1 4-4Z" fill="{c.color("tag")}"/>')
    c.add(f'<g transform="translate(8 9)" fill="none" stroke="{c.color("ink")}" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>')
    c.text(label, 27, 21, 11, "ink")
    c.text(value + " ↗", left + 11, 21, 11, "text")
    title = escape(f"{label}: {value}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(width)}" height="32" viewBox="0 0 {num(width)} 32" role="img" aria-label="{title}">'
            f'<title>{title}</title><defs>{"".join(c.defs.values())}</defs>{"".join(c.body)}</svg>\n')


# -- workspace ----------------------------------------------------------------

def directory_text(c, text, x, y, size, highlight=False):
    family = "bold" if highlight else "mono"
    if highlight:
        width = c.measure(text, size, family)
        c.rect(x - 5, y - size * 1.15, width + 10, size + 7, "lilac", 3, extra=f' opacity="{.12 if c.theme == "light" else .18}"')
    c.text(text[:-1], x, y, size, "blue", family=family)
    c.text("/", x + c.measure(text[:-1], size, family), y, size, "gold", family=family)
    return c.measure(text, size, family)


def wind_chime(c):
    """A fūrin swaying under the title bar."""
    c.style('.furin{transform-origin:722px 44px;animation:swing 5s ease-in-out infinite}.tanzaku{transform-origin:722px 92px;animation:swing 3.2s ease-in-out -1s infinite}'
            '@keyframes swing{0%,100%{transform:rotate(-5deg)}50%{transform:rotate(5deg)}}')
    c.add(f'<g transform="translate(722 44) scale(1.35) translate(-722 -44)"><g class="furin"><path d="M722 44V62M722 76V92" stroke="{c.color("muted")}" stroke-width=".8"/>'
          f'<path d="M711 76C711 66 716 62 722 62S733 66 733 76Z" fill="{c.color("blue")}" fill-opacity=".28" stroke="{c.color("blue")}"/>'
          f'<ellipse cx="718.5" cy="70.5" rx="2.6" ry="1.4" fill="{c.color("red")}" opacity=".85"/><path d="M716 70.5l-2.2-1.4v2.8Z" fill="{c.color("red")}" opacity=".85"/>'
          f'<g class="tanzaku"><rect x="717.5" y="92" width="9" height="28" rx="1" fill="{c.color("lilac")}" opacity=".5"/>'
          f'<path d="M719.5 100q2.5-2 5 0M719.5 106q2.5-2 5 0" fill="none" stroke="{c.color("paper")}" stroke-width=".8"/></g></g></g>')


def workspace(theme, cfg):
    w = cfg["workspace"]
    c = new_canvas(theme, 350, cfg)
    c.window(f'{c.user}@{c.host} — workspace')
    wind_chime(c)
    c.prompt("ls ~/focus", CONTENT_X, CONTENT_TOP)
    name_width = max(c.measure(entry["name"], 12, "bold") for entry in w["focus"])
    for i, entry in enumerate(w["focus"]):
        y = 104 + i * 25
        directory_text(c, entry["name"], 58, y, 12, highlight=True)
        c.text(entry["detail"], 58 + name_width + 34, y, 10, "muted")
    c.prompt("ls ~/stack", CONTENT_X, 185)
    x = 58
    for tool in w["stack"]:
        x += directory_text(c, tool, x, 214, 11) + c.measure("  ", 11)
    c.prompt(f'cat ~/{w["manifesto_file"]}', CONTENT_X, 250)
    c.text(w["manifesto"][0], 58, 280, 12, "text")
    c.text(w["manifesto"][1], 58, 305, 11, "muted")
    c.text(w["motto"], 58, 329, 12, "gold", family="serif")
    focus = ", ".join(entry["name"].rstrip("/") for entry in w["focus"])
    stack = ", ".join(tool.rstrip("/") for tool in w["stack"])
    return c.finish(f'Focus: {focus}. Stack: {stack}. {" ".join(w["manifesto"])} {w["motto"]}')


# -- GitHub card --------------------------------------------------------------

def key_times(*times):
    return ";".join(f"{t:.9f}".rstrip("0").rstrip(".") for t in times)


def draw_trail(c, data, x0, y0, right, footer_y, footer):
    """The year as a grid of paddies, with a small train riding through every square."""
    days = data["days"]
    first = date.fromisoformat(days[0]["date"])
    first_row = (first.weekday() + 1) % 7
    origin = first - timedelta(days=first_row)
    last = date.fromisoformat(days[-1]["date"])
    last_col, last_row = divmod((last - origin).days, 7)
    weeks = last_col + 1
    step = min(16, (right - x0) / weeks)
    cell = step * .75

    # A boustrophedon route: down one week, up the next, through every square.
    points = [(col, 6 - j if col % 2 else j) for col in range(weeks) for j in range(7)]
    end = points.index((last_col, 0 if last_col % 2 else last_row))
    points = [(-1, first_row), *points[first_row:end + 1], (weeks, points[end][1])]
    path = "M" + " L".join(f"{x},{y}" for x, y in points)
    point_index = {point: i for i, point in enumerate(points)}
    segments, spacing = 7, .6
    head_start, tail_end = .02, .92
    steps = len(points) - 1
    step_time = (tail_end - head_start) / (steps + (segments - 1) * spacing)
    duration = min(34, max(3, .11 * steps))
    clock = f'dur="{duration:g}s" repeatCount="indefinite"'

    month = None
    for day in days:
        d = date.fromisoformat(day["date"])
        col, row = divmod((d - origin).days, 7)
        x, y = x0 + col * step, y0 + row * step
        rect = f'<rect class="contribution" x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="2" fill="{CELLS[c.theme][day["level"]]}"><title>{day["date"]}: {day["count"]} contributions</title>'
        if day["count"]:
            arrive = head_start + point_index[col, row] * step_time
            times = key_times(0, arrive, arrive + .3 * step_time, .94, .98, 1)
            rect += f'<animate attributeName="opacity" {clock} values="1;1;.17;.17;1;1" keyTimes="{times}"/>'
        c.add(rect + "</rect>")
        if d.month != month:
            month = d.month
            c.text(calendar.month_abbr[month], x, y0 - 12, 9, "muted")
    for label, row in [("M", 1), ("W", 3), ("F", 5)]:
        c.text(label, x0 - 22, y0 + row * step + 9, 8, "muted")

    c.defs["trail-route"] = f'<path id="trail-route" d="{path}"/>'
    head_color, body_color = TRAIN[c.theme]
    cars = [f'<g class="trail" transform="translate({x0 + cell / 2:.6f},{y0 + cell / 2:.6f}) scale({step:.6f})">']
    for i in range(segments - 1, -1, -1):
        start = head_start + i * spacing * step_time
        finish = start + steps * step_time
        motion = key_times(0, start, finish, 1)
        fade = key_times(0, start, start + .7 * step_time, finish - .7 * step_time, finish, 1)
        opacity = f"{1 - i * .07:.2f}"
        cars.append(f'<rect x="-.33" y="-.33" width=".66" height=".66" rx=".13" fill="{head_color if i == 0 else body_color}" opacity="0">'
                    f'<animateMotion {clock} calcMode="linear" keyPoints="0;0;1;1" keyTimes="{motion}"><mpath href="#trail-route"/></animateMotion>'
                    f'<animate attributeName="opacity" {clock} values="0;0;{opacity};{opacity};0;0" keyTimes="{fade}"/></rect>')
    cars.append("</g>")
    c.add("".join(cars))
    c.style('@media(prefers-reduced-motion:reduce){.trail{display:none}.contribution{opacity:1!important}}')

    c.text(footer, x0 - 27, footer_y, 9, "muted")
    c.text("More", right, footer_y, 9, "muted", "end")
    for i, color in enumerate(CELLS[c.theme]):
        c.rect(right - 76 + i * 10, footer_y - 7, 7, 7, color, 1)
    c.text("Less", right - 82, footer_y, 9, "muted", "end")


def github(data, theme, cfg):
    c = new_canvas(theme, 412, cfg)
    c.window(f'{c.user}@{c.host} — github')
    summary, year = data["summary"], data["asOf"][:4]
    as_of = date.fromisoformat(data["asOf"])
    c.text("On GitHub", CONTENT_X, CONTENT_TOP, 13, "text", family="bold")
    c.text(f"{year} · as of {calendar.month_abbr[as_of.month]} {as_of.day:02d}", 754, CONTENT_TOP, 9, "muted", "end")
    c.prompt(f"git stats --year={year}", CONTENT_X, 98)
    if summary["currentStart"]:
        start, end = map(date.fromisoformat, [summary["currentStart"], summary["currentEnd"]])
        span = f"{calendar.month_abbr[start.month]} {start.day:02d} – {calendar.month_abbr[end.month]} {end.day:02d}"
    else:
        span = "No active streak"
    stats = [(f'{summary["total"]:,}', "Contributions", year),
             (summary["currentStreak"], "Current streak", span),
             (summary["longestStreak"], "Longest streak", f"in {year}")]
    for center, (value, label, foot) in zip([161, 394, 627], stats):
        c.text(value, center, 140, 24, "text", "middle", "bold")
        c.text(label, center, 165, 11, "muted", "middle")
        c.text(foot, center, 185, 9, "muted", "middle")
    c.prompt(f"git trail --year={year}", CONTENT_X, 225)
    draw_trail(c, data, 71, 257, 752, 386, cfg["github_card"]["footer"])
    return c.finish(f"On GitHub in {year}: {summary['total']} contributions, current streak {summary['currentStreak']}, "
                    f"longest streak {summary['longestStreak']}. Contribution trail through {data['asOf']}.")


# -- output -------------------------------------------------------------------

def write_assets(data, cfg):
    dest = ROOT / "assets"
    dest.mkdir(exist_ok=True)
    for theme in ("light", "dark"):
        files = {"header": header(theme, cfg), "workspace": workspace(theme, cfg), "github": github(data, theme, cfg)}
        for item in cfg["badges"]:
            files[f'badge-{item["slug"]}'] = badge(item["icon"], item["label"], item["value"], theme, cfg)
        for name, svg in files.items():
            (dest / f"{name}-{theme}.svg").write_text(svg, encoding="utf-8", newline="\n")
