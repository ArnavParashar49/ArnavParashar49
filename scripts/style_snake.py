#!/usr/bin/env python3
"""Restyles Platane/snk's contribution snake to match the rest of the README.

- the site's palette: contribution levels in ink greys, the snake in signal orange
- square cells, like the site's square nodes
- a long comet tail: snk draws 4 segments; extra ones replay the last segment's
  path a step or more behind, shrinking and fading
- cells glow orange for a moment as they're eaten, then go dark

Runs in .github/workflows/snake.yml right after snk (standard library only):

    python3 scripts/style_snake.py light dist/github-snake.svg
    python3 scripts/style_snake.py dark  dist/github-snake-dark.svg
"""
import re
import sys

PALETTES = {
    "light": dict(cb="#0b0b0b0f", cs="#DD6A1F", ch="#F2A66E", ce="#EDEDEB",
                  levels=["#C9C9C7", "#9A9A98", "#5C5C5C", "#0B0B0B"]),
    "dark": dict(cb="#f0f6fc0d", cs="#EC7A2C", ch="#9A4A16", ce="#161B22",
                 levels=["#2D333B", "#545D68", "#9198A1", "#F0F6FC"]),
}
TAIL = 8       # extra tail segments behind snk's four
GLOW = 2.2     # how long an eaten cell glows, in % of the loop


def restyle(theme, path):
    p = PALETTES[theme]
    with open(path) as fh:
        s = fh.read()

    # palette ------------------------------------------------------------------
    root = (f":root{{--cb:{p['cb']};--cs:{p['cs']};--ch:{p['ch']};--ce:{p['ce']};--c0:{p['ce']};"
            + "".join(f"--c{i + 1}:{c};" for i, c in enumerate(p["levels"])) + "}")
    s, n = re.subn(r":root\{[^}]*\}", root, s, count=1)
    assert n == 1, "snk palette block not found"

    # eaten cells flash orange, then fade to empty ------------------------------
    def ember(m):
        name, eat, lvl, gone = m.group(1), m.group(2), m.group(3), float(m.group(4))
        end = min(gone + GLOW, 100.0)
        return (f"@keyframes {name}{{{eat}%{{fill:var(--c{lvl})}}{m.group(4)}%{{fill:var(--ch)}}"
                f"{end:.2f}%,100%{{fill:var(--ce)}}}}")

    s, n = re.subn(r"@keyframes (c\w*)\{([\d.]+)%\{fill:var\(--c(\d)\)\}([\d.]+)%,100%\{fill:var\(--ce\)\}\}", ember, s)
    print(f"  {path}: {n} cells glow when eaten")

    # square cells ---------------------------------------------------------------
    s = re.sub(r'(<rect class="c[^"]*"[^>]*?) rx="[\d.]+" ry="[\d.]+"', r'\1 rx="1.5" ry="1.5"', s)

    # snake: square segments, a fading comet tail ----------------------------------
    dur = int(re.search(r"\.s\{[^}]*?(\d+)ms", s).group(1))
    s0 = re.search(r"@keyframes s0\{(.*?)\}\}", s).group(1)
    pcts = sorted({float(x) for x in re.findall(r"([\d.]+)%", s0)})
    step_ms = min(b - a for a, b in zip(pcts, pcts[1:]) if b - a > 0.01) / 100 * dur

    def square(m):
        r = 2.5 if m.group(1) == "0" else 2
        return m.group(0).replace(f'rx="{m.group(4)}" ry="{m.group(4)}"', f'rx="{r}" ry="{r}"')

    s = re.sub(r'<rect class="s s(\d)" x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="[\d.]+" rx="([\d.]+)" ry="[\d.]+"/>',
               square, s)
    tail = []
    for k in range(1, TAIL + 1):
        size = round(9.6 - k * 0.7, 2)
        off = round((16 - size) / 2, 2)
        delay = -(dur - k * step_ms)        # = k steps behind, for a looping animation
        op = round(0.82 - k * 0.085, 3)
        tail.append(f'<rect class="s s3" x="{off}" y="{off}" width="{size}" height="{size}" rx="1.5" ry="1.5" '
                    f'style="animation-delay:{delay:.0f}ms;opacity:{op}"/>')
    first = s.index('<rect class="s s0"')
    s = s[:first] + "".join(reversed(tail)) + s[first:]
    s = s.replace("</style>", ".s.s1{opacity:.95}.s.s2{opacity:.9}.s.s3{opacity:.85}"
                              ".s.s0{filter:drop-shadow(0 0 3px var(--cs))}</style>", 1)

    with open(path, "w") as fh:
        fh.write(s)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in PALETTES:
        sys.exit("usage: style_snake.py light|dark FILE.svg [FILE.svg ...]")
    for f in sys.argv[2:]:
        restyle(sys.argv[1], f)
