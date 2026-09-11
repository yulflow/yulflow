#!/usr/bin/env python3
"""README에 들어가는 SVG를 굽는다. 텍스트는 전부 윤곽선 <path>로 변환한다.

GitHub은 README 이미지를 camo 프록시로 감싸기 때문에 SVG 안에서 웹폰트·외부
이미지·외부 CSS를 불러올 수 없다. 그래서 필요한 글자를 harfbuzz로 셰이핑한 뒤
글리프 윤곽선을 직접 path로 써 넣는다. CSS @keyframes는 프록시를 통과하므로
애니메이션만 살려 둔다.

    uv run --with fonttools --with uharfbuzz python scripts/build-assets.py

토큰 정본: seoyulson-site/DESIGN.md
"""

from __future__ import annotations

import io
import math
import random
import subprocess
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.transform import Transform
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONTDIR = Path(__file__).resolve().parent / "fonts"
OUT = ROOT / "assets"
GF = "https://github.com/google/fonts/raw/main/"

# ---- design tokens (DESIGN.md) ----
BG = "#111210"
INK = "#f0eadf"
INK_DIM = "#b8ac9c"
INK_FAINT = "#7d756b"
ACCENT = "#d0a05a"   # amber, 강조 전용
MINERAL = "#86aaa0"  # 보조 라벨 큐 전용
HAIR = "rgba(240,234,223,0.14)"

# (키, google/fonts 경로, 고정할 가변축)
FONTS = {
    "display":   ("ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf", {"wght": 350}),
    "italic":    ("ofl/cormorantgaramond/CormorantGaramond-Italic%5Bwght%5D.ttf", {"wght": 350}),
    "mono":      ("ofl/spacemono/SpaceMono-Regular.ttf", None),
    "mono-bold": ("ofl/spacemono/SpaceMono-Bold.ttf", None),
    "body":      ("ofl/inter/Inter%5Bopsz,wght%5D.ttf", {"wght": 300, "opsz": 14}),
    "ko":        ("ofl/notoserifkr/NotoSerifKR%5Bwght%5D.ttf", {"wght": 400}),
}

_loaded: dict[str, tuple] = {}


def num(v: float) -> str:
    """좌표를 소수점 2자리로 줄인다."""
    r = round(v, 2)
    if r == int(r):
        return str(int(r))
    return f"{r:.2f}".rstrip("0")


def source_ttf(key: str) -> Path:
    """원본 TTF를 받아 scripts/fonts/에 캐시한다."""
    path, _ = FONTS[key]
    dest = FONTDIR / path.rsplit("/", 1)[-1].replace("%5B", "[").replace("%5D", "]")
    if not dest.exists():
        FONTDIR.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(GF + path) as r:
                dest.write_bytes(r.read())
        except OSError:
            # 일부 실행 환경은 파이썬 소켓만 막는다. curl로 한 번 더 시도한다.
            subprocess.run(["curl", "-sL", "--fail", "--max-time", "300",
                            "-o", str(dest), GF + path], check=True)
    return dest


def load(key: str):
    """가변 폰트를 원하는 weight로 인스턴스화한 뒤 (TTFont, hb.Font, upem)을 돌려준다."""
    if key in _loaded:
        return _loaded[key]
    _, axes = FONTS[key]
    cache = FONTDIR / f"{key}.inst.ttf"
    if not cache.exists():
        tt = TTFont(source_ttf(key))
        if axes:
            tt = instancer.instantiateVariableFont(tt, axes, inplace=False)
        tt.save(cache)
    data = cache.read_bytes()
    tt = TTFont(io.BytesIO(data))
    face = hb.Face(data)
    hbf = hb.Font(face)
    hb.ot_font_set_funcs(hbf)
    _loaded[key] = (tt, hbf, face.upem)
    return _loaded[key]


def measure(key: str, text: str, size: float, tracking: float = 0.0) -> float:
    """마지막 글자 뒤 자간을 뺀 실제 폭."""
    _, hbf, upem = load(key)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": True, "liga": True})
    s = size / upem
    w = sum(p.x_advance for p in buf.glyph_positions) * s
    return w + tracking * max(len(buf.glyph_infos) - 1, 0)


