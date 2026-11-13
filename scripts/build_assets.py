#!/usr/bin/env python3
"""Builds the animated SVGs for the GitHub profile README, in the design
language of arnavparashar.com: paper and ink, hairlines, tracked mono labels,
Geist Pixel display type, halftone dots, one orange signal colour, and the
black island with NotchHub's pixel fox.

    pip install fonttools brotli
    python3 scripts/build_assets.py

Writes assets/light/*.svg and assets/dark/*.svg (the README picks one with
<picture> and prefers-color-scheme).

- The fox is read from scripts/pet/ (a copy of NotchHub/art/pet).
- Fonts come from scripts/fonts/ (the site's own woff2 files, all SIL OFL).
  Each SVG embeds a subset holding only the glyphs it uses, because GitHub
  serves README images in a sandbox that can't load web fonts.
- Animations only play under prefers-reduced-motion: no-preference; everyone
  else gets a still frame.
"""
import base64
import html
import io
import math
import os
from collections import defaultdict

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PET_DIR = os.path.join(ROOT, "scripts", "pet")
FONT_DIR = os.path.join(ROOT, "scripts", "fonts")
OUT_DIR = os.path.join(ROOT, "assets")

# --------------------------------------------------------------------------- #
# Themes. Light is the site's own palette; dark keeps the same design on
# GitHub's dark canvas.
# --------------------------------------------------------------------------- #
THEMES = {
    "light": dict(
        surface="#F6F6F5", panel="#FFFFFF", ink="#0B0B0B", muted="#525252",
        faint="#6E6E6E", ghost="#8A8A8A", line="#0B0B0B", la=0.08, lb=0.16,
        dot="#0B0B0B", grid=0.11, signal="#DD6A1F", soft="#FFF3E2",
        island="#050505", rim=0.0, rail="#262626", btn="#0B0B0B", btn_ink="#FFFFFF",
        plate="#FFFFFF", side_l="#EFEFED", side_r="#E2E2E0", shadow=0.10,
    ),
    "dark": dict(
        surface="#151B23", panel="#0D1117", ink="#F0F6FC", muted="#9198A1",
        faint="#7D8590", ghost="#6E7681", line="#F0F6FC", la=0.10, lb=0.20,
        dot="#F0F6FC", grid=0.10, signal="#EC7A2C", soft="#3A2414",
        island="#000000", rim=0.16, rail="#2B2B2B", btn="#F0F6FC", btn_ink="#0D1117",
        plate="#161B22", side_l="#10151C", side_r="#0B0F14", shadow=0.45,
    ),
}
LANG = [("python", "#3572A5"), ("swift", "#F05138"), ("typescript", "#3178C6"),
        ("rust", "#DEA584"), ("css", "#663399")]

# island UI (always dark)
I_TEXT, I_SUB, I_EYE = "#FAFAFA", "#A3A3A3", "#7A7A7A"


def esc(s):
    return html.escape(s, quote=True)


def f(n):
    """Compact number formatting for SVG attributes."""
    return f"{n:.2f}".rstrip("0").rstrip(".") if isinstance(n, float) else str(n)


# --------------------------------------------------------------------------- #
# Fonts: measuring and subsetting
# --------------------------------------------------------------------------- #
FONT_FILES = {
    "sans": ("Archivo-Variable.woff2", "ap-sans", "100 900", "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"),
    "mono": ("JetBrainsMono-Variable.woff2", "ap-mono", "100 800", "ui-monospace,Menlo,Consolas,monospace"),
    "pixel": ("GeistPixel-Square.woff2", "ap-pixel", "100 900", "ui-monospace,monospace"),
    "grid": ("GeistPixel-Grid.woff2", "ap-grid", "100 900", "ui-monospace,monospace"),
}


class Fonts:
    def __init__(self):
        self.raw = {k: TTFont(os.path.join(FONT_DIR, v[0])) for k, v in FONT_FILES.items()}
        self._adv = {}
        self._sub = {}

    def advances(self, fam, weight):
        font = self.raw[fam]
        key = (fam, weight if "fvar" in font else None)
        if key not in self._adv:
            if "fvar" in font and weight:
                font = instancer.instantiateVariableFont(font, {"wght": weight}, inplace=False)
            cmap = font.getBestCmap()
            hmtx = font["hmtx"]
            upm = font["head"].unitsPerEm
            self._adv[key] = ({cp: hmtx[g][0] / upm for cp, g in cmap.items()}, hmtx[cmap[32]][0] / upm)
        return self._adv[key]

    def width(self, s, fam, size, weight=400, ls=0.0):
        adv, space = self.advances(fam, weight)
        return sum(adv.get(ord(c), space) for c in s) * size + ls * len(s)

    def subset_b64(self, fam, chars):
        key = (fam, "".join(sorted(chars)))
        if key not in self._sub:
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern"]
            opts.hinting = False
            opts.desubroutinize = True
            opts.name_IDs = [1, 2]
            opts.notdef_outline = False
            font = TTFont(os.path.join(FONT_DIR, FONT_FILES[fam][0]))
            sub = subset.Subsetter(opts)
            sub.populate(unicodes={ord(c) for c in chars} | {32})
            sub.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff2"
            font.save(buf)
            self._sub[key] = base64.b64encode(buf.getvalue()).decode()
        return self._sub[key]


FONTS = Fonts()


# --------------------------------------------------------------------------- #
# The fox (NotchHub's pixel pet)
# --------------------------------------------------------------------------- #
def load_pet():
    pal = {}
    with open(os.path.join(PET_DIR, "palette.txt")) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                k, c = line.split()[:2]
                pal[k] = c
    frames = {}
    for name in sorted(os.listdir(PET_DIR)):
        if not name.endswith(".pet"):
            continue
        cur = None
        with open(os.path.join(PET_DIR, name)) as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("@frame"):
                    cur = line.split()[1]
                    frames[cur] = []
                elif cur and len(line) == 16 and not line.startswith("#"):
                    frames[cur].append(line)
    return pal, frames


PAL, FRAMES = load_pet()


def fox_symbol(name, rows=None, sym_id=None):
    rows = rows if rows is not None else FRAMES[name]
    by = {}
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            c = row[x]
            if c == ".":
                x += 1
                continue
            e = x
            while e < len(row) and row[e] == c:
                e += 1
            by.setdefault(c, []).append(f"M{x} {y}h{e - x}v1h{x - e}z")
            x = e
    paths = "".join(f'<path fill="{PAL[c]}" d="{"".join(d)}"/>' for c, d in by.items())
    return f'<g id="{sym_id or "fx-" + name}">{paths}</g>'


