#!/usr/bin/env python3
"""A year of contributions as a heart-monitor strip: one beat per week, R-peak height = weekly contributions.
Below the monitor a cat paw (pawtop-*.png) presses ENTER (key-*.png) on every pulse, at the bpm rate.

usage: GITHUB_TOKEN=... python3 vitals.py OUT_DIR [LOGIN]
writes OUT_DIR/vitals-dark.svg (monitor) and OUT_DIR/vitals-light.svg (ekg paper)
"""
import base64
import datetime as dt
import json
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date contributionCount } } } } } }"""
QUOTE = ['"В этом мире у кого-то лапки, а у кого-то клешни,', "но это не важно когда нажимаешь ENTER",
         'главно что у тебя в голове" - lucipure']

W, H, DESK = 1000, 480, 306
X0, X1, BASE, AMP = 30, 970, 165, 110
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
THEMES = {
    "dark": dict(bg="#070708", desk="#0c0c0f", grid="#ff1a3c", g1=.06, g2=.15, trace="#ff1a3c", old=.28,
                 ink="#efe6da", red="#ff1a3c", head="#ffffff", legend="#efe6da", shade="#000"),
    "light": dict(bg="#fbf2ef", desk="#ece6de", grid="#e0485f", g1=.14, g2=.34, trace="#141414", old=.22,
                  ink="#141414", red="#c8001a", head="#c8001a", legend="#141414", shade="#5a3a3a"),
}
# one heartbeat on u in [0, 1]: (u, deflection as a fraction of the R peak, negative is up)
BEAT = [(0, 0), (.16, 0), (.19, -.05), (.22, -.09), (.25, -.05), (.28, 0), (.4, 0), (.43, .12), (.47, -1),
        (.51, .3), (.55, 0), (.66, 0), (.7, -.07), (.75, -.17), (.8, -.07), (.84, 0), (1, 0)]


def css(period):
    return f"""text{{font-family:{MONO}}}