def text_path(key: str, text: str, size: float, x: float, y: float,
              tracking: float = 0.0, anchor: str = "start") -> str:
    """셰이핑된 글리프 윤곽선을 하나의 path d 문자열로 합친다."""
    tt, hbf, upem = load(key)
    glyph_set = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": True, "liga": True})
    s = size / upem

    if anchor != "start":
        w = measure(key, text, size, tracking)
        x = x - w if anchor == "end" else x - w / 2

    parts: list[str] = []
    pen_x = x
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        gx = pen_x + pos.x_offset * s
        gy = y - pos.y_offset * s
        pen = SVGPathPen(glyph_set, ntos=num)
        glyph_set[name].draw(TransformPen(pen, Transform(s, 0, 0, -s, gx, gy)))
        d = pen.getCommands()
        if d:
            parts.append(d)
        pen_x += pos.x_advance * s + tracking
    return "".join(parts)


def t(key: str, text: str, size: float, x: float, y: float, fill: str,
      tracking: float = 0.0, anchor: str = "start", opacity: str | None = None) -> str:
    d = text_path(key, text, size, x, y, tracking, anchor)
    op = f' opacity="{opacity}"' if opacity else ""
    return f'  <path d="{d}" fill="{fill}"{op}/>\n'


# ---------------------------------------------------------------- waveform

def waveform(x0: float, x1: float, y: float, n: int, seed: int) -> str:
    """양 끝이 잦아드는 파형 막대. 5개 클래스로 나눠 서로 다른 주기로 숨쉰다."""
    rng = random.Random(seed)
    classes = "abcde"
    out = [f'  <g class="wave">\n']
    step = (x1 - x0) / (n - 1)
    for i in range(n):
        px = x0 + i * step
        u = i / (n - 1)
        # 양 끝 페이드 + 느린/빠른 두 개의 마디감 + 약간의 요동 = 눈금 아닌 소리
        env = math.sin(math.pi * u) ** 0.42
        slow = 0.5 + 0.5 * abs(math.sin(u * math.pi * 2.7 + 0.7))
        fast = 0.55 + 0.45 * abs(math.sin(u * math.pi * 8.3 + 1.9))
        amp = (0.7 + 15.5 * slow * fast * rng.uniform(0.6, 1.0)) * env + 0.6
        c = classes[rng.randrange(5)]
        delay = -rng.random() * 4.2
        out.append(
            f'    <line x1="{num(px)}" y1="{num(y - amp)}" x2="{num(px)}" y2="{num(y + amp)}"'
            f' class="b p{c}" style="animation-delay:{delay:.2f}s"/>\n'
        )
    out.append("  </g>\n")
    return "".join(out)


def rings(items: list[tuple[float, float, float, str]]) -> str:
    """겹치는 얇은 링. 포트폴리오 모티프."""
    out = []
    for cx, cy, r, extra in items:
        out.append(f'    <circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="none"'
                   f' stroke="{HAIR}" stroke-width="1"{extra}/>\n')
    return "".join(out)


# ---------------------------------------------------------------- assets

HERO_W, HERO_H = 880, 300