# --------------------------------------------------------------------------- #
# CSS keyframes toolkit
# --------------------------------------------------------------------------- #
class Sheet:
    def __init__(self, T):
        self.T = T
        self.static, self.motion, self.reduce = [], [], []
        self.n = 0

    def pct(self, t):
        p = max(0.0, min(100.0, t / self.T * 100))
        return f"{p:.3f}".rstrip("0").rstrip(".") + "%"

    def uid(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def keyframes(self, name, stops):
        stops = sorted(stops, key=lambda s: s[0])
        if stops[0][0] > 0:
            stops.insert(0, (0, stops[0][1], None))
        if stops[-1][0] < self.T:
            stops.append((self.T, stops[-1][1], None))
        body = "".join(
            f"{self.pct(t)}{{{d};{'animation-timing-function:' + tf + ';' if tf else ''}}}" for t, d, tf in stops
        )
        self.motion.append(f"@keyframes {name}{{{body}}}")

    def animate(self, sel, name, timing="linear"):
        self.motion.append(f"{sel}{{animation:{name} {self.T}s {timing} infinite}}")

    def fade(self, cls, spans, fin=0.3, fout=0.25, rise=0, visible=False):
        name = self.uid("fd")
        hid = "opacity:0" + (f";transform:translateY({rise}px)" if rise else "")
        shw = "opacity:1" + (";transform:translateY(0px)" if rise else "")
        st = [(0, hid, None)]
        for a, b in spans:
            st += [(a, hid, "cubic-bezier(.16,1,.3,1)"), (a + fin, shw, None), (b, shw, "ease-in"), (b + fout, hid, None)]
        self.keyframes(name, st)
        self.animate(f".{cls}", name)
        self.static.append(f".{cls}{{opacity:{1 if visible else 0}}}")

    def steps(self, cls, spans, visible=False):
        """Hard on/off visibility."""
        name = self.uid("st")
        st = [(0, "opacity:0", None)]
        for a, b in spans:
            st += [(a, "opacity:1", None), (b, "opacity:0", None)]
        self.keyframes(name, st)
        self.animate(f".{cls}", name, "steps(1,end)")
        self.static.append(f".{cls}{{opacity:{1 if visible else 0}}}")

    def sprite(self, slot, seq, still, x=0, y=0, scale=1):
        seq = sorted(seq)
        names = []
        for _, fr in seq:
            if fr not in names:
                names.append(fr)
        if still not in names:
            names.append(still)
        uses = []
        for fr in names:
            cls = f"{slot}-{fr.replace('_', '')}"
            ch, last = [], None
            for t, g in seq:
                v = 1 if g == fr else 0
                if v != last:
                    ch.append((t, f"opacity:{v}", None))
                    last = v
            if not ch or ch[0][0] > 0:
                ch.insert(0, (0, "opacity:0", None))
            name = self.uid("sp")
            self.keyframes(name, ch)
            self.animate(f".{cls}", name, "steps(1,end)")
            self.static.append(f".{cls}{{opacity:{1 if fr == still else 0}}}")
            uses.append(f'<use href="#fx-{fr}" class="{cls}"/>')
        return (
            f'<g transform="translate({f(x)} {f(y)}) scale({f(scale)})" shape-rendering="crispEdges">'
            + "".join(uses) + "</g>"
        ), set(names)

    def css(self):
        out = "".join(self.static)
        out += "@media (prefers-reduced-motion: no-preference){" + "".join(self.motion) + "}"
        if self.reduce:
            out += "@media (prefers-reduced-motion: reduce){" + "".join(self.reduce) + "}"
        return out


def cycle(t0, t1, frames, step):
    out, t, i = [], t0, 0
    while t < t1 - 1e-6:
        out.append((round(t, 3), frames[i % len(frames)]))
        t += step
        i += 1
    return out


# --------------------------------------------------------------------------- #
# Document: collects glyphs per font, then embeds subsets
# --------------------------------------------------------------------------- #
class Doc:
    def __init__(self, theme, T=10.0):
        self.th = THEMES[theme]
        self.theme = theme
        self.sh = Sheet(T)
        self.glyphs = defaultdict(set)
        self.frames = set()
        self.defs = []

    # text ------------------------------------------------------------------
    def w(self, s, fam="sans", size=16, weight=400, ls=0.0):
        return FONTS.width(s, fam, size, weight, ls)

    def t(self, x, y, s, fam="sans", size=16, fill=None, weight=None, anchor=None, ls=None, cls="", op=None):
        self.glyphs[fam] |= set(s)
        a = [f'x="{f(x)}"', f'y="{f(y)}"', f'class="{fam}{(" " + cls) if cls else ""}"', f'font-size="{f(size)}"',
             f'fill="{fill or self.th["ink"]}"']
        if weight:
            a.append(f'font-weight="{weight}"')
        if anchor:
            a.append(f'text-anchor="{anchor}"')
        if ls:
            a.append(f'letter-spacing="{f(ls)}"')
        if op is not None:
            a.append(f'fill-opacity="{f(op)}"')
        return f"<text {' '.join(a)}>{esc(s)}</text>"

    def spans(self, x, y, parts, fam="sans", size=16, anchor=None, ls=None, cls=""):
        """parts: [(text, fill, weight_or_None, fam_or_None, size_or_None)]"""
        out = []
        for p in parts:
            s, fill = p[0], p[1]
            wt = p[2] if len(p) > 2 else None
            fm = p[3] if len(p) > 3 and p[3] else fam
            sz = p[4] if len(p) > 4 and p[4] else None
            self.glyphs[fm] |= set(s)
            attrs = f' fill="{fill}"'
            if wt:
                attrs += f' font-weight="{wt}"'
            if fm != fam:
                attrs += f' class="{fm}"'
            if sz:
                attrs += f' font-size="{f(sz)}"'
            out.append(f"<tspan{attrs}>{esc(s)}</tspan>")
        a = f'x="{f(x)}" y="{f(y)}" class="{fam}{(" " + cls) if cls else ""}" font-size="{f(size)}"'
        if anchor:
            a += f' text-anchor="{anchor}"'
        if ls:
            a += f' letter-spacing="{f(ls)}"'
        return f"<text {a}>{''.join(out)}</text>"

    def wrap(self, s, width, fam="sans", size=16, weight=400, ls=0.0):
        lines, cur = [], ""
        for word in s.split():
            nxt = (cur + " " + word).strip()
            if cur and self.w(nxt, fam, size, weight, ls) > width:
                lines.append(cur)
                cur = word
            else:
                cur = nxt
        if cur:
            lines.append(cur)
        return lines

    def caps(self, x, y, s, size=11, fill=None, ls=None, anchor=None, weight=None, cls=""):
        """Tracked uppercase mono label, the site's eyebrow style."""
        return self.t(x, y, s.upper(), "mono", size, fill or self.th["faint"], weight, anchor,
                      ls if ls is not None else size * 0.3, cls)

    def capsw(self, s, size=11, ls=None):
        return self.w(s.upper(), "mono", size, 400, ls if ls is not None else size * 0.3)

    # shapes ----------------------------------------------------------------
    def hline(self, x1, x2, y, a=None, colour=None, w=1):
        return (f'<path d="M{f(x1)} {f(y + .5)}H{f(x2)}" stroke="{colour or self.th["line"]}" '
                f'stroke-opacity="{f(a if a is not None else self.th["lb"])}" stroke-width="{w}"/>')

    def sq(self, x, y, s, fill=None, op=None, cls=""):
        c = f' class="{cls}"' if cls else ""
        o = f' fill-opacity="{f(op)}"' if op is not None else ""
        return f'<rect x="{f(x)}" y="{f(y)}" width="{f(s)}" height="{f(s)}" fill="{fill or self.th["ink"]}"{o}{c}/>'

    def osq(self, cx, cy, s, colour=None, fill="none", cls="", sw=1.25):
        c = f' class="{cls}"' if cls else ""
        return (f'<rect x="{f(cx - s / 2)}" y="{f(cy - s / 2)}" width="{f(s)}" height="{f(s)}" fill="{fill}" '
                f'stroke="{colour or self.th["ink"]}" stroke-width="{sw}"{c}/>')

    def fox(self, slot, seq, still, x, y, scale):
        svg, names = self.sh.sprite(slot, seq, still, x, y, scale)
        self.frames |= names
        return svg

    # output ----------------------------------------------------------------
    def render(self, w, h, title, desc, body):
        css = []
        for fam, chars in self.glyphs.items():
            _, name, weights, fallback = FONT_FILES[fam]
            b64 = FONTS.subset_b64(fam, chars)
            css.append(f'@font-face{{font-family:"{name}";src:url(data:font/woff2;base64,{b64}) format("woff2");'
                       f"font-weight:{weights};font-style:normal}}")
            extra = "font-variant-ligatures:none;" if fam == "mono" else ""
            css.append(f'.{fam}{{font-family:"{name}",{fallback};{extra}}}')
        css.append("text{font-kerning:normal}")
        css.append(self.sh.css())
        defs = "".join(fox_symbol(fr) for fr in sorted(self.frames)) + "".join(self.defs)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="t d" fill="none">'
            f'<title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>'
            f"<style>{''.join(css)}</style><defs>{defs}</defs>{body}</svg>"
        )


def check(cx, cy, s, colour, w=2.0):
    return (f'<path d="M{f(cx - 4.5 * s)} {f(cy + .3 * s)}l{f(3 * s)} {f(3 * s)}l{f(6 * s)} {f(-6.6 * s)}" '
            f'stroke="{colour}" stroke-width="{f(w)}" stroke-linecap="square"/>')


def arrow_ne(x, y, s, colour, w=1.6):
    """↗ drawn as a path (the site's fonts don't carry arrows)."""
    return (f'<path d="M{f(x)} {f(y)}l{f(s)} {f(-s)}M{f(x + s * .25)} {f(y - s)}h{f(s * .75)}v{f(s * .75)}" '
            f'stroke="{colour}" stroke-width="{f(w)}"/>')


def arrow_e(x, y, s, colour, w=1.6):
    return (f'<path d="M{f(x)} {f(y)}h{f(s)}M{f(x + s * .55)} {f(y - s * .45)}l{f(s * .45)} {f(s * .45)}l{f(-s * .45)} {f(s * .45)}" '
            f'stroke="{colour}" stroke-width="{f(w)}"/>')


def hash01(i, j, seed):
    v = math.sin(i * 127.1 + j * 311.7 + seed * 74.7) * 43758.5453
    return v - math.floor(v)