.p{{animation:p {period:.3f}s ease-out infinite}}@keyframes p{{0%{{opacity:1}}60%{{opacity:.15}}}}
.tap{{animation:tap {period:.3f}s ease-in-out infinite}}
@keyframes tap{{0%,14%{{transform:translate(0,0)}}42%,86%{{transform:translate(10px,-4px)}}100%{{transform:translate(0,0)}}}}
.key{{transform-box:fill-box;transform-origin:50% 50%;animation:key {period:.3f}s ease-in-out infinite}}
@keyframes key{{0%,14%{{transform:translateY(2px) scale(.965)}}40%,88%{{transform:none}}100%{{transform:translateY(2px) scale(.965)}}}}
.led{{animation:led {period:.3f}s ease-out infinite}}@keyframes led{{0%,12%{{opacity:1}}50%,100%{{opacity:.22}}}}
.bpm{{transform-box:fill-box;transform-origin:50% 100%;animation:bpm {period:.3f}s ease-out infinite}}
@keyframes bpm{{0%{{transform:scale(1.12)}}30%,100%{{transform:none}}}}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "vitals"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        sys.exit(f"graphql: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]
    return cal["totalContributions"], weeks


def stats(total, weeks):
    days = [c for w in weeks for _, c in w]
    if days and days[-1] == 0:  # today not started yet: the streak is still alive
        days = days[:-1]
    cur = 0
    for c in reversed(days):
        if not c:
            break
        cur += 1
    best = run = 0
    for c in days:
        run = run + 1 if c else 0
        best = max(best, run)
    sums = [sum(c for _, c in w) for w in weeks]
    peak = max(range(len(sums)), key=sums.__getitem__)
    return dict(bpm=round(total / max(len(weeks), 1)), total=total, sums=sums, peak=sums[peak],
                peak_date=dt.date.fromisoformat(weeks[peak][0][0]), cur=cur, best=best,
                alive=sum([c for w in weeks for _, c in w][-7:]) > 0)


def trace(sums):
    top = max(sums) or 1
    cell = (X1 - X0) / len(sums)
    pts = []
    for i, s in enumerate(sums):
        amp = max(10, AMP * math.sqrt(s / top)) if s else 0
        for u, v in BEAT[(1 if i else 0):]:
            pts.append((X0 + (i + u) * cell, BASE + v * amp))
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def b64(name):
    with open(os.path.join(HERE, name), "rb") as f:
        return base64.b64encode(f.read()).decode()


def svg(st, weeks, theme, login):
    t = THEMES[theme]
    d = trace(st["sums"])
    cell = (X1 - X0) / len(weeks)
    grid = "".join(f"M{x},0V{DESK}" for x in range(0, W + 1, 10)) + "".join(f"M0,{y}H{W}" for y in range(0, DESK, 10))
    major = "".join(f"M{x},0V{DESK}" for x in range(0, W + 1, 50)) + "".join(f"M0,{y}H{W}" for y in range(0, DESK, 50))
    ticks = []
    for i, w in enumerate(weeks):
        day = dt.date.fromisoformat(w[0][0])
        if day.day <= 7:
            x = X0 + (i + .5) * cell
            ticks.append(f'<path d="M{x:.1f},{BASE + 48}v6" stroke="{t["ink"]}" stroke-opacity=".35"/>'
                         f'<text x="{x:.1f}" y="{BASE + 70}" text-anchor="middle" fill="{t["ink"]}" fill-opacity=".45">{day.strftime("%b").lower()}</text>')
    status, dot = ("ALIVE", t["red"]) if st["alive"] else ("FLATLINE", t["ink"])
    peak = st["peak_date"].strftime("%b %d").lower()
    period = min(2.0, max(.5, 60 / max(st["bpm"], 1)))       # one press per heartbeat
    k = 6.5 / 9
    kx, ky, kw, kh = 690, 346, 204, 110                       # ENTER keycap sprite (2.25u)
    pcx, pcy = kx + 268, ky + kh / 2                          # paw sprite centre, toes rotated to the left
    quote = "".join(
        f'<text x="30" y="{360 + 26 * n}" font-size="15" fill="{t["ink"]}" fill-opacity=".85" xml:space="preserve">'
        + line.replace("ENTER", f'<tspan fill="{t["red"]}" font-weight="700">ENTER</tspan>') + "</text>"
        for n, line in enumerate(QUOTE))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="vitals: {st["total"]} contributions in the last year, {st["bpm"]} per week">
<defs><style>{css(period)}</style>
<filter id="glow" x="-5%" y="-30%" width="110%" height="160%"><feGaussianBlur stdDeviation="3"/></filter>
<filter id="blur" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="9"/></filter>
<linearGradient id="hd" x1="1" x2="0"><stop offset="0" stop-color="{t["head"]}" stop-opacity=".9"/><stop offset="1" stop-color="{t["head"]}" stop-opacity="0"/></linearGradient>
<linearGradient id="deskG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["desk"]}"/><stop offset="1" stop-color="{t["bg"]}"/></linearGradient>
<clipPath id="rev"><rect x="0" y="0" width="0" height="{DESK}"><animate attributeName="width" dur="9s" repeatCount="indefinite" keyTimes="0;{k:.3f};1" values="0;{W};{W}"/></rect></clipPath>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="8"/></clipPath></defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{t["bg"]}"/>
<path d="{grid}" stroke="{t["grid"]}" stroke-opacity="{t["g1"]}"/><path d="{major}" stroke="{t["grid"]}" stroke-opacity="{t["g2"]}"/>
<path d="{d}" fill="none" stroke="{t["trace"]}" stroke-opacity="{t["old"]}" stroke-width="2" stroke-linejoin="round"/>
<g clip-path="url(#rev)"><path d="{d}" fill="none" stroke="{t["trace"]}" stroke-width="5" stroke-opacity=".45" filter="url(#glow)"/>
<path d="{d}" fill="none" stroke="{t["trace"]}" stroke-width="2.2" stroke-linejoin="round"/></g>
<rect y="{BASE - AMP - 10}" width="26" height="{AMP + 60}" fill="url(#hd)"><animate attributeName="x" dur="9s" repeatCount="indefinite" keyTimes="0;{k:.3f};1" values="-26;{W - 26};{W + 40}"/></rect>
<g font-size="12">{"".join(ticks)}</g>
<circle class="p" cx="42" cy="38" r="6" fill="{dot}"/>
<text x="56" y="43" font-size="14" font-weight="700" fill="{t["ink"]}">VITALS</text><text x="126" y="43" font-size="14" fill="{t["ink"]}" fill-opacity=".5">// {login}</text>
<text x="{W - 30}" y="43" font-size="14" font-weight="700" text-anchor="end" fill="{dot}">STATUS: {status}</text>
<text x="30" y="{DESK - 22}" font-size="13" fill="{t["ink"]}" fill-opacity=".75">TOTAL {st["total"]} / yr · PEAK {st["peak"]} (wk of {peak}) · STREAK {st["cur"]}d · LONGEST {st["best"]}d</text>
<text x="{W - 104}" y="{DESK - 40}" font-size="14" font-weight="700" text-anchor="end" fill="{t["ink"]}" fill-opacity=".8">bpm</text>
<text x="{W - 104}" y="{DESK - 22}" font-size="12" text-anchor="end" fill="{t["ink"]}" fill-opacity=".5">avg contributions / week</text>
<text class="bpm" x="{W - 30}" y="{DESK - 20}" font-size="54" font-weight="700" text-anchor="end" fill="{t["red"]}">{st["bpm"]}</text>
<rect y="{DESK}" width="{W}" height="{H - DESK}" fill="url(#deskG)"/>
<path d="M0,{DESK}H{W}" stroke="{t["ink"]}" stroke-opacity=".14"/>
{quote}
<rect class="led" x="{kx + 6}" y="{ky + 8}" width="{kw - 12}" height="{kh - 10}" rx="14" fill="{t["red"]}" fill-opacity=".75" filter="url(#blur)"/>
<g class="key"><image href="data:image/png;base64,{b64(f"key-{theme}.png")}" x="{kx}" y="{ky}" width="{kw}" height="{kh}"/>
<text x="{kx + 30}" y="{ky + 50}" font-size="16" font-weight="700" fill="{t["legend"]}" fill-opacity=".9">ENTER</text>
<text x="{kx + 86}" y="{ky + 52}" font-size="20" font-weight="700" fill="{t["red"]}">↵</text></g>
<g class="tap"><ellipse cx="{pcx - 6}" cy="{pcy + 20}" rx="120" ry="52" fill="{t["shade"]}" fill-opacity=".45" filter="url(#blur)"/>
<image href="data:image/png;base64,{b64(f"pawtop-{theme}.png")}" x="{pcx - 86}" y="{pcy - 134.5}" width="172" height="269" transform="rotate(-90 {pcx} {pcy})"/></g>
</g></svg>'''


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    login = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GITHUB_REPOSITORY_OWNER", "ProximaCA")
    total, weeks = fetch(login, os.environ["GITHUB_TOKEN"])
    st = stats(total, weeks)
    os.makedirs(out, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(out, f"vitals-{theme}.svg"), "w") as f:
            f.write(svg(st, weeks, theme, login))
    print(f"vitals: {st['total']} contributions, {st['bpm']} bpm, streak {st['cur']}d")