def build_hero() -> str:
    meta = "SEOUL · MARTE, DONGGUK UNIV. · ESTHER MUSIC ACADEMY"
    role = "COMPOSER · SOUND ARTIST · BUILDS WITH AI AGENTS"
    wave_y = 250.0

    s = [
        f'<svg viewBox="0 0 {HERO_W} {HERO_H}" width="{HERO_W}" height="{HERO_H}"'
        ' xmlns="http://www.w3.org/2000/svg" role="img"'
        ' aria-label="Seoyul Son 손서율 · composer, sound artist, builds with AI agents">\n',
        "  <title>Seoyul Son · 손서율</title>\n",
        "  <style>\n"
        "    .b { transform-box: fill-box; transform-origin: center; stroke: %s;\n"
        "         stroke-width: 1.25; stroke-linecap: round; opacity: 0.85; }\n"
        "    .pa { animation: ka 5.2s ease-in-out infinite; }\n"
        "    .pb { animation: kb 5.9s ease-in-out infinite; }\n"
        "    .pc { animation: kc 6.4s ease-in-out infinite; }\n"
        "    .pd { animation: kd 7.1s ease-in-out infinite; }\n"
        "    .pe { animation: ke 7.8s ease-in-out infinite; }\n"
        "    .head { animation: sweep 18s cubic-bezier(0.2,0.8,0.2,1) infinite; }\n"
        "    .spin { transform-origin: 777px 150px; animation: spin 120s linear infinite; }\n"
        "    @keyframes ka { 0%%,100%% { transform: scaleY(0.86); } 45%% { transform: scaleY(1.14); } }\n"
        "    @keyframes kb { 0%%,100%% { transform: scaleY(0.8);  } 55%% { transform: scaleY(1.2);  } }\n"
        "    @keyframes kc { 0%%,100%% { transform: scaleY(0.9);  } 50%% { transform: scaleY(1.1);  } }\n"
        "    @keyframes kd { 0%%,100%% { transform: scaleY(0.83); } 60%% { transform: scaleY(1.17); } }\n"
        "    @keyframes ke { 0%%,100%% { transform: scaleY(0.88); } 40%% { transform: scaleY(1.12); } }\n"
        "    @keyframes spin { to { transform: rotate(360deg); } }\n"
        "    @keyframes sweep {\n"
        "      0%%   { transform: translateX(0px);   opacity: 0; }\n"
        "      8%%   { opacity: 1; }\n"
        "      92%%  { opacity: 1; }\n"
        "      100%% { transform: translateX(784px); opacity: 0; }\n"
        "    }\n"
        "    @media (prefers-reduced-motion: reduce) {\n"
        "      .pa, .pb, .pc, .pd, .pe, .head, .spin { animation: none; }\n"
        "      .head { opacity: 1; }\n"
        "    }\n"
        "  </style>\n" % INK_FAINT,
        f'  <clipPath id="frame"><rect x="0" y="0" width="{HERO_W}" height="{HERO_H}"/></clipPath>\n',
        f'  <rect x="0" y="0" width="{HERO_W}" height="{HERO_H}" fill="{BG}"/>\n',
        '  <g clip-path="url(#frame)">\n',
        rings([(742, 150, 118, ""), (812, 150, 118, ""),
               (777, 150, 62, ' stroke-dasharray="1 7" class="spin"')]),
        f'    <circle cx="777" cy="37.3" r="2.4" fill="{ACCENT}"/>\n',
        "  </g>\n",
    ]

    # 상단 메타 행
    s.append(f'  <rect x="48" y="38.5" width="4" height="4" fill="{MINERAL}"/>\n')
    s.append(t("mono", meta, 12.5, 62, 45, INK_FAINT, tracking=2.6))
    s.append(f'  <line x1="48" y1="66.5" x2="832" y2="66.5" stroke="{HAIR}" stroke-width="1"/>\n')

    # 이름
    s.append(t("display", "Seoyul Son", 92, 46, 152, INK))
    name_w = measure("display", "Seoyul Son", 92)
    sep = 46 + name_w + 34
    s.append(f'  <line x1="{num(sep)}" y1="112" x2="{num(sep)}" y2="152" stroke="{HAIR}" stroke-width="1"/>\n')
    s.append(t("ko", "손서율", 27, sep + 26, 149, INK_DIM))

    # 역할 행
    s.append(t("mono", role, 13.5, 48, 199, INK_DIM, tracking=3.2))

    # 파형 + 플레이헤드
    s.append(f'  <line x1="48" y1="{num(wave_y)}" x2="832" y2="{num(wave_y)}" stroke="{HAIR}" stroke-width="1"/>\n')
    s.append(waveform(48, 832, wave_y, 96, seed=20260911))
    s.append(
        f'  <g class="head">\n'
        f'    <line x1="48" y1="{num(wave_y - 26)}" x2="48" y2="{num(wave_y + 26)}"'
        f' stroke="{ACCENT}" stroke-width="1" opacity="0.32"/>\n'
        f'    <circle cx="48" cy="{num(wave_y)}" r="2.6" fill="{ACCENT}"/>\n'
        f"  </g>\n"
    )
    s.append(f'  <rect x="0.5" y="0.5" width="{HERO_W - 1}" height="{HERO_H - 1}" fill="none"'
             f' stroke="{HAIR}" stroke-width="1"/>\n')
    s.append("</svg>\n")
    return "".join(s)


