#!/usr/bin/env python3
"""
Generates card-dark.svg and card-light.svg for the profile README.

Pulls live data from the GitHub REST API and renders a hand-crafted SVG
that mirrors dimitrisofikitis.com (terminal aesthetic, JetBrains Mono stack,
exact site palette). Runs daily via .github/workflows/update.yml.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

USER = "dSofikitis"
ASSETS = Path("assets")

MSC_START = dt.date(2026, 8, 10)
MSC_LABEL = "MSc Cyber Security · NTNU, Trondheim, Norway"

PALETTES = {
    "dark": {
        "bg": "#000000",
        "text": "#e0e0e0",
        "dim": "#777777",
        "accent": "#cc0000",
        "accent_dim": "#660000",
        "cyan": "#00d4aa",
        "amber": "#ffab00",
        "blue": "#448aff",
        "panel_border": "rgba(224,224,224,0.10)",
        "panel_inner": "rgba(224,224,224,0.04)",
        "rule": "rgba(224,224,224,0.08)",
        "bar_track": "rgba(224,224,224,0.08)",
    },
    "light": {
        "bg": "#f0f0f0",
        "text": "#1a1a1a",
        "dim": "#888888",
        "accent": "#cc0000",
        "accent_dim": "#ffcccc",
        "cyan": "#009688",
        "amber": "#e65100",
        "blue": "#1565c0",
        "panel_border": "rgba(0,0,0,0.10)",
        "panel_inner": "rgba(0,0,0,0.03)",
        "rule": "rgba(0,0,0,0.08)",
        "bar_track": "rgba(0,0,0,0.08)",
    },
}

# Default radius for inner panels and outer SVG corners (was 14; user wanted
# a touch tighter, all panels now use 10).
PANEL_RX = 10

# Vertical padding inside the SVG outer bg.
# OUTER_PAD_TOP gives the bracketed label its own headroom above the gray
# panel; OUTER_PAD_BOTTOM is just visual breathing room below the panel.
OUTER_PAD_TOP = 32
OUTER_PAD_BOTTOM = 12
# Label baseline sits in the top-pad black strip, ~10px above the panel top.
LABEL_Y = OUTER_PAD_TOP - 10


def rounded_path(x: float, y: float, w: float, h: float, r: float, corners: str) -> str:
    """SVG path 'd' data for a rect with selective rounded corners.

    corners: 'top' | 'middle' | 'bottom' | 'all'
    Used to chain stacked SVGs in the README so the outer rectangles read as
    one continuous card (rounded only at the very top and very bottom).
    """
    tl = tr = bl = br = 0.0
    if corners in ("top", "all"):
        tl = tr = r
    if corners in ("bottom", "all"):
        bl = br = r
    arc = lambda rad, x2, y2: f"A {rad} {rad} 0 0 1 {x2} {y2} " if rad > 0 else ""
    return (
        f"M {x+tl} {y} "
        f"L {x+w-tr} {y} "
        + arc(tr, x + w, y + tr)
        + f"L {x+w} {y+h-br} "
        + arc(br, x + w - br, y + h)
        + f"L {x+bl} {y+h} "
        + arc(bl, x, y + h - bl)
        + f"L {x} {y+tl} "
        + arc(tl, x + tl, y)
        + "Z"
    )

LANG_COLORS = {
    "Python": "#3776AB",
    "TypeScript": "#3178C6",
    "JavaScript": "#F7DF1E",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
    "C": "#A8B9CC",
    "C++": "#00599C",
    "C#": "#512BD4",
    "Java": "#ED8B00",
    "Shell": "#89E051",
    "HTML": "#E34F26",
    "CSS": "#264DE4",
    "Dockerfile": "#2496ED",
    "Jupyter Notebook": "#DA5B0B",
    "Svelte": "#FF3E00",
}


def gh_api(path: str) -> dict | list:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect_stats() -> dict:
    user = gh_api(f"users/{USER}")
    repos: list[dict] = []
    page = 1
    while True:
        chunk = gh_api(f"users/{USER}/repos?per_page=100&page={page}&type=owner&sort=pushed")
        if not isinstance(chunk, list) or not chunk:
            break
        repos.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1

    own_repos = [r for r in repos if not r.get("fork") and not r.get("private")]
    stars = sum(r.get("stargazers_count", 0) for r in own_repos)

    # Sum byte counts per language across all non-archived repos for an accurate
    # breakdown. The /repos response only carries the primary detected language;
    # per-repo /languages returns the full byte distribution.
    lang_bytes: dict[str, int] = {}
    for r in own_repos:
        if r.get("archived"):
            continue
        try:
            data = gh_api(f"repos/{USER}/{r['name']}/languages")
        except Exception:
            continue
        if isinstance(data, dict):
            for k, v in data.items():
                lang_bytes[k] = lang_bytes.get(k, 0) + int(v)

    excluded_langs = {"HTML", "CSS"}
    filtered_langs = {k: v for k, v in lang_bytes.items() if k not in excluded_langs}

    total_lang = sum(filtered_langs.values()) or 1
    top_langs = sorted(filtered_langs.items(), key=lambda kv: -kv[1])[:8]
    top_langs = [(name, round(100 * b / total_lang)) for name, b in top_langs]
    # Drop trailing zero-percent entries
    top_langs = [(n, p) for n, p in top_langs if p > 0][:6]

    today = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    active = sum(
        1 for r in own_repos
        if r.get("pushed_at")
        and (today - dt.datetime.strptime(r["pushed_at"], "%Y-%m-%dT%H:%M:%SZ")).days <= 90
    )

    # Commits in the last 30 days. /events/public is unreliable (caps at ~300
    # events, drops some pushes, broken for unauth runs), so use the search API
    # which returns an authoritative total_count. Falls back to /events/public
    # if search fails (rate-limited or unauthenticated locally).
    commits_30d = 0
    since_iso = (today - dt.timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        result = gh_api(f"search/commits?q=author:{USER}+committer-date:>={since_iso}&per_page=1")
        if isinstance(result, dict) and "total_count" in result:
            commits_30d = int(result["total_count"])
    except Exception as e:
        print(f"warn: search/commits failed ({e}); falling back to events", file=sys.stderr)
        try:
            events = gh_api(f"users/{USER}/events/public?per_page=100")
        except Exception:
            events = []
        cutoff = today - dt.timedelta(days=30)
        if isinstance(events, list):
            for ev in events:
                if ev.get("type") != "PushEvent":
                    continue
                ts = dt.datetime.strptime(ev["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                if ts >= cutoff:
                    commits_30d += len(ev.get("payload", {}).get("commits", []))

    # "NOW building" — most recently pushed repos, excluding the profile repo
    # itself and any meta repos.
    excluded = {USER.lower(), "gh-profile"}
    pushed_titles = [
        r["name"] for r in own_repos
        if not r.get("archived") and r["name"].lower() not in excluded
    ][:3]

    return {
        "repos_total": user.get("public_repos", len(own_repos)),
        "repos_active": active,
        "stars": stars,
        "followers": user.get("followers", 0),
        "top_langs": top_langs,
        "commits_30d": commits_30d,
        "now_repos": pushed_titles,
    }


def days_to_msc() -> int:
    today = dt.date.today()
    return max(0, (MSC_START - today).days)


def render_svg(theme: str, stats: dict, corners: str = "all") -> str:
    p = PALETTES[theme]
    W, H = 880, 540
    days = days_to_msc()
    today_iso = dt.date.today().isoformat()

    name = "DIMITRIS SOFIKITIS"
    name_hex = " ".join(f"{b:02X}" for b in name.encode("ascii"))

    now_repos = stats["now_repos"] or ["aegis-rag-lab", "sentinel-stream", "zerotrust-gatekeeper"]
    now_repos = (now_repos + ["—"] * 3)[:3]

    top_langs = stats["top_langs"] or [("Python", 40), ("TypeScript", 22), ("Go", 14), ("Rust", 10), ("C++", 8), ("Shell", 6)]

    font_stack = "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace"

    css = f"""
    .bg     {{ fill: {p['bg']}; }}
    .text   {{ fill: {p['text']}; }}
    .dim    {{ fill: {p['dim']}; }}
    .accent {{ fill: {p['accent']}; }}
    .cyan   {{ fill: {p['cyan']}; }}
    .amber  {{ fill: {p['amber']}; }}
    .blue   {{ fill: {p['blue']}; }}
    .panel  {{ fill: {p['panel_inner']}; stroke: {p['panel_border']}; stroke-width: 1; }}
    .rule   {{ stroke: {p['rule']}; stroke-width: 1; }}
    .h1     {{ font-size: 28px; font-weight: 700; letter-spacing: 0.15em; }}
    .role   {{ font-size: 11px; letter-spacing: 0.18em; }}
    .mono   {{ font-size: 12px; }}
    .small  {{ font-size: 10px; letter-spacing: 0.06em; }}
    .label  {{ font-size: 9px; letter-spacing: 0.18em; font-weight: 700;
               stroke: {p['bg']}; stroke-width: 6px; stroke-linejoin: round;
               paint-order: stroke fill; }}
    .stat   {{ font-size: 22px; font-weight: 700; }}
    .stat-l {{ font-size: 9px; letter-spacing: 0.12em; }}

    .blink  {{ animation: blink 1.05s step-end infinite; }}
    @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}

    .fade-1 {{ opacity: 0; animation: fadein .55s ease-out .00s forwards; }}
    .fade-2 {{ opacity: 0; animation: fadein .55s ease-out .15s forwards; }}
    .fade-3 {{ opacity: 0; animation: fadein .55s ease-out .30s forwards; }}
    .fade-4 {{ opacity: 0; animation: fadein .55s ease-out .45s forwards; }}
    .fade-5 {{ opacity: 0; animation: fadein .55s ease-out .60s forwards; }}
    .fade-6 {{ opacity: 0; animation: fadein .55s ease-out .75s forwards; }}
    .fade-7 {{ opacity: 0; animation: fadein .55s ease-out .90s forwards; }}
    .fade-8 {{ opacity: 0; animation: fadein .55s ease-out 1.05s forwards; }}
    @keyframes fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

    .reveal {{ clip-path: inset(0 100% 0 0); animation: reveal 1.4s cubic-bezier(.23,1,.32,1) .9s forwards; }}
    @keyframes reveal {{ to {{ clip-path: inset(0 0 0 0); }} }}
    """

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{font_stack}" role="img" aria-label="Dimitris Sofikitis profile card">'
    )
    parts.append(f"<defs><style>{css}</style></defs>")
    parts.append(f'<path class="bg" d="{rounded_path(0, 0, W, H, PANEL_RX, corners)}" />')

    # === Hero block ===========================================================
    parts.append(
        f'<g class="fade-1">'
        f'<text x="32" y="58" class="h1 text">DIMITRIS SOFIKITIS</text>'
        f'<text x="34" y="80" class="role dim">AI/ML SOFTWARE ENGINEER · ATHENS, GR</text>'
        f"</g>"
    )
    parts.append(
        f'<g class="fade-2">'
        f'<text x="32" y="112" class="mono">'
        f'<tspan class="dim">&gt; </tspan>'
        f'<tspan class="text">Engineering Trust in a world of Chaos</tspan>'
        f'<tspan class="accent blink">█</tspan>'
        f"</text></g>"
    )

    # === Memory-dump strip ====================================================
    parts.append(
        f'<g class="fade-3">'
        f'<text x="32" y="146" class="mono dim">0x0000</text>'
        f'<text x="92" y="146" class="mono text" letter-spacing="1">{name_hex}</text>'
        f'<text x="{W-32}" y="146" text-anchor="end" class="mono dim">{name}</text>'
        f"</g>"
    )
    parts.append(f'<line x1="32" y1="160" x2="{W-32}" y2="160" class="rule" />')

    # === Boot messages ========================================================
    boot_lines = [
        ("init engineering trust",            "[ OK ]"),
        ("securing agentic systems",          "[ OK ]"),
        ("breaking what shouldn't be trusted", "[ OK ]"),
    ]
    y = 184
    for i, (msg, status) in enumerate(boot_lines):
        parts.append(
            f'<g class="fade-{4+i}">'
            f'<text x="32" y="{y}" class="mono">'
            f'<tspan class="dim">[BOOT] </tspan>'
            f'<tspan class="text">{msg}</tspan>'
            f"</text>"
            f'<text x="{W-32}" y="{y}" text-anchor="end" class="mono accent">{status}</text>'
            f"</g>"
        )
        y += 22

    # === Bracketed stat panels ================================================
    panel_y = 268
    panel_h = 110
    gap = 16
    panel_w = (W - 64 - 2 * gap) // 3
    panels = [
        ("NOW",   [now_repos[0], now_repos[1], now_repos[2]], None, "cyan"),
        ("STATS", [
            ("commits/30d", str(stats["commits_30d"])),
            ("repos·active", str(stats["repos_active"])),
            ("stars",        str(stats["stars"])),
        ], "kv", "amber"),
        ("NEXT",  [MSC_LABEL.split(" · ")[0], MSC_LABEL.split(" · ")[1], f"T-{days} days"], None, "accent"),
    ]
    for idx, (label, content, kind, color) in enumerate(panels):
        x = 32 + idx * (panel_w + gap)
        # Panel rect
        parts.append(
            f'<g class="fade-{6+min(idx,2)}">'
            f'<rect x="{x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="10" class="panel" />'
        )
        # Bracketed label sits on top of the panel border. The .label CSS class
        # uses paint-order:stroke fill with a bg-colored stroke as a halo, which
        # masks the border behind the text without needing a separate slab rect.
        label_text = f"[ {label} ]"
        parts.append(
            f'<text x="{x+18}" y="{panel_y+3}" class="label {color}">{label_text}</text>'
        )
        # Body
        if kind == "kv":
            for i, (k, v) in enumerate(content):
                row_y = panel_y + 32 + i * 24
                parts.append(
                    f'<text x="{x+16}" y="{row_y}" class="small dim">{k}</text>'
                    f'<text x="{x+panel_w-16}" y="{row_y}" text-anchor="end" class="stat text">{v}</text>'
                )
        else:
            for i, line in enumerate(content):
                row_y = panel_y + 34 + i * 22
                glyph = "·"
                parts.append(
                    f'<text x="{x+16}" y="{row_y}" class="mono dim">{glyph}</text>'
                    f'<text x="{x+30}" y="{row_y}" class="mono text">{line}</text>'
                )
        parts.append("</g>")

    # === Languages bar ========================================================
    lang_y = 408
    parts.append(
        f'<g class="fade-7">'
        f'<text x="32" y="{lang_y}" class="mono">'
        f'<tspan class="dim">&gt; </tspan>'
        f'<tspan class="text">languages --top 6</tspan>'
        f"</text></g>"
    )
    bar_x = 32
    bar_w = W - 64
    bar_h = 8
    bar_top = lang_y + 16
    total_pct = sum(pct for _, pct in top_langs) or 1

    # Track + segments wrapped together so the whole bar reveals left-to-right
    # via clip-path (avoids transform-origin pitfalls in scaled SVG).
    parts.append(f'<g class="fade-8 reveal">')
    parts.append(
        f'<rect x="{bar_x}" y="{bar_top}" width="{bar_w}" height="{bar_h}" rx="2" fill="{p["bar_track"]}" />'
    )
    cumulative = 0
    for name_l, pct in top_langs:
        seg_w = int(bar_w * pct / total_pct)
        color = LANG_COLORS.get(name_l, p["accent"])
        parts.append(
            f'<rect x="{bar_x + cumulative}" y="{bar_top}" width="{seg_w}" height="{bar_h}" fill="{color}" />'
        )
        cumulative += seg_w
    parts.append("</g>")

    # Legend — 3-column × 2-row grid of fixed-width cells.
    legend_y = bar_top + 30
    cols = 3
    row_h = 20
    cell_w = bar_w // cols
    for i, (name_l, pct) in enumerate(top_langs):
        color = LANG_COLORS.get(name_l, p["accent"])
        col = i % cols
        row = i // cols
        cx = bar_x + col * cell_w
        cy = legend_y + row * row_h
        parts.append(
            f'<g class="fade-8">'
            f'<circle cx="{cx + 4}" cy="{cy - 3}" r="3" fill="{color}" />'
            f'<text x="{cx + 14}" y="{cy}" class="small text">{name_l}</text>'
            f'<text x="{cx + cell_w - 4}" y="{cy}" text-anchor="end" class="small dim">{pct}%</text>'
            f'</g>'
        )

    # === Footer ==============================================================
    parts.append(
        f'<g class="fade-8">'
        f'<text x="32" y="{H-20}" class="small dim">&gt; last_sync: {today_iso}</text>'
        f'<text x="{W-32}" y="{H-20}" text-anchor="end" class="small dim">'
        f'dimitrisofikitis.com'
        f"</text>"
        f"</g>"
    )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


CONTACTS = [
    ("site",     "dimitrisofikitis.com"),
    ("linkedin", "/in/dimitrisofikitis"),
    ("email",    "d.sofikitis@icloud.com"),
    ("resume",   "dimitrisofikitis.com/resume"),
    ("apps",     "apps.dimitrisofikitis.com"),
]

# Lines pre-wrapped to comfortably fit at ~13px JetBrains Mono in an 816px column.
# Color hint maps to a CSS class: cyan | amber | accent | text.
WHOAMI = [
    ("mantra", "cyan", [
        "I build things that need to be trusted —",
        "and break things that shouldn't be.",
    ]),
    ("by_day", "amber", [
        "engineer trust into AI systems —",
        "prompt-injection defense, hallucination mitigation,",
        "evaluation frameworks for agentic AI.",
    ]),
    ("by_night", "accent", [
        "reverse-engineering something I shouldn't be,",
        "reading threat reports, or over-engineering a personal project.",
    ]),
    ("based_in", "blue", [
        "Athens, GR — fueled by curiosity, passion,",
        "and a mild obsession with making machines behave.",
    ]),
]


def render_whoami_svg(theme: str, corners: str = "all") -> str:
    """Long-form 'about me' rendered as a structured terminal output."""
    p = PALETTES[theme]
    W, H = 880, 480  # +20 vs prev to fit the label-above-panel headroom
    font_stack = "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace"

    css = f"""
    .bg     {{ fill: {p['bg']}; }}
    .text   {{ fill: {p['text']}; }}
    .dim    {{ fill: {p['dim']}; }}
    .accent {{ fill: {p['accent']}; }}
    .cyan   {{ fill: {p['cyan']}; }}
    .amber  {{ fill: {p['amber']}; }}
    .blue   {{ fill: {p['blue']}; }}
    .panel  {{ fill: {p['panel_inner']}; stroke: {p['panel_border']}; stroke-width: 1; }}
    .rule   {{ stroke: {p['rule']}; stroke-width: 1; }}
    .label  {{ font-size: 9px; letter-spacing: 0.18em; font-weight: 700;
               stroke: {p['bg']}; stroke-width: 6px; stroke-linejoin: round;
               paint-order: stroke fill; }}
    .mono   {{ font-size: 13px; }}
    .body   {{ font-size: 13px; }}
    .key    {{ font-size: 13px; letter-spacing: 0.10em; font-weight: 700; }}
    .small  {{ font-size: 10px; letter-spacing: 0.06em; }}

    .blink  {{ animation: blink 1.05s step-end infinite; }}
    @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}

    .fade-1 {{ opacity: 0; animation: fadein .55s ease-out .00s forwards; }}
    .fade-2 {{ opacity: 0; animation: fadein .55s ease-out .15s forwards; }}
    .fade-3 {{ opacity: 0; animation: fadein .55s ease-out .30s forwards; }}
    .fade-4 {{ opacity: 0; animation: fadein .55s ease-out .45s forwards; }}
    .fade-5 {{ opacity: 0; animation: fadein .55s ease-out .60s forwards; }}
    .fade-6 {{ opacity: 0; animation: fadein .55s ease-out .75s forwards; }}
    .fade-7 {{ opacity: 0; animation: fadein .55s ease-out .90s forwards; }}
    @keyframes fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    """

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{font_stack}" role="img" aria-label="Dimitris Sofikitis — whoami">'
    )
    parts.append(f"<defs><style>{css}</style></defs>")
    parts.append(f'<path class="bg" d="{rounded_path(0, 0, W, H, PANEL_RX, corners)}" />')

    # Outer panel sits below OUTER_PAD_TOP black bg space (where the label
    # lives). Inner rx stays fully rounded regardless of position.
    panel_y = OUTER_PAD_TOP
    panel_h = H - OUTER_PAD_TOP - OUTER_PAD_BOTTOM
    parts.append(
        f'<path d="{rounded_path(12, panel_y, W-24, panel_h, PANEL_RX, "all")}" class="panel" />'
    )

    # Bracketed label sits ABOVE the panel in the top black bg.
    parts.append(
        f'<text x="30" y="{LABEL_Y}" class="label accent">[ whoami ]</text>'
    )

    # Prompt
    parts.append(
        f'<g class="fade-1">'
        f'<text x="32" y="64" class="mono">'
        f'<tspan class="dim">$ </tspan>'
        f'<tspan class="text">whoami --verbose</tspan>'
        f'<tspan class="accent blink">█</tspan>'
        f'</text>'
        f'</g>'
    )

    # Separator
    parts.append(f'<line x1="32" y1="80" x2="{W-32}" y2="80" class="rule" />')

    # Sections
    y = 108
    section_gap = 20  # between sections (in addition to row spacing)
    line_h = 22
    for i, (key, color, lines) in enumerate(WHOAMI):
        # Header
        parts.append(
            f'<g class="fade-{2+i}">'
            f'<text x="32" y="{y}" class="mono">'
            f'<tspan class="dim">&gt; </tspan>'
            f'<tspan class="key {color}">{key}</tspan>'
            f'</text>'
        )
        # Body lines, indented
        for j, ln in enumerate(lines):
            row_y = y + (j + 1) * line_h
            # Escape XML special chars
            safe = ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(
                f'<text x="56" y="{row_y}" class="body text">{safe}</text>'
            )
        parts.append("</g>")
        y += line_h * (len(lines) + 1) + section_gap

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_elsewhere_svg(theme: str, corners: str = "all") -> str:
    """Compact bracketed panel listing contact endpoints, same DNA as the main card."""
    p = PALETTES[theme]
    W, H = 880, 270  # +20 for label-above-panel headroom
    today_iso = dt.date.today().isoformat()
    font_stack = "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace"

    css = f"""
    .bg     {{ fill: {p['bg']}; }}
    .text   {{ fill: {p['text']}; }}
    .dim    {{ fill: {p['dim']}; }}
    .accent {{ fill: {p['accent']}; }}
    .cyan   {{ fill: {p['cyan']}; }}
    .amber  {{ fill: {p['amber']}; }}
    .panel  {{ fill: {p['panel_inner']}; stroke: {p['panel_border']}; stroke-width: 1; }}
    .rule   {{ stroke: {p['rule']}; stroke-width: 1; }}
    .label  {{ font-size: 9px; letter-spacing: 0.18em; font-weight: 700;
               stroke: {p['bg']}; stroke-width: 6px; stroke-linejoin: round;
               paint-order: stroke fill; }}
    .mono   {{ font-size: 13px; }}
    .small  {{ font-size: 10px; letter-spacing: 0.06em; }}
    .key    {{ font-size: 13px; letter-spacing: 0.10em; font-weight: 700; }}

    .blink  {{ animation: blink 1.05s step-end infinite; }}
    @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}

    .fade-1 {{ opacity: 0; animation: fadein .55s ease-out .00s forwards; }}
    .fade-2 {{ opacity: 0; animation: fadein .55s ease-out .15s forwards; }}
    .fade-3 {{ opacity: 0; animation: fadein .55s ease-out .30s forwards; }}
    .fade-4 {{ opacity: 0; animation: fadein .55s ease-out .45s forwards; }}
    .fade-5 {{ opacity: 0; animation: fadein .55s ease-out .60s forwards; }}
    .fade-6 {{ opacity: 0; animation: fadein .55s ease-out .75s forwards; }}
    @keyframes fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    """

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{font_stack}" role="img" aria-label="Dimitris Sofikitis contact endpoints">'
    )
    parts.append(f"<defs><style>{css}</style></defs>")
    parts.append(f'<path class="bg" d="{rounded_path(0, 0, W, H, PANEL_RX, corners)}" />')

    # Outer panel below the label headroom; inner rx always full.
    panel_y = OUTER_PAD_TOP
    panel_h = H - OUTER_PAD_TOP - OUTER_PAD_BOTTOM
    parts.append(
        f'<path d="{rounded_path(12, panel_y, W-24, panel_h, PANEL_RX, "all")}" class="panel" />'
    )

    # Bracketed label sits ABOVE the panel in the top black bg.
    parts.append(
        f'<text x="30" y="{LABEL_Y}" class="label cyan">[ elsewhere ]</text>'
    )

    # Prompt line
    parts.append(
        f'<g class="fade-1">'
        f'<text x="32" y="64" class="mono">'
        f'<tspan class="dim">$ </tspan>'
        f'<tspan class="text">cat ~/contacts++</tspan>'
        f'<tspan class="accent blink">█</tspan>'
        f'</text>'
        f'</g>'
    )

    # Separator
    parts.append(f'<line x1="32" y1="80" x2="{W-32}" y2="80" class="rule" />')

    # Rows
    key_col_x = 122
    val_col_x = 272
    y0 = 108
    row_h = 24
    for i, (key, val) in enumerate(CONTACTS):
        y = y0 + i * row_h
        parts.append(
            f'<g class="fade-{2+i}">'
            f'<text x="32" y="{y}" class="mono dim">0x0{i}</text>'
            f'<text x="{key_col_x}" y="{y}" class="key amber">{key}</text>'
            f'<text x="{key_col_x + 80}" y="{y}" class="mono dim">▸</text>'
            f'<text x="{val_col_x}" y="{y}" class="mono text">{val}</text>'
            f'</g>'
        )

    # EOF marker
    eof_y = y0 + len(CONTACTS) * row_h + 18
    parts.append(
        f'<g class="fade-6">'
        f'<text x="32" y="{eof_y}" class="small dim">EOF · last_sync: {today_iso}</text>'
        f'</g>'
    )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


STACK_ROWS: list[tuple[str, str, list[str]]] = [
    # (label, accent_class, skillicons keys)
    ("langs",        "amber", ["python", "ts", "js", "go", "rust", "c", "cpp", "cs", "java", "bash"]),
    ("web · api",    "cyan",  ["fastapi", "flask", "nodejs", "react", "nextjs", "svelte", "tailwind", "html", "css", "postman"]),
    ("data · cloud", "blue",  ["postgres", "mysql", "redis", "mongodb", "aws", "azure", "gcp", "docker", "kubernetes", "terraform"]),
]


def _fetch_skillicons_row(icons: list[str]) -> tuple[str, float, float] | None:
    """Fetch a row of skillicons.dev icons. Returns (inner_svg, width, height)."""
    url = f"https://skillicons.dev/icons?i={','.join(icons)}&perline={len(icons)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-readme"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
    except Exception as e:
        print(f"warn: skillicons fetch failed for {icons!r} ({e})", file=sys.stderr)
        return None
    m = re.search(r"<svg([^>]*)>(.*)</svg>", raw, re.DOTALL)
    if not m:
        return None
    attrs, inner = m.group(1), m.group(2)
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', attrs)
    if vb:
        nums = vb.group(1).split()
        return inner, float(nums[2]), float(nums[3])
    wm = re.search(r'width\s*=\s*"([^"]+)"', attrs)
    hm = re.search(r'height\s*=\s*"([^"]+)"', attrs)
    return inner, float(wm.group(1)) if wm else 588.0, float(hm.group(1)) if hm else 48.0


def render_stack_svg(theme: str, corners: str = "all") -> str | None:
    """Composite SVG: bracketed [stack] panel framing the three skillicons rows."""
    p = PALETTES[theme]
    today_iso = dt.date.today().isoformat()
    font_stack = "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace"

    rows: list[tuple[str, str, str, float, float]] = []
    for label, color, icons in STACK_ROWS:
        fetched = _fetch_skillicons_row(icons)
        if fetched is None:
            return None  # any failure → keep prior file
        inner, w, h = fetched
        rows.append((label, color, inner, w, h))

    W = 880
    usable_w = W - 64  # 32px padding each side
    # All rows share the same width (10 icons each); scale uniformly.
    src_w = rows[0][3]
    src_h = rows[0][4]
    scale = usable_w / src_w
    icon_block_h = src_h * scale

    # Vertical layout: per row, 22px header + 8px gap + icon_block_h + 28px gap.
    header_h = 22
    after_header = 8
    after_icons = 28

    # Top: OUTER_PAD_TOP black bg (label) + 32 to prompt + 16 rule + 22 first content
    content_start = OUTER_PAD_TOP + 32 + 16 + 22
    rows_h = sum(header_h + after_header + icon_block_h + after_icons for _ in rows)
    rows_h -= after_icons  # no trailing gap after last row
    bottom_pad = 36
    H = int(content_start + rows_h + bottom_pad + OUTER_PAD_BOTTOM)

    css = f"""
    .bg     {{ fill: {p['bg']}; }}
    .text   {{ fill: {p['text']}; }}
    .dim    {{ fill: {p['dim']}; }}
    .accent {{ fill: {p['accent']}; }}
    .cyan   {{ fill: {p['cyan']}; }}
    .amber  {{ fill: {p['amber']}; }}
    .blue   {{ fill: {p['blue']}; }}
    .panel  {{ fill: {p['panel_inner']}; stroke: {p['panel_border']}; stroke-width: 1; }}
    .rule   {{ stroke: {p['rule']}; stroke-width: 1; }}
    .label  {{ font-size: 9px; letter-spacing: 0.18em; font-weight: 700;
               stroke: {p['bg']}; stroke-width: 6px; stroke-linejoin: round;
               paint-order: stroke fill; }}
    .mono   {{ font-size: 13px; }}
    .small  {{ font-size: 10px; letter-spacing: 0.06em; }}
    .key    {{ font-size: 13px; letter-spacing: 0.10em; font-weight: 700; }}

    .blink  {{ animation: blink 1.05s step-end infinite; }}
    @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}

    .fade-1 {{ opacity: 0; animation: fadein .55s ease-out .00s forwards; }}
    .fade-2 {{ opacity: 0; animation: fadein .55s ease-out .20s forwards; }}
    .fade-3 {{ opacity: 0; animation: fadein .55s ease-out .40s forwards; }}
    .fade-4 {{ opacity: 0; animation: fadein .55s ease-out .60s forwards; }}
    @keyframes fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    """

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{font_stack}" role="img" aria-label="Tech stack">'
    )
    parts.append(f"<defs><style>{css}</style></defs>")
    parts.append(f'<path class="bg" d="{rounded_path(0, 0, W, H, PANEL_RX, corners)}" />')
    panel_y = OUTER_PAD_TOP
    panel_h = H - OUTER_PAD_TOP - OUTER_PAD_BOTTOM
    parts.append(
        f'<path d="{rounded_path(12, panel_y, W-24, panel_h, PANEL_RX, "all")}" class="panel" />'
    )
    parts.append(f'<text x="30" y="{LABEL_Y}" class="label amber">[ stack ]</text>')

    parts.append(
        f'<g class="fade-1">'
        f'<text x="32" y="64" class="mono">'
        f'<tspan class="dim">$ </tspan>'
        f'<tspan class="text">ls /usr/local/bin</tspan>'
        f'<tspan class="accent blink">█</tspan>'
        f'</text>'
        f'</g>'
    )
    parts.append(f'<line x1="32" y1="80" x2="{W-32}" y2="80" class="rule" />')

    y = content_start
    for i, (label, color, inner, w, h) in enumerate(rows):
        parts.append(
            f'<g class="fade-{2+i}">'
            f'<text x="32" y="{y}" class="mono">'
            f'<tspan class="dim">&gt; </tspan>'
            f'<tspan class="key {color}">{label}</tspan>'
            f'</text>'
        )
        # Embed icon row, scaled and positioned
        icon_y = y + after_header
        # Wrap inner in a group with translate + scale so the row fits our usable_w
        # while preserving its native coordinates.
        parts.append(
            f'<g transform="translate(32 {icon_y}) scale({scale:.4f})">{inner}</g>'
        )
        parts.append("</g>")
        y += header_h + after_header + icon_block_h + after_icons

    parts.append(
        f'<g class="fade-4">'
        f'<text x="32" y="{H-22}" class="small dim">EOF · last_sync: {today_iso}</text>'
        f'</g>'
    )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def fetch_activity_svg(theme: str, corners: str = "all") -> str | None:
    """Fetch the third-party activity graph and wrap it with rounded corners.

    Returns the wrapped SVG markup, or None if the fetch failed (caller should
    keep the previously committed file in that case).
    Side effect: this is the ONLY external request made on README view —
    pre-rendering it locally means visitors don't ping vercel on every load.
    """
    p = PALETTES[theme]
    bg    = p["bg"].lstrip("#")
    text  = p["text"].lstrip("#")
    line  = p["accent"].lstrip("#")
    point = p["amber"].lstrip("#")

    url = (
        "https://github-readme-activity-graph.vercel.app/graph"
        f"?username={USER}"
        f"&bg_color={bg}"
        f"&color={text}"
        f"&line={line}"
        f"&point={point}"
        "&area=true"
        "&hide_border=true"
        "&custom_title=contribution+signal"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"{USER}-readme"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
    except Exception as e:
        print(f"warn: activity graph fetch failed for {theme} ({e})", file=sys.stderr)
        return None

    m = re.search(r"<svg([^>]*)>(.*)</svg>", raw, re.DOTALL)
    if not m:
        print(f"warn: activity graph SVG didn't parse for {theme}", file=sys.stderr)
        return None

    attrs, inner = m.group(1), m.group(2)

    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', attrs)
    if vb:
        nums = vb.group(1).split()
        w, h = float(nums[2]), float(nums[3])
    else:
        wm = re.search(r'width\s*=\s*"([^"]+)"', attrs)
        hm = re.search(r'height\s*=\s*"([^"]+)"', attrs)
        w = float(wm.group(1)) if wm else 800.0
        h = float(hm.group(1)) if hm else 240.0

    # Use the third-party's native viewBox (1200×420). The widget's card_bg
    # rect uses width="100%" / height="100%", which only fills correctly when
    # the viewBox matches the source. Wrapping in a scale transform broke this
    # (the bg got scaled while "100%" still meant the outer wrapper). Activity
    # is standalone in the README, so width-mismatch with the chain doesn't
    # matter — both render at width="100%" of the container.
    # Scale the rx so the rendered corner radius visually matches the chain.
    rx = PANEL_RX * (w / 880)
    clip_d = rounded_path(0, 0, w, h, rx, corners)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}">'
        f'<defs><clipPath id="rounded-frame">'
        f'<path d="{clip_d}" />'
        f'</clipPath></defs>'
        f'<g clip-path="url(#rounded-frame)">{inner}</g>'
        f'</svg>\n'
    )


def combine_svgs(srcs: list[Path], dst: Path) -> bool:
    """Stack multiple SVG files vertically into a single combined SVG.

    Why: GitHub README markdown can't eliminate the line-height gap between
    adjacent <picture><img> blocks (inline styles get sanitized away). Putting
    everything into one SVG means one <img> in the README — zero gaps possible.

    How: each source becomes a <g transform="translate(0 Y)">. IDs are
    suffixed per section so duplicate ids (e.g. clipPath#rounded-frame in the
    activity wrapper) don't collide once everything shares one document.
    """
    sections: list[tuple[str, float, float]] = []  # (inner, w, y_offset)
    cumulative_y = 0.0
    max_w = 0.0
    missing = [s for s in srcs if not s.exists()]
    if missing:
        print(f"warn: combine skipped, missing {missing}", file=sys.stderr)
        return False

    for i, src in enumerate(srcs):
        content = src.read_text(encoding="utf-8")
        m_vb = re.search(r'<svg[^>]*viewBox\s*=\s*"([^"]+)"', content)
        if not m_vb:
            print(f"warn: no viewBox on {src}; skipping combine", file=sys.stderr)
            return False
        nums = m_vb.group(1).split()
        w, h = float(nums[2]), float(nums[3])
        max_w = max(max_w, w)

        m_inner = re.search(r"<svg[^>]*>(.*)</svg>", content, re.DOTALL)
        if not m_inner:
            return False
        inner = m_inner.group(1)

        suffix = f"-s{i}"
        # Namespace IDs so clipPath#rounded-frame, etc., don't collide across sections
        inner = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{m.group(1)}{suffix}"', inner)
        inner = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{m.group(1)}{suffix})", inner)
        inner = re.sub(
            r'\b(xlink:)?href="#([^"]+)"',
            lambda m: f'{m.group(1) or ""}href="#{m.group(2)}{suffix}"',
            inner,
        )

        sections.append((inner, h, cumulative_y))
        cumulative_y += h

    # font-family must live on the combined root: each component's font-family
    # was set as an attribute on its <svg>, which we strip when extracting
    # inner content. Without it, browsers fall back to default serif (Times
    # New Roman) for the chain.
    H = cumulative_y
    font_stack = "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {max_w:g} {H:g}" width="{max_w:g}" height="{H:g}" '
        f'font-family="{font_stack}">'
    ]
    for inner, _h, y in sections:
        parts.append(f'<g transform="translate(0 {y:g})">{inner}</g>')
    parts.append("</svg>")
    dst.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return True


def main() -> int:
    try:
        stats = collect_stats()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"warn: GitHub API failed ({e}); falling back to defaults", file=sys.stderr)
        stats = {
            "repos_total": 0, "repos_active": 0, "stars": 0, "followers": 0,
            "top_langs": [], "commits_30d": 0,
            "now_repos": ["aegis-rag-lab", "sentinel-stream", "zerotrust-gatekeeper"],
        }

    ASSETS.mkdir(exist_ok=True)
    # Positional corners: stacked top→bottom in the README, so only the very
    # top SVG gets rounded top corners and only the very bottom SVG gets
    # rounded bottom corners. Middles are flush rectangles → reads as one
    # continuous card.
    # Three independently rounded blocks in the README:
    #   1. main card (standalone, fully rounded)
    #   2. chain → whoami → stack → elsewhere (continuous tower)
    #   3. activity graph (standalone after the contact pills, fully rounded)
    POSITIONS = {
        "card":      "all",
        "whoami":    "top",
        "stack":     "middle",
        "elsewhere": "bottom",
        "activity":  "all",
    }

    for theme in ("dark", "light"):
        card = ASSETS / f"card-{theme}.svg"
        card.write_text(render_svg(theme, stats, corners=POSITIONS["card"]), encoding="utf-8")
        print(f"wrote {card} ({card.stat().st_size:,} bytes)")

        whoami = ASSETS / f"whoami-{theme}.svg"
        whoami.write_text(render_whoami_svg(theme, corners=POSITIONS["whoami"]), encoding="utf-8")
        print(f"wrote {whoami} ({whoami.stat().st_size:,} bytes)")

        stack_path = ASSETS / f"stack-{theme}.svg"
        stack = render_stack_svg(theme, corners=POSITIONS["stack"])
        if stack is not None:
            stack_path.write_text(stack, encoding="utf-8")
            print(f"wrote {stack_path} ({stack_path.stat().st_size:,} bytes)")
        elif stack_path.exists():
            print(f"kept existing {stack_path}")
        else:
            print(f"skipped {stack_path} (fetch failed, no prior file)")

        activity_path = ASSETS / f"activity-{theme}.svg"
        activity = fetch_activity_svg(theme, corners=POSITIONS["activity"])
        if activity is not None:
            activity_path.write_text(activity, encoding="utf-8")
            print(f"wrote {activity_path} ({activity_path.stat().st_size:,} bytes)")
        elif activity_path.exists():
            print(f"kept existing {activity_path}")
        else:
            print(f"skipped {activity_path} (fetch failed, no prior file)")

        elsewhere = ASSETS / f"elsewhere-{theme}.svg"
        elsewhere.write_text(render_elsewhere_svg(theme, corners=POSITIONS["elsewhere"]), encoding="utf-8")
        print(f"wrote {elsewhere} ({elsewhere.stat().st_size:,} bytes)")

        # Fuse the three chain cards (whoami, stack, elsewhere) into one SVG.
        # README references just this single file → zero margin/baseline gap.
        # Activity stays standalone so it can sit below the contact pills.
        chain_path = ASSETS / f"chain-{theme}.svg"
        chain_srcs = [
            ASSETS / f"whoami-{theme}.svg",
            ASSETS / f"stack-{theme}.svg",
            ASSETS / f"elsewhere-{theme}.svg",
        ]
        if combine_svgs(chain_srcs, chain_path):
            print(f"wrote {chain_path} ({chain_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