def vnoise(x, y, seed):
    """Smooth value noise in [0, 1]."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b = hash01(xi, yi, seed), hash01(xi + 1, yi, seed)
    c, d = hash01(xi, yi + 1, seed), hash01(xi + 1, yi + 1, seed)
    return (a + (b - a) * u) + ((c + (d - c) * u) - (a + (b - a) * u)) * v


def cloud(x, y, seed, scale=120.0):
    n = (vnoise(x / scale, y / scale, seed) * .62 + vnoise(x / (scale * .45), y / (scale * .45), seed + 9) * .28
         + vnoise(x / (scale * .2), y / (scale * .2), seed + 17) * .10)
    return n


def halftone(field, x0, x1, y0, y1, step, rmax, seed=0):
    """Square-grid halftone; `field(x, y)` in [0, 1] sets each dot's size."""
    out = []
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            v = field(x, y)
            if v > 0.04:
                r = rmax * min(1.0, v) ** 1.15
                if r >= 0.5:
                    out.append(f'<circle cx="{f(round(x, 1))}" cy="{f(round(y, 1))}" r="{f(round(r, 2))}"/>')
            x += step
        y += step
    return "".join(out)


# --------------------------------------------------------------------------- #
# HERO
# --------------------------------------------------------------------------- #
def hero(theme):
    W, H, T = 960, 540, 22.0
    d = Doc(theme, T)
    th, sh = d.th, d.sh
    CX = 480
    IW, IV, IHID, IRX = 500, 112, 50, 30
    CW_, CH_ = 220, 38
    SX, SY = CW_ / IW, CH_ / IV
    col = f"scale({SX:.4f},{SY:.4f})"
    bump = "scale(1.02,1.05)"
    OPEN0, OPEN1 = 3.0, 3.75
    A = [(3.75, 7.6), (7.6, 11.6), (11.6, 15.6), (15.6, 19.4)]
    SHUT0, SHUT1 = 19.4, 20.05

    # island geometry ----------------------------------------------------------
    st = [(0, f"transform:{col}", None), (OPEN0, f"transform:{col}", "cubic-bezier(.3,1.35,.45,1)"),
          (OPEN1, "transform:scale(1,1)", None)]
    for t in (A[1][0], A[2][0], A[3][0]):
        st += [(t - .05, "transform:scale(1,1)", "cubic-bezier(.3,0,.5,1)"), (t + .2, f"transform:{bump}", "cubic-bezier(.3,1.5,.5,1)"),
               (t + .6, "transform:scale(1,1)", None)]
    st += [(SHUT0, "transform:scale(1,1)", "cubic-bezier(.55,0,.3,1.15)"), (SHUT1, f"transform:{col}", None)]
    sh.keyframes("island", st)
    sh.animate(".island", "island")
    sh.static.append(f".island{{transform-origin:{CX}px 0px}}")
    sh.static.append(".rail{opacity:0}")
    rail_kf = sh.uid("rl")
    sh.keyframes(rail_kf, [(0, "opacity:1", None), (OPEN0, "opacity:1", None), (OPEN0 + .2, "opacity:0", None),
                           (SHUT1 - .05, "opacity:0", None), (SHUT1 + .25, "opacity:1", None)])
    sh.animate(".rail", rail_kf)

    # fox path ---------------------------------------------------------------------
    RAIL_Y = 28
    LEFT_X, MID_X = CX - CW_ / 2 + 14, CX - 8
    BIG = (CX - IW / 2 + 26, 30, 3.5)

    def tf(x, y, s, flip=False):
        return f"transform:translate({f(x + (16 * s if flip else 0))}px,{f(y)}px) scale({f(-s if flip else s)},{f(s)})"

    sh.keyframes("foxmove", [
        (0, tf(LEFT_X, RAIL_Y - 16, 1), "linear"),
        (2.4, tf(MID_X, RAIL_Y - 16, 1), None),
        (OPEN0, tf(MID_X, RAIL_Y - 16, 1), "cubic-bezier(.3,1.25,.45,1)"),
        (OPEN1 + .1, tf(*BIG), None),
        (SHUT0, tf(*BIG), "cubic-bezier(.5,0,.3,1.1)"),
        (SHUT1 + .05, tf(MID_X, RAIL_Y - 16, 1), None),
        (SHUT1 + .3, tf(MID_X, RAIL_Y - 16, 1), None),
        (SHUT1 + .35, tf(MID_X, RAIL_Y - 16, 1, True), "linear"),
        (T - .05, tf(LEFT_X, RAIL_Y - 16, 1, True), None),
        (T, tf(LEFT_X, RAIL_Y - 16, 1), None),
    ])
    sh.animate(".fox", "foxmove")
    sh.static.append(f".fox{{transform-origin:0 0;{tf(*BIG)}}}")
    run = ["run_1", "run_2", "run_3", "run_4"]
    seq = cycle(0, 2.4, run, 0.1) + [(2.4, "sit"), (3.2, "sit_blink"), (3.32, "sit")]
    seq += cycle(4.0, 5.4, ["wave_1", "wave_2"], 0.2) + [(5.4, "happy"), (6.6, "sit"), (7.0, "sit_blink"), (7.12, "sit")]
    ct = ["code_type_1", "code_type_2", "code_type_3", "code_type_2"]
    seq += cycle(7.7, 9.6, ct, 0.14) + cycle(9.6, 10.6, ["code_think_1", "code_think_2"], 0.5) + cycle(10.6, 11.6, ct, 0.14)
    seq += [(11.6, "sit"), (11.85, "meet_listen")] + cycle(13.2, 14.6, ["meet_talk_1", "meet_talk_2"], 0.18) + [(14.6, "meet_listen")]
    seq += cycle(15.65, 17.1, ["celebrate_1", "celebrate_2", "celebrate_3"], 0.16) + [(17.1, "code_done"), (18.5, "happy"), (19.3, "sit")]
    seq += cycle(SHUT1 + .35, T, run, 0.1)
    fox = d.fox("fx", seq, "sit", 0, 0, 1)

    # island content -------------------------------------------------------------
    TX = BIG[0] + 56 + 22
    AX = CX + IW / 2 - 38
    acts = [
        ("hello", "hey, I’m Arnav", "CS at BITS Pilani, building AI agents"),
        ("now building", "NEO 2.0", "an AI agent that uses your Mac like you do"),
        ("listening", "“Neo, reply to Sam”", "wake word, speech and routing on device"),
        ("shipped", "NotchHub", "a Dynamic Island for the notch. I live here."),
    ]
    sig = th["signal"]
    content = []
    for i, ((a, b), (eye, title, sub)) in enumerate(zip(A, acts)):
        cls = f"a{i}"
        sh.fade(cls, [(a + .15, b - .25)], rise=4, visible=(i == 0))
        content.append(
            f'<g class="{cls}">'
            + d.caps(TX, 42, eye, 9.5, I_EYE, 2.6)
            + d.t(TX, 69, title, "sans", 21, I_TEXT, 600)
            + d.t(TX, 92, sub, "sans", 14, I_SUB, 400)
            + accessory(d, i, AX, 58, sig) + "</g>"
        )
    pop = sh.uid("pop")
    sh.keyframes(pop, [(0, "transform:scale(.3)", None), (A[3][0] + .25, "transform:scale(.3)", "cubic-bezier(.3,1.7,.5,1)"),
                       (A[3][0] + .7, "transform:scale(1)", None)])
    sh.animate(".pop", pop)
    sh.static.append(".pop,.pulse,.bar{transform-box:fill-box;transform-origin:center}")
    sh.motion.append(
        "@keyframes pulse{0%{transform:scale(1);opacity:.6}100%{transform:scale(2.8);opacity:0}}"
        ".pulse{animation:pulse 1.6s cubic-bezier(.2,.6,.3,1) infinite}"
        "@keyframes blip{0%,100%{opacity:.25}20%{opacity:1}55%{opacity:.25}}"
        ".blip{animation:blip 1.2s steps(1,end) infinite}.blip.b2{animation-delay:.2s}.blip.b3{animation-delay:.4s}"
        "@keyframes bar{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}"
        ".bar{animation:bar .9s ease-in-out infinite}.bar.v2{animation-duration:.7s;animation-delay:-.4s}"
        ".bar.v3{animation-duration:1.1s;animation-delay:-.2s}.bar.v4{animation-duration:.8s;animation-delay:-.6s}"
        ".bar.v5{animation-duration:1s;animation-delay:-.3s}"
    )

    # island + rail --------------------------------------------------------------
    rim = (f'<rect x="{CX - IW / 2}" y="{-IHID}" width="{IW}" height="{IHID + IV}" rx="{IRX}" stroke="#fff" '
           f'stroke-opacity="{th["rim"]}" vector-effect="non-scaling-stroke"/>') if th["rim"] else ""
    island = (f'<g class="island" filter="url(#lift)"><rect x="{CX - IW / 2}" y="{-IHID}" width="{IW}" height="{IHID + IV}" '
              f'rx="{IRX}" fill="{th["island"]}"/>{rim}</g>')
    rail = f'<path class="rail" d="M{CX - CW_ / 2 + 12} {RAIL_Y + .5}H{CX + CW_ / 2 - 12}" stroke="{th["rail"]}"/>'

    # backdrop ---------------------------------------------------------------------
    d.defs.append(
        '<pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">'
        f'<circle cx="10" cy="10" r=".8" fill="{th["dot"]}" fill-opacity="{th["grid"]}"/></pattern>'
        '<radialGradient id="gridFade" cx="50%" cy="45%" r="62%"><stop offset=".35" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="gm"><rect width="{W}" height="{H}" fill="url(#gridFade)"/></mask>'
        f'<linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{th["line"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{th["line"]}" stop-opacity="{th["lb"]}"/>'
        f'<stop offset="1" stop-color="{th["line"]}" stop-opacity="0"/></linearGradient>'
        '<filter id="lift" x="-20%" y="-30%" width="140%" height="190%">'
        f'<feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000" flood-opacity="{th["shadow"] + .08}"/></filter>'
    )

    def edge(y):  # soften the cloud's top and bottom
        return max(0.0, min(1.0, (y - 100) / 110)) * max(0.0, min(1.0, (H + 20 - y) / 60))

    def field_l(x, y):
        reach = max(0.0, min(1.0, (205 - x) / 185)) ** 1.1
        return max(0.0, (cloud(x, y, 3) - .28) * 2.1 + reach * .35 - .12) * reach * edge(y)

    def field_r(x, y):
        reach = max(0.0, min(1.0, (x - 755) / 185)) ** 1.1
        return max(0.0, (cloud(x, y, 8) - .28) * 2.1 + reach * .35 - .12) * reach * edge(y)

    dots_l = halftone(field_l, 4, 250, 100, H, 9, 3.4)
    dots_r = halftone(field_r, 712, W - 4, 100, H, 9, 3.4)

    # headline + copy --------------------------------------------------------------
    L1, L2 = "I build software systems", "that hold together."
    head = (d.t(CX, 224, L1, "pixel", 54, th["ghost"], 500, "middle")
            + d.t(CX, 286, L2, "pixel", 54, th["ink"], 500, "middle"))
    sub = (d.t(CX, 334, "CS at BITS Pilani. I work across AI agents, automation, interfaces", "sans", 18, th["muted"], 400, "middle")
           + d.t(CX, 360, "and the infrastructure underneath.", "sans", 18, th["muted"], 400, "middle"))

    # CTA: pill + fox ---------------------------------------------------------------
    label = "arnavparashar.com"
    tw = d.w(label, "sans", 16, 500)
    pw = 26 + tw + 10 + 11 + 24
    gw = pw + 22 + 48
    px = CX - gw / 2
    py = 392
    cta = (f'<rect x="{f(px)}" y="{py}" width="{f(pw)}" height="48" rx="24" fill="{th["btn"]}"/>'
           + d.t(px + 26, py + 29.5, label, "sans", 16, th["btn_ink"], 500)
           + arrow_ne(px + 26 + tw + 10, py + 29, 9, th["btn_ink"], 1.7))
    idle = ([(0, "sit"), (1.6, "sit_blink"), (1.72, "sit"), (3.0, "sit_tail_1"), (3.2, "sit_tail_2"), (3.4, "sit_tail_1"),
             (3.6, "sit"), (6.0, "sit_look_left"), (7.2, "sit"), (9.6, "sit_blink"), (9.72, "sit"), (12.0, "sit_look_right"),
             (13.0, "sit"), (15.5, "sit_tail_1"), (15.7, "sit_tail_2"), (15.9, "sit_tail_1"), (16.1, "sit"), (19.0, "sit_blink"),
             (19.12, "sit")])
    cta += d.fox("cf", idle, "sit", px + pw + 22, py, 3)

    # stat strip --------------------------------------------------------------------
    parts = [("caps", "NEO 2.0"), ("rule",), ("num", "52"), ("lbl", "tools"), ("dot",), ("num", "~20"), ("lbl", "ms routing"),
             ("dot",), ("num", "0.90"), ("lbl", "intent accuracy"), ("arrow",)]
    widths = []
    for p in parts:
        k = p[0]
        widths.append({"caps": lambda: d.capsw(p[1], 11.5, 4.2), "rule": lambda: 44, "num": lambda: d.w(p[1], "pixel", 21, 500),
                       "lbl": lambda: d.w(p[1], "sans", 15, 400), "dot": lambda: 5, "arrow": lambda: 13}[k]())
    gaps = {"caps": 16, "rule": 18, "num": 6, "lbl": 13, "dot": 13, "arrow": 0}
    total = sum(widths) + sum(gaps[p[0]] for p in parts[:-1])
    x = CX - total / 2
    y = 508
    strip = []
    for p, wd in zip(parts, widths):
        k = p[0]
        if k == "caps":
            strip.append(d.caps(x, y, p[1], 11.5, th["faint"], 4.2))
        elif k == "rule":
            strip.append(d.hline(x, x + wd, y - 5, th["lb"]))
        elif k == "num":
            strip.append(d.t(x, y + 1, p[1], "pixel", 21, th["ink"], 500))
        elif k == "lbl":
            strip.append(d.t(x, y, p[1], "sans", 15, th["muted"], 400))
        elif k == "dot":
            strip.append(d.sq(x, y - 7, 4, th["faint"], .7))
        elif k == "arrow":
            strip.append(arrow_e(x, y - 5, 12, th["ink"], 1.6))
        x += wd + gaps[k]

    head_left = d.t(24, 40, "Arnav Parashar", "mono", 16, th["ink"], 400)
    head_right = d.caps(W - 24, 39, "BITS Pilani · Dubai", 10.5, th["faint"], 3.2, "end")

    body = (
        f'<rect width="{W}" height="{H}" fill="url(#grid)" mask="url(#gm)"/>'
        f'<g fill="{th["dot"]}">{dots_l}{dots_r}</g>'
        f'<rect width="{W}" height="1" fill="url(#edge)"/>'
        + head_left + head_right + island + rail + f'<g class="fox">{fox}</g>' + "".join(content)
        + head + sub + cta + "".join(strip)
    )
    return d.render(
        W, H, "Arnav Parashar",
        "I build software systems that hold together. CS at BITS Pilani. I work across AI agents, automation, "
        "interfaces and the infrastructure underneath. A black notch at the top springs open into a Dynamic Island "
        "where NotchHub's pixel fox says hi, builds NEO 2.0, listens for the wake word and celebrates shipping NotchHub. "
        "NEO 2.0: 52 tools, ~20 ms routing, 0.90 intent accuracy.",
        body,
    )