SEC_W, SEC_H = 880, 34


def build_section(title: str, right: list[tuple[str, str]], label: str) -> str:
    """본문 열 위에 얹는 얇은 구분선. 배경 없이 양쪽 테마에서 읽히는 중간 회색만 쓴다."""
    base = 22.0
    s = [
        f'<svg viewBox="0 0 {SEC_W} {SEC_H}" width="{SEC_W}" height="{SEC_H}"'
        f' xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">\n',
        f"  <title>{label}</title>\n",
    ]
    s.append(f'  <rect x="0" y="{num(base - 9.5)}" width="4" height="4" fill="{INK_FAINT}"/>\n')
    s.append(t("mono", title, 13.5, 14, base, INK_FAINT, tracking=3.2))
    left_end = 14 + measure("mono", title, 13.5, 3.2)

    right_w = 0.0
    if right:
        sizes = {"ko": 13.0, "mono": 12.5}
        widths = [measure(k, txt, sizes[k], 2.4 if k == "mono" else 0.0) for k, txt in right]
        right_w = sum(widths) + 6 * (len(right) - 1)
        rx = SEC_W - right_w
        for (k, txt), w in zip(right, widths):
            s.append(t(k, txt, sizes[k], rx, base, INK_FAINT,
                       tracking=2.4 if k == "mono" else 0.0))
            rx += w + 6

    rule_x0 = left_end + 18
    rule_x1 = SEC_W - right_w - (18 if right else 0)
    if rule_x1 > rule_x0 + 20:
        s.append(f'  <line x1="{num(rule_x0)}" y1="17.5" x2="{num(rule_x1)}" y2="17.5"'
                 f' stroke="{INK_FAINT}" stroke-width="1" opacity="0.34"/>\n')
    s.append("</svg>\n")
    return "".join(s)


CLOSE_W, CLOSE_H = 880, 152


def build_closing() -> str:
    l1 = "Machines hold the memory and run the repetition."
    l2 = "The judgment, the taste, the responsibility · mine."
    label = "Machines hold the memory and run the repetition. " \
            "The judgment, the taste, the responsibility · mine. Seoul."
    s = [
        f'<svg viewBox="0 0 {CLOSE_W} {CLOSE_H}" width="{CLOSE_W}" height="{CLOSE_H}"'
        f' xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">\n',
        f"  <title>{label}</title>\n",
        f'  <clipPath id="cframe"><rect x="0" y="0" width="{CLOSE_W}" height="{CLOSE_H}"/></clipPath>\n',
        f'  <rect x="0" y="0" width="{CLOSE_W}" height="{CLOSE_H}" fill="{BG}"/>\n',
        '  <g clip-path="url(#cframe)">\n',
        rings([(828, 76, 92, ""), (896, 76, 92, "")]),
        "  </g>\n",
        f'  <line x1="56" y1="0" x2="56" y2="{CLOSE_H}" stroke="{HAIR}" stroke-width="1"/>\n',
    ]
    s.append(t("italic", l1, 28, 80, 66, INK_DIM))
    s.append(t("italic", l2, 28, 80, 104, INK))
    s.append(t("mono", "SEOUL.", 12.5, 832, 132, INK_FAINT, tracking=3.0, anchor="end"))
    s.append(f'  <rect x="0.5" y="0.5" width="{CLOSE_W - 1}" height="{CLOSE_H - 1}" fill="none"'
             f' stroke="{HAIR}" stroke-width="1"/>\n')
    s.append("</svg>\n")
    return "".join(s)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "hero.svg": build_hero(),
        "selected-work.svg": build_section(
            "SELECTED WORK", [("mono", "SOUND · TEACHING · RESEARCH")],
            "Selected work · sound, teaching, research"),
        "stack.svg": build_section(
            "STACK", [("mono", "BUILD · DIRECT · MAKE")],
            "Stack · build, direct, make"),
        "closing.svg": build_closing(),
    }
    total = 0
    for name, body in files.items():
        p = OUT / name
        p.write_text(body, encoding="utf-8")
        size = p.stat().st_size
        total += size
        print(f"{name:16} {size / 1024:7.1f} KB")
    print(f"{'total':16} {total / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