def accessory(d, i, x, y, sig):
    if i == 0:
        return d.sq(x - 4, y - 4, 8, sig, None, "pulse") + d.sq(x - 4, y - 4, 8, sig)
    if i == 1:
        return "".join(d.sq(x - 17 + j * 12, y - 3, 6, "#FAFAFA", None, f"blip b{j + 1}") for j in range(3))
    if i == 2:
        hs = [10, 20, 28, 18, 10]
        return "".join(f'<rect x="{f(x - 18 + j * 8)}" y="{f(y - h / 2)}" width="4" height="{h}" fill="{sig}" class="bar v{j + 1}"/>'
                       for j, h in enumerate(hs))
    return f'<g class="pop"><rect x="{x - 12}" y="{y - 12}" width="24" height="24" fill="{sig}"/>{check(x, y, 1.0, "#fff", 2.2)}</g>'


# --------------------------------------------------------------------------- #
# Section header: 01 / My Work
# --------------------------------------------------------------------------- #
def section_work(theme):
    W, H = 960, 214
    d = Doc(theme)
    th = d.th
    text = ("NEO 2.0, a voice-first Mac agent with a local router; NotchHub, a native Dynamic Island for the "
            "MacBook notch; and NEO, the menu-bar companion NEO 2.0 replaced.")
    lines = d.wrap(text, 380, "sans", 18.5, 400)
    body = d.t(2, 19, "01", "mono", 12, th["faint"]) + d.hline(34, W, 14, th["lb"])
    body += d.t(-4, 162, "My Work", "pixel", 108, th["ink"], 500)
    y0 = 118 - (len(lines) - 1) * 27 / 2
    for i, ln in enumerate(lines):
        body += d.t(W - 380, y0 + i * 27, ln, "sans", 18.5, th["muted"], 400)
    return d.render(W, H, "01. My Work", "My Work. " + text, body)


# --------------------------------------------------------------------------- #
# Project cards
# --------------------------------------------------------------------------- #
CW, CH = 960, 520


def card_shell(d, eyebrow, title, desc, stats):
    th = d.th
    out = [f'<rect x=".5" y=".5" width="{CW - 1}" height="{CH - 1}" fill="{th["surface"]}" stroke="{th["line"]}" '
           f'stroke-opacity="{th["lb"]}"/>']
    # faint halftone seam between the columns, as on the site
    out.append(f'<g fill="{th["dot"]}" fill-opacity=".5">' + halftone(
        lambda x, y: max(0.0, (cloud(x, y, 5, 60) - .3) * 1.6) * max(0.0, 1 - abs(x - 462) / 28) * min(1.0, y / 120, (CH - y) / 120),
        434, 478, 40, CH - 30, 8, 2.0) + "</g>")
    x = 52
    items = []
    for i, word in enumerate(eyebrow):
        if i:
            items.append(d.sq(x + 7, 66.5, 4, th["faint"], .6))
            x += 24
        items.append(d.caps(x, 72, word, 11, th["muted"], 3.4))
        x += d.capsw(word, 11, 3.4)
    out += items
    out.append(d.t(48, 172, title, "grid", 86, th["ink"], 500))
    for i, ln in enumerate(d.wrap(desc, 392, "sans", 19, 400)):
        out.append(d.t(52, 222 + i * 28, ln, "sans", 19, th["muted"], 400))
    out.append(d.hline(52, 440, 310, th["la"] + .03))
    for i, (num, unit, label) in enumerate(stats):
        cx_ = 52 + (i % 2) * 210
        cy_ = 378 + (i // 2) * 90
        parts = [(num, th["ink"], 500)]
        if unit:
            parts.append((unit, th["ink"], 500, None, 25))
        out.append(d.spans(cx_ - 1, cy_, parts, "pixel", 50))
        out.append(d.caps(cx_, cy_ + 27, label, 10, th["faint"], 3))
    return "".join(out)


def panel(d, x, y, w, h, left, right_cls_texts):
    """White inner panel with the header strip; right header text cycles."""
    th = d.th
    out = (f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" fill="{th["panel"]}" stroke="{th["line"]}" '
           f'stroke-opacity="{th["lb"]}"/>' + d.caps(x + 20, y + 27, left, 10, th["faint"], 2.8)
           + d.hline(x, x + w, y + 42, th["la"] + .02))
    for cls, txt in right_cls_texts:
        out += f'<g class="{cls}">' + d.caps(x + w - 20, y + 27, txt, 10, th["ink"], 2.8, "end", 600) + "</g>"
    return out


def card_neo(theme):
    T = 12.0
    d = Doc(theme, T)
    th, sh = d.th, d.sh
    sig = th["signal"]
    shell = card_shell(
        d, ["Python", "macOS", "voice-first"], "NEO 2.0",
        "An AI agent for your Mac that works the way you do: it reads the screen, clicks, types, runs commands and handles mail.",
        [("52", "", "registered tools"), ("~20", "ms", "encoder pass, M3 Pro"), ("0.90", "", "intent, held-out"),
         ("421M", "", "Laya parameters")],
    )
    PX, PY, PW, PH = 480, 36, 440, 448
    phases = [(0, 4), (4, 8), (8, 12)]
    for k, (a, b) in enumerate(phases):
        sh.steps(f"lane{k}", [(a, b)], visible=(k == 1))
    out = [panel(d, PX, PY, PW, PH, "How a request is routed", [(f"lane{k}", f"Lane 0{k + 1}") for k in range(3)])]

    ink, faint, line_a = th["ink"], th["faint"], th["lb"] + .1
    MY = 300
    RQ = 505          # request node centre x
    BA = 540          # branch to the regex lane
    BOX0, BOX1 = 664, 708
    BB = 730          # branch to the agent loop
    END = 896
    L1Y, L3Y = 150, 440

    def stroke(dd, extra=""):
        return f'<path d="{dd}" stroke="{ink}" stroke-opacity="{f(line_a)}" stroke-width="1.2"{extra}/>'

    # rails
    out.append(stroke(f"M{RQ + 5} {MY}H{BOX0}M{BOX1} {MY}H{END}"))
    out.append(stroke(f"M{BA} {MY}V{L1Y}H{END}"))
    out.append(stroke(f"M{BB} {MY}V{L3Y}H{END}"))
    # request node + router box
    out.append(d.sq(RQ - 5, MY - 5, 10, ink))
    out.append(d.osq((BOX0 + BOX1) / 2, MY, 44, ink, th["panel"], sw=1.4))
    out.append(f'<rect class="boxfl" x="{BOX0 + 1}" y="{MY - 21}" width="42" height="42" fill="{sig}" fill-opacity=".16"/>')
    grid = [1, 1, 0, 1, 0, 1, 0, 1, 1]
    for i, on in enumerate(grid):
        gx = BOX0 + 8 + (i % 3) * 10
        gy = MY - 14 + (i // 3) * 10
        out.append(d.sq(gx, gy, 8, ink, 1 if on else .22))
    out.append(d.t(BOX1, 252, "Laya router", "mono", 12.5, ink, 400, "end"))
    out.append(d.t(BOX1, 270, "1 encoder pass, ~20 ms", "mono", 11, faint, 400, "end"))
    # mid + end nodes
    out.append(d.osq(836, MY, 10, ink, th["panel"]))
    for yy in (L1Y, MY, L3Y):
        out.append(d.osq(END, yy, 10, ink, th["panel"]))
    # lane labels
    labels = [(BA + 150, L1Y, "01", "Regex fast path", "0 LLM calls, ~0 ms"),
              (BB + 16, MY, "02", "Local, then Groq", "~150 ms + first token"),
              (BB + 16, L3Y, "03", "Agent loop", "52 tools until it’s done")]
    for k, (lx, ly, num, name, note) in enumerate(labels):
        out.append(d.spans(lx, ly - 12, [(num + " ", faint), (name, ink)], "mono", 12.5))
        out.append(d.t(lx, ly + 22, note, "mono", 11, faint))
        out.append(f'<g class="lane{k}">' + d.sq(lx - 11, ly - 20.5, 6, sig) + "</g>")
    # the signal: orange overlays drawn on along the chosen lane
    paths = [
        (f"M{RQ + 5} {MY}H{BA}V{L1Y}H{END - 5}", (BA - RQ - 5) + (MY - L1Y) + (END - 5 - BA)),
        (f"M{RQ + 5} {MY}H{BOX0}M{BOX1} {MY}H{END - 5}", (BOX0 - RQ - 5) + (END - 5 - BOX1)),
        (f"M{RQ + 5} {MY}H{BOX0}M{BOX1} {MY}H{BB}V{L3Y}H{END - 5}", (BOX0 - RQ - 5) + (BB - BOX1) + (L3Y - MY) + (END - 5 - BB)),
    ]
    flash = [(0, "opacity:0", None)]
    for k, ((a, b), (pd, L)) in enumerate(zip(phases, paths)):
        if k:  # the signal passes through the router box (the draw-on is roughly linear in the middle)
            tb = a + .4 + 1.4 * (BOX0 - RQ - 5) / L
            flash += [(tb - .05, "opacity:0", None), (tb + .05, "opacity:1", None), (tb + .8, "opacity:0", None)]
    sh.keyframes("flash", flash)
    sh.animate(".boxfl", "flash")
    sh.static.append(".boxfl{opacity:0}")
    for k, ((a, b), (pd, L)) in enumerate(zip(phases, paths)):
        name = sh.uid("dr")
        L = round(L + 2)
        sh.keyframes(name, [
            (0, f"stroke-dashoffset:{L};opacity:1", None),
            (a + .4, f"stroke-dashoffset:{L};opacity:1", "cubic-bezier(.45,0,.2,1)"),
            (a + 1.8, "stroke-dashoffset:0;opacity:1", None),
            (b - .45, "stroke-dashoffset:0;opacity:1", "ease-in"),
            (b - .15, "stroke-dashoffset:0;opacity:0", None),
            (b - .14, f"stroke-dashoffset:{L};opacity:0", None),
        ])
        sh.animate(f".ov{k}", name)
        sh.static.append(f".ov{k}{{stroke-dasharray:{L} {L};stroke-dashoffset:{0 if k == 1 else L};opacity:{1 if k == 1 else 0}}}")
        out.append(f'<path class="ov{k}" d="{pd}" stroke="{sig}" stroke-width="2"/>')
        endy = [L1Y, MY, L3Y][k]
        sh.steps(f"en{k}", [(a + 1.8, b - .15)], visible=(k == 1))
        out.append(f'<rect class="en{k}" x="{END - 5}" y="{endy - 5}" width="10" height="10" fill="{sig}"/>')
    # request label
    out.append(d.caps(RQ - 5, 334, "Request", 10, faint, 2.6))
    reqs = ["turn the volume up", "a factual question", "reply to Sam’s email"]
    for k, ((a, b), r) in enumerate(zip(phases, reqs)):
        sh.fade(f"rq{k}", [(a + .05, b - .35)], fin=.25, fout=.2, rise=3, visible=(k == 1))
        out.append(f'<g class="rq{k}">' + d.t(RQ - 5, 355, r, "mono", 12.5, ink) + "</g>")

    body = shell + "".join(out)
    return d.render(
        CW, CH, "NEO 2.0",
        "NEO 2.0, Python, macOS, voice-first. An AI agent for your Mac that works the way you do: it reads the screen, "
        "clicks, types, runs commands and handles mail. 52 registered tools, ~20 ms encoder pass on an M3 Pro, 0.90 "
        "held-out intent accuracy, 421M-parameter Laya router. Diagram: how a request is routed. Lane 01, regex fast "
        "path, 0 LLM calls. Lane 02, local then Groq, ~150 ms plus first token. Lane 03, the agent loop.",
        body,
    )


def card_notchhub(theme):
    T = 15.0
    d = Doc(theme, T)
    th, sh = d.th, d.sh
    sig = th["signal"]
    shell = card_shell(
        d, ["Swift", "SwiftUI + AppKit", "no Electron"], "NotchHub",
        "A native Dynamic Island for the MacBook notch: quiet until something happens, then it springs open. "
        "And a pixel fox lives in it.",
        [("16", "", "system listeners"), ("5", "", "island states"), ("98", "", "frames of fox"), ("0", "", "web wrappers")],
    )
    PX, PY, PW, PH = 480, 36, 440, 448
    names = ["idle", "wings", "compact", "expanded", "interactive"]
    span = T / len(names)
    win = [(i * span, (i + 1) * span) for i in range(len(names))]
    STILL = 3
    for k, (a, b) in enumerate(win):
        sh.steps(f"stt{k}", [(a, b)], visible=(k == STILL))
    out = [panel(d, PX, PY, PW, PH, "The island, state by state", [(f"stt{k}", f"State 0{k + 1}") for k in range(5)])]
    CX = PX + PW / 2
    TOP = 104
    out.append(d.hline(PX + 20, PX + PW - 20, TOP - 1, th["lb"] + .1))
    geo = [(126, 28, 10), (236, 28, 10), (270, 44, 16), (344, 124, 30), (344, 124, 30)]

    # island shape via SMIL (geometry can't be animated with CSS everywhere)
    def vals(idx):
        w, h, r = geo[idx]
        return w, h, r

    times, xs, ws, hs, rs, splines = [], [], [], [], [], []

    def push(t, w, h, r, spline):
        times.append(t / T)
        xs.append(CX - w / 2)
        ws.append(w)
        hs.append(h + 40)
        rs.append(r)
        splines.append(spline)

    w0, h0, r0 = vals(0)
    push(0, w0, h0, r0, "0 0 1 1")
    for k in range(1, len(names)):
        a = win[k][0]
        pw_, ph_, pr_ = vals(k - 1)
        nw, nh, nr = vals(k)
        push(a, pw_, ph_, pr_, ".3 0 .2 1")
        push(a + .32, nw + (nw - pw_) * .05, nh + (nh - ph_) * .08, nr, ".4 0 .4 1")
        push(a + .6, nw, nh, nr, "0 0 1 1")
    # back to idle at the loop end
    lw, lh, lr = vals(len(names) - 1)
    push(T - .6, lw, lh, lr, ".3 0 .2 1")
    push(T - .05, w0, h0, r0, "0 0 1 1")
    push(T, w0, h0, r0, "0 0 1 1")
    kt = ";".join(f"{t:.4f}" for t in times)
    ks = ";".join(splines[:-1])

    def anim(attr, values):
        return (f'<animate attributeName="{attr}" dur="{T}s" repeatCount="indefinite" calcMode="spline" '
                f'keyTimes="{kt}" keySplines="{ks}" values="{";".join(f(round(v, 2)) for v in values)}"/>')

    sw_, shh, sr = geo[STILL]
    isl_static = f'<rect x="{CX - sw_ / 2}" y="{TOP - 40}" width="{sw_}" height="{shh + 40}" rx="{sr}" fill="{th["island"]}"/>'
    isl_motion = (f'<rect x="{CX - w0 / 2}" y="{TOP - 40}" width="{w0}" height="{h0 + 40}" rx="{r0}" fill="{th["island"]}">'
                  + anim("x", xs) + anim("width", ws) + anim("height", hs) + anim("rx", rs) + "</rect>")
    d.defs.append(f'<clipPath id="below"><rect x="{PX}" y="{TOP}" width="{PW}" height="{PH}"/></clipPath>')
    sh.static.append(".mo{display:none}.st{display:inline}")
    sh.motion.append(".mo{display:inline}.st{display:none}")
    out.append(f'<g clip-path="url(#below)"><g class="st">{isl_static}</g><g class="mo">{isl_motion}</g></g>')

    # contents per state ------------------------------------------------------------
    groups = []
    # 0 idle: fox sits beside the notch, a camera dot in the middle
    g = d.fox("p0", [(0, "sit"), (1.2, "sit_blink"), (1.32, "sit"), (2.0, "sit_look_left")], "sit", CX + 63 + 8, TOP + 4, 1.25)
    groups.append(g + f'<circle cx="{CX}" cy="{TOP + 13}" r="3.2" fill="#161616"/><circle cx="{CX}" cy="{TOP + 13}" r="1.3" fill="#24304A"/>')
    # 1 wings: fox left, battery right
    w, h, _ = geo[1]
    g = d.fox("p1", [(span, "sit"), (span + .6, "sit_tail_1"), (span + .8, "sit_tail_2"), (span + 1.0, "sit_tail_1"), (span + 1.2, "sit")],
              "sit", CX - w / 2 + 12, TOP + 4, 1.25)
    bx = CX + w / 2 - 50
    g += (f'<rect x="{bx}" y="{TOP + 9.5}" width="19" height="10" rx="2.5" stroke="#FAFAFA" stroke-opacity=".55"/>'
          f'<rect x="{bx + 2}" y="{TOP + 11.5}" width="12" height="6" rx="1" fill="#43D68B"/>'
          + d.t(CX + w / 2 - 12, TOP + 18.5, "82%", "mono", 10.5, "#FAFAFA", 500, "end"))
    groups.append(g)
    # 2 compact: now playing
    w, h, _ = geo[2]
    a = win[2][0]
    g = d.fox("p2", cycle(a, a + span, ["music_1", "music_2", "music_3", "music_2"], .32), "music_2", CX - w / 2 + 12, TOP + 7, 1.85)
    g += d.t(CX - w / 2 + 50, TOP + 19, "Now playing", "sans", 12.5, I_TEXT, 600)
    g += d.t(CX - w / 2 + 50, TOP + 34, "lo-fi to build to", "sans", 11, I_SUB, 400)
    for j, hh in enumerate([8, 15, 20, 12]):
        g += f'<rect x="{f(CX + w / 2 - 44 + j * 7)}" y="{f(TOP + 22 - hh / 2)}" width="3.5" height="{hh}" fill="{sig}" class="bar v{j + 1}"/>'
    groups.append(g)
    # 3 expanded: charging
    w, h, _ = geo[3]
    a = win[3][0]
    lx = CX - w / 2 + 24
    g = d.fox("p3", cycle(a, a + span, ["charge_1", "charge_2"], .45), "charge_1", lx, TOP + 22, 3)
    tx = lx + 48 + 20
    g += d.caps(tx, TOP + 34, "power", 9, I_EYE, 2.4)
    g += d.t(tx, TOP + 56, "Charging", "sans", 18, I_TEXT, 600)
    g += d.t(tx, TOP + 75, "82% · 40 min to full", "sans", 12.5, I_SUB, 400)
    track = CX + w / 2 - 24 - tx
    g += f'<rect x="{f(tx)}" y="{TOP + 88}" width="{f(track)}" height="5" fill="#fff" fill-opacity=".14"/>'
    grow = sh.uid("gr")
    sh.keyframes(grow, [(0, "transform:scaleX(.6)", None), (a + .4, "transform:scaleX(.6)", "cubic-bezier(.16,1,.3,1)"),
                        (a + 2.4, "transform:scaleX(1)", None)])
    sh.animate(".grow", grow)
    sh.static.append(".grow{transform-box:fill-box;transform-origin:left center}")
    g += f'<rect class="grow" x="{f(tx)}" y="{TOP + 88}" width="{f(track * .82)}" height="5" fill="{sig}"/>'
    groups.append(g)
    # 4 interactive: NEO asks before acting
    a = win[4][0]
    g = d.fox("p4", [(a, "notify"), (a + 1.2, "alert"), (a + 2.2, "happy")], "notify", lx, TOP + 22, 3)
    g += d.caps(tx, TOP + 34, "neo", 9, I_EYE, 2.4)
    g += d.t(tx, TOP + 56, "Needs your OK", "sans", 18, I_TEXT, 600)
    g += d.t(tx, TOP + 75, "Send this reply to Sam?", "sans", 12.5, I_SUB, 400)
    g += (f'<rect x="{f(tx)}" y="{TOP + 86}" width="70" height="24" rx="12" fill="#FAFAFA"/>'
          + d.t(tx + 35, TOP + 102, "Allow", "sans", 12, "#0B0B0B", 600, "middle")
          + f'<rect x="{f(tx + 78)}" y="{TOP + 86}" width="70" height="24" rx="12" fill="#fff" fill-opacity=".12"/>'
          + d.t(tx + 113, TOP + 102, "Cancel", "sans", 12, "#D4D4D4", 500, "middle"))
    press = sh.uid("pr")
    sh.keyframes(press, [(0, "opacity:0", None), (a + 2.0, "opacity:0", None), (a + 2.1, "opacity:.9", None), (a + 2.5, "opacity:0", None)])
    sh.animate(".press", press)
    sh.static.append(".press{opacity:0}")
    g += f'<rect class="press" x="{f(tx)}" y="{TOP + 86}" width="70" height="24" rx="12" fill="{sig}"/>'
    groups.append(g)
    for k, g in enumerate(groups):
        a, b = win[k]
        sh.fade(f"gs{k}", [(a + (0 if k == 0 else .35), b - .15)], fin=.3, fout=.12, visible=(k == STILL))
        out.append(f'<g class="gs{k}">{g}</g>')
    sh.static.append(".bar{transform-box:fill-box;transform-origin:center}")
    sh.motion.append(
        "@keyframes bar{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}"
        ".bar{animation:bar .9s ease-in-out infinite}.bar.v2{animation-duration:.7s;animation-delay:-.4s}"
        ".bar.v3{animation-duration:1.1s;animation-delay:-.2s}.bar.v4{animation-duration:.8s;animation-delay:-.6s}"
    )

    # caption + state machine ---------------------------------------------------------
    captions = ["Invisible. Just the notch, and a fox beside it.", "Small facts tuck in beside the notch.",
                "Live activity: music, timers, calls.", "Opens for detail, then springs back.",
                "Asks before NEO does anything it can’t undo."]
    for k, c in enumerate(captions):
        a, b = win[k]
        sh.fade(f"cap{k}", [(a + .3, b - .2)], fin=.3, fout=.2, rise=3, visible=(k == STILL))
        out.append(f'<g class="cap{k}">' + d.t(CX, 304, c, "sans", 15, th["muted"], 400, "middle") + "</g>")
    nx0, nx1, ny = PX + 50, PX + PW - 50, 398
    step = (nx1 - nx0) / 4
    out.append(f'<path d="M{nx0} {ny}H{nx1}" stroke="{th["ink"]}" stroke-opacity="{f(th["lb"] + .1)}" stroke-width="1.2"/>')
    for k, nm in enumerate(names):
        x = nx0 + k * step
        out.append(d.osq(x, ny, 10, th["ink"], th["panel"]))
        out.append(f'<g class="stt{k}">' + d.sq(x - 5, ny - 5, 10, sig) + "</g>")
        out.append(d.t(x, ny + 30, nm, "mono", 11.5, th["faint"], 400, "middle"))
        out.append(f'<g class="stt{k}">' + d.t(x, ny + 30, nm, "mono", 11.5, th["ink"], 600, "middle") + "</g>")
        out.append(d.t(x, ny - 16, f"0{k + 1}", "mono", 10, th["faint"], 400, "middle"))

    body = shell + "".join(out)
    return d.render(
        CW, CH, "NotchHub",
        "NotchHub, Swift, SwiftUI and AppKit, no Electron. A native Dynamic Island for the MacBook notch: quiet until "
        "something happens, then it springs open. A pixel fox lives in it. 16 system listeners, 5 island states, "
        "98 frames of fox, 0 web wrappers. Diagram: the island morphing through its five states, idle, wings, compact, "
        "expanded and interactive.",
        body,
    )


# --------------------------------------------------------------------------- #
# 02 / The stack
# --------------------------------------------------------------------------- #
def stack(theme):
    T = 9.0
    d = Doc(theme, T)
    th, sh = d.th, d.sh
    sig = th["signal"]
    W = 960
    layers = [  # top to bottom
        ("04", "AI", "Model and agent integration inside working systems, not demos.",
         "NEO 2.0 routes on device: Laya (421M) plus five small heads trained on ~16k utterances. "
         "0.90 held-out on intent, against 0.44 for Laya zero-shot.", "radial"),
        ("03", "Automation", "Pipelines, scripts and tooling that remove repeated work.",
         "NEO 2.0 registers 52 tools as plain Python functions.", "edge"),
        ("02", "Interfaces", "Front ends and interaction behaviour that get used, measured and revised.",
         "NEO: a voice-first companion in the macOS menu bar. NotchHub: a Dynamic Island for the notch.", "ring"),
        ("01", "Infrastructure", "Services, deployment and the parts that have to stay up.",
         "Wake word, speech and routing on device; Gemini and Groq free tiers, or Gemma 4 locally.", "dense"),
    ]
    LX, LW = 548, 404
    # label column layout
    entries, y = [], 168
    for num, name, desc, note, _ in layers:
        dl = d.wrap(desc, LW, "sans", 17, 400)
        nl = d.wrap(note, LW - 20, "mono", 11.5, 400)
        hgt = 52 + len(dl) * 24 + 12 + len(nl) * 18
        entries.append((y, dl, nl, hgt))
        y += hgt + 34
    H = int(y + 34)

    out = [d.t(2, 19, "02", "mono", 12, th["faint"]), d.hline(34, W, 14, th["lb"]),
           d.t(0, 84, "The stack", "sans", 38, th["ink"], 600), d.t(0, 116, "Four layers, three seams.", "sans", 19, th["muted"], 400)]

    CXp, A_, B_, TH_ = 262, 196, 113, 14
    c0, c3 = entries[0][0] + 104, entries[3][0] + 40
    stepc = min((c3 - c0) / 3, 2 * B_ - 70)
    mid = (c0 + c3) / 2
    centers = [round(mid + (i - 1.5) * stepc) for i in range(4)]
    plate_svg = []
    seam_of = {3: 0, 2: 1, 1: 2}   # plate index -> seam number (lit in this order)
    seam_t = [1.2, 3.0, 4.8]
    for k in range(3):
        sh.steps(f"sm{k}", [(seam_t[k], T - .5)], visible=True)
    counts = [(0, seam_t[0]), (seam_t[0], seam_t[1]), (seam_t[1], seam_t[2]), (seam_t[2], T - .5)]
    for idx in reversed(range(4)):
        cy = centers[idx]
        kind = layers[idx][4]
        g = []
        g.append(f'<path d="M{CXp - A_} {cy}L{CXp} {cy + B_}V{cy + B_ + TH_}L{CXp - A_} {cy + TH_}z" fill="{th["side_l"]}"/>')
        g.append(f'<path d="M{CXp} {cy + B_}L{CXp + A_} {cy}V{cy + TH_}L{CXp} {cy + B_ + TH_}z" fill="{th["side_r"]}"/>')
        g.append(f'<path d="M{CXp} {cy - B_}L{CXp + A_} {cy}L{CXp} {cy + B_}L{CXp - A_} {cy}z" fill="{th["plate"]}" '
                 f'stroke="{th["line"]}" stroke-opacity="{f(th["lb"])}"/>')
        n = 13
        dots = []
        for i in range(n):
            for j in range(n):
                u = -1 + (i + .5) * 2 / n
                v = -1 + (j + .5) * 2 / n
                dist = math.sqrt(u * u + v * v) / math.sqrt(2)
                if kind == "radial":
                    val = (1 - dist) ** 1.7
                elif kind == "edge":
                    val = dist ** 1.6
                elif kind == "ring":
                    val = math.exp(-((dist - .62) / .2) ** 2) * .9 + .1
                else:
                    val = .35 + .55 * dist
                val += (hash01(i, j, idx) - .5) * .08
                r = .075 * max(.12, min(1, val))
                dots.append(f'<circle cx="{f(round(u, 3))}" cy="{f(round(v, 3))}" r="{f(round(r, 4))}"/>')
        g.append(f'<g transform="matrix({A_ / 2} {B_ / 2} {-A_ / 2} {B_ / 2} {CXp} {cy})" fill="{th["dot"]}" '
                 f'fill-opacity=".86">{"".join(dots)}</g>')
        if idx in seam_of:
            s = seam_of[idx]
            g.append(f'<g class="sm{s}"><path d="M{CXp - A_} {cy}L{CXp} {cy + B_}L{CXp + A_} {cy}" stroke="{sig}" stroke-width="1.6"/>'
                     + d.sq(CXp - A_ - 3, cy - 3, 6, sig) + d.sq(CXp - 3, cy + B_ - 3, 6, sig) + d.sq(CXp + A_ - 3, cy - 3, 6, sig)
                     + "</g>")
        plate_svg.append(f'<g filter="url(#plate)">{"".join(g)}</g>')
    d.defs.append('<filter id="plate" x="-20%" y="-20%" width="140%" height="160%">'
                  f'<feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000" flood-opacity="{th["shadow"]}"/></filter>')
    out += plate_svg

    # leaders + labels
    for idx, ((num, name, _, _, _), (ey, dl, nl, hgt)) in enumerate(zip(layers, entries)):
        cy = centers[idx]
        lead = f"M{CXp + A_ + 2} {cy}L{LX - 48} {ey}H{W}"
        out.append(f'<path d="{lead}" stroke="{th["ink"]}" stroke-opacity="{f(th["lb"])}"/>')
        out.append(f'<circle cx="{CXp + A_}" cy="{cy}" r="2.6" fill="{th["panel"]}" stroke="{th["ink"]}"/>')
        if idx in seam_of:
            out.append(f'<g class="sm{seam_of[idx]}"><path d="{lead}" stroke="{th["ink"]}" stroke-width="1.2"/></g>')
        out.append(d.t(LX, ey + 44, num, "mono", 12, th["faint"]))
        out.append(d.t(LX + 30, ey + 46, name, "sans", 38, th["ink"], 400))
        for i, ln in enumerate(dl):
            out.append(d.t(LX, ey + 80 + i * 24, ln, "sans", 17, th["muted"], 400))
        ny = ey + 80 + len(dl) * 24 + 10
        bullet_col = th["ink"]
        out.append(d.sq(LX, ny - 6, 6, bullet_col))
        if idx in seam_of:
            out.append(f'<g class="sm{seam_of[idx]}">' + d.sq(LX, ny - 6, 6, sig) + "</g>")
        for i, ln in enumerate(nl):
            out.append(d.t(LX + 20, ny + i * 18, ln, "mono", 11.5, th["muted"]))

    # footer row: seams counter + languages
    for k, (a, b) in enumerate(counts):
        sh.steps(f"ct{k}", [(a, b)], visible=(k == 3))
        out.append(f'<g class="ct{k}">' + d.caps(0, H - 18, f"Seams lit {k}/3", 11, th["muted"], 3.4) + "</g>")
    x = W
    items = []
    for name, colour in reversed(LANG):
        wdt = d.capsw(name, 10.5, 3)
        x -= wdt
        items.append(d.caps(x, H - 18, name, 10.5, th["muted"], 3))
        x -= 15
        items.append(d.sq(x, H - 25.5, 7, colour))
        x -= 20
    lbl = "built with"
    x -= d.capsw(lbl, 10.5, 3) - 6
    items.append(d.caps(x, H - 18, lbl, 10.5, th["faint"], 3))
    out += items

    return d.render(
        W, H, "02. The stack",
        "The stack: four layers, three seams. 04 AI: model and agent integration inside working systems, not demos. "
        "03 Automation: pipelines, scripts and tooling that remove repeated work. 02 Interfaces: front ends and "
        "interaction behaviour that get used, measured and revised. 01 Infrastructure: services, deployment and the "
        "parts that have to stay up. Built with Python, Swift, TypeScript, Rust and CSS.",
        "".join(out),
    )


# --------------------------------------------------------------------------- #
# Footer: the fox runs along the hairline
# --------------------------------------------------------------------------- #
def footer(theme):
    W, H, T = 960, 130, 14.0
    d = Doc(theme, T)
    th, sh = d.th, d.sh
    LINE = 74
    S = 3
    FY = LINE - 16 * S
    SIT = 440
    run = ["run_1", "run_2", "run_3", "run_4"]
    seq = [(0, "run_1")] + cycle(.2, 2.9, run, .09) + [(2.9, "skid"), (3.3, "sit")]
    seq += cycle(3.8, 5.4, ["wave_1", "wave_2"], .2) + [(5.4, "happy"), (6.6, "sit"), (7.4, "sit_blink"), (7.52, "sit"),
                                                          (8.3, "sit_look_right"), (8.9, "alert"), (9.2, "jump_crouch")]
    seq += cycle(9.4, 12.4, run, .09) + [(12.4, "sit")]
    fox = d.fox("ff", seq, "sit", 0, 0, S)

    def tf(x):
        return f"transform:translate({x}px,{FY}px)"

    sh.keyframes("run", [(0, tf(-70), None), (.2, tf(-70), "cubic-bezier(.25,.1,.3,1)"), (2.9, tf(SIT - 16), "cubic-bezier(.2,.6,.3,1)"),
                         (3.3, tf(SIT), None), (9.4, tf(SIT), "cubic-bezier(.6,0,.9,.6)"), (12.3, tf(1010), None)])
    sh.animate(".runner", "run")
    sh.static.append(f".runner{{{tf(SIT)}}}")
    sh.fade("bye", [(3.9, 9.0)], fin=.25, fout=.2, rise=3)
    bubble_x, bubble_y = SIT + 54, FY - 6
    bw = d.w("bye!", "mono", 12, 500) + 18
    bubble = (f'<g class="bye"><rect x="{bubble_x}" y="{bubble_y - 18}" width="{f(bw)}" height="24" fill="{th["btn"]}"/>'
              f'<path d="M{bubble_x} {bubble_y + 6}v7l7 -7z" fill="{th["btn"]}"/>'
              + d.t(bubble_x + 9, bubble_y - 1.5, "bye!", "mono", 12, th["btn_ink"], 500) + "</g>")
    d.defs.append(f'<linearGradient id="fl" x1="0" x2="1"><stop offset="0" stop-color="{th["line"]}" stop-opacity="0"/>'
                  f'<stop offset=".12" stop-color="{th["line"]}" stop-opacity="{th["lb"] + .06}"/>'
                  f'<stop offset=".88" stop-color="{th["line"]}" stop-opacity="{th["lb"] + .06}"/>'
                  f'<stop offset="1" stop-color="{th["line"]}" stop-opacity="0"/></linearGradient>')
    right = "arnavparashar.com"
    rw = d.capsw(right, 11, 3.4)
    body = (f'<rect y="{LINE}" width="{W}" height="1" fill="url(#fl)"/>'
            + f'<g class="runner">{fox}</g>' + bubble
            + d.caps(0, 114, "Thanks for stopping by", 11, th["faint"], 3.4)
            + d.caps(W - 20, 114, right, 11, th["ink"], 3.4, "end")
            + arrow_ne(W - 12, 113, 8, th["ink"], 1.5))
    return d.render(W, H, "Thanks for stopping by",
                    "NotchHub's pixel fox runs along a hairline, stops, waves and says bye, then runs off. "
                    "Thanks for stopping by. arnavparashar.com", body)


def main():
    builders = [("hero", hero), ("section-work", section_work), ("card-neo", card_neo),
                ("card-notchhub", card_notchhub), ("stack", stack), ("footer", footer)]
    for theme in THEMES:
        os.makedirs(os.path.join(OUT_DIR, theme), exist_ok=True)
        for name, fn in builders:
            svg = fn(theme)
            path = os.path.join(OUT_DIR, theme, f"{name}.svg")
            with open(path, "w") as fh:
                fh.write(svg)
            print(f"  {theme}/{name + '.svg':<20} {len(svg) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
