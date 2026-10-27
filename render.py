"""Static HTML rendering for the family newsletter (Bauhaus / monochrome).

All model output is HTML-escaped here; the model never produces markup.
"""

import datetime as dt
from html import escape
from urllib.parse import urlparse

CSS = """
:root{--ink:#111;--paper:#f4f2ee;--mute:#5c5c5c;--line:#111;--card:#fff}
@media (prefers-color-scheme:dark){:root{--ink:#eceae6;--paper:#121212;--mute:#a3a3a3;--line:#eceae6;--card:#1b1b1b}}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:"Helvetica Neue",Helvetica,Arial,"Liberation Sans",sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit}
.wrap{max-width:980px;margin:0 auto;padding:0 20px}
header.mast{border-bottom:6px solid var(--line);padding:40px 0 28px}
.mast .row{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}
.mast h1{font-size:clamp(2.2rem,7vw,4.6rem);line-height:.92;font-weight:900;letter-spacing:-.03em;text-transform:uppercase}
.mast .sub{margin-top:14px;font-size:1rem;color:var(--mute);max-width:46ch}
.shapes{display:flex;gap:10px;align-items:flex-end}
.shapes svg{display:block}
.meta{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;border-bottom:1px solid var(--line);padding:10px 0;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase}
.intro{font-size:1.25rem;line-height:1.5;padding:36px 0;max-width:60ch;font-weight:500}
section.topic{border-top:6px solid var(--line);padding:22px 0 44px}
.topic-head{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:baseline;margin-bottom:22px}
.num{font-size:3rem;font-weight:900;line-height:1;letter-spacing:-.04em}
.topic h2{font-size:1.5rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));border-top:2px solid var(--line);border-left:2px solid var(--line)}
article{background:var(--card);padding:22px 20px 20px;display:flex;flex-direction:column;gap:10px;border-right:2px solid var(--line);border-bottom:2px solid var(--line)}
article h3{font-size:1.12rem;line-height:1.25;font-weight:800}
article p{font-size:.96rem}
.why{font-size:.88rem;border-left:4px solid var(--line);padding-left:10px;color:var(--mute)}
.src{margin-top:auto;font-size:.75rem;letter-spacing:.08em;text-transform:uppercase}
.src a{text-decoration:none;border-bottom:1px solid var(--line)}
.empty{color:var(--mute);font-style:italic}
footer{border-top:1px solid var(--line);padding:18px 0 40px;font-size:.78rem;color:var(--mute);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
ol.issues{list-style:none;border-top:6px solid var(--line);margin-top:32px}
ol.issues li{border-bottom:1px solid var(--line)}
ol.issues a{display:grid;grid-template-columns:150px 1fr;gap:18px;padding:18px 0;text-decoration:none}
ol.issues a:hover{background:var(--card)}
.idate{font-weight:900;font-size:1.05rem;letter-spacing:-.01em}
.iheads{font-size:.92rem;color:var(--mute)}
.latest{display:inline-block;margin-top:24px;background:var(--ink);color:var(--paper);padding:12px 20px;text-decoration:none;font-weight:800;text-transform:uppercase;letter-spacing:.1em;font-size:.85rem}
section.weather{border-top:6px solid var(--line);padding:22px 0 36px}
.weather h2{font-size:1.5rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em;margin-bottom:18px}
.weather h2 small{font-size:.78rem;font-weight:500;color:var(--mute);letter-spacing:.1em;margin-left:10px}
.days{display:grid;grid-template-columns:repeat(6,1fr);border-top:2px solid var(--line);border-left:2px solid var(--line)}
.day{background:var(--card);padding:16px 14px;display:flex;flex-direction:column;gap:4px;border-right:2px solid var(--line);border-bottom:2px solid var(--line)}
.dname{font-size:.78rem;letter-spacing:.12em;text-transform:uppercase;font-weight:800}
.day svg{display:block;margin:6px 0}
.temps{font-size:1.5rem;font-weight:900;letter-spacing:-.02em}
.temps span{font-size:1rem;font-weight:500;color:var(--mute)}
.cond{font-size:.88rem}
.pop{font-size:.78rem;color:var(--mute)}
@media (max-width:760px){.days{grid-template-columns:repeat(3,1fr)}}
@media (max-width:560px){ol.issues a{grid-template-columns:1fr;gap:4px}.shapes{display:none}}
"""

SHAPES = """<div class="shapes" aria-hidden="true">
<svg width="54" height="54" viewBox="0 0 54 54"><circle cx="27" cy="27" r="27" fill="currentColor"/></svg>
<svg width="54" height="54" viewBox="0 0 54 54"><rect width="54" height="54" fill="none" stroke="currentColor" stroke-width="6"/></svg>
<svg width="60" height="54" viewBox="0 0 60 54"><polygon points="30,0 60,54 0,54" fill="currentColor"/></svg>
</div>"""


def _page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>')


def _safe_href(url):
    return escape(url) if urlparse(url).scheme in ("http", "https") else "#"


def _domain(url):
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _nice_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d:%A}, {d:%B} {d.day}, {d:%Y}"


_CLOUD = ('<circle cx="15" cy="17" r="7"/><circle cx="25" cy="13" r="9"/>'
          '<rect x="8" y="17" width="26" height="10" rx="5"/>')
_RAYS = "".join(f'<line x1="{22 + 13 * c:.1f}" y1="{22 + 13 * s:.1f}" x2="{22 + 18 * c:.1f}" '
                f'y2="{22 + 18 * s:.1f}"/>'
                for c, s in ((1, 0), (.707, .707), (0, 1), (-.707, .707),
                             (-1, 0), (-.707, -.707), (0, -1), (.707, -.707)))
_ICONS = {
    "sun": f'<circle cx="22" cy="22" r="9"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round">{_RAYS}</g>',
    "partly": ('<circle cx="14" cy="14" r="7"/>'
               f'<g transform="translate(4 8)" stroke="var(--card)" stroke-width="2">{_CLOUD}</g>'),
    "cloud": f'<g transform="translate(0 5)">{_CLOUD}</g>',
    "rain": (f'{_CLOUD}<g stroke="currentColor" stroke-width="3" stroke-linecap="round">'
             '<line x1="14" y1="32" x2="11" y2="40"/><line x1="22" y1="32" x2="19" y2="40"/>'
             '<line x1="30" y1="32" x2="27" y2="40"/></g>'),
    "snow": (f'{_CLOUD}<circle cx="13" cy="35" r="2.5"/><circle cx="22" cy="38" r="2.5"/>'
             '<circle cx="31" cy="35" r="2.5"/>'),
    "storm": f'{_CLOUD}<polygon points="24,28 16,38 22,38 19,44 30,33 24,33"/>',
}


def _icon(kind):
    return (f'<svg width="44" height="44" viewBox="0 0 44 44" fill="currentColor" aria-hidden="true">'
            f'{_ICONS.get(kind, _ICONS["cloud"])}</svg>')


def _day_name(iso, first):
    if first:
        return "Today"
    d = dt.date.fromisoformat(iso)
    return f"{d:%a} {d.day}"


def _render_weather(weather):
    """Forecast strip; values come from the forecast API, all text is escaped."""
    where = weather.get("location", "")
    parts = [f'<section class="weather"><h2>Weather<small>{escape(where)}</small></h2><div class="days">']
    for i, day in enumerate(weather["days"]):
        pop = day.get("precip")
        pop_html = f'<span class="pop" title="Chance of rain or snow">Precip. {int(pop)}%</span>' if pop is not None else ""
        parts.append(
            f'<div class="day"><span class="dname">{escape(_day_name(day["date"], i == 0))}</span>'
            f'{_icon(day.get("kind"))}'
            f'<span class="temps">{int(day["high"])}&deg; <span>/ {int(day["low"])}&deg;</span></span>'
            f'<span class="cond">{escape(day["label"])}</span>{pop_html}</div>')
    parts.append('</div></section>')
    return "".join(parts)


def render_issue(issue):
    parts = [f'<header class="mast"><div class="wrap"><div class="row"><div>'
             f'<h1>{escape(issue["title"])}</h1>'
             f'<p class="sub">{escape(issue.get("subtitle", ""))}</p></div>{SHAPES}</div></div></header>'
             f'<div class="wrap"><div class="meta"><span>{escape(_nice_date(issue["date"]))}</span>'
             f'<span><a href="../index.html">All issues &rarr;</a></span></div>']
    if issue.get("intro"):
        parts.append(f'<p class="intro">{escape(issue["intro"])}</p>')
    if issue.get("weather") and issue["weather"].get("days"):
        parts.append(_render_weather(issue["weather"]))

    for i, sec in enumerate(issue["sections"], 1):
        parts.append(f'<section class="topic"><div class="topic-head"><span class="num">{i:02d}</span>'
                     f'<h2>{escape(sec["name"])}</h2></div>')
        if not sec["stories"]:
            parts.append('<p class="empty">No verified stories this week.</p></section>')
            continue
        parts.append('<div class="grid">')
        for st in sec["stories"]:
            label = st.get("source_title") or _domain(st["source_url"])
            parts.append(
                f'<article><h3>{escape(st["headline"])}</h3><p>{escape(st["summary"])}</p>'
                f'<p class="why">{escape(st["why_it_matters"])}</p>'
                f'<p class="src">Source: <a href="{_safe_href(st["source_url"])}" target="_blank" '
                f'rel="noopener noreferrer" title="{escape(label)}">{escape(_domain(st["source_url"]))}</a></p>'
                f'</article>')
        parts.append('</div></section>')

    parts.append(f'<footer><span>Researched and written by a local AI ({escape(issue.get("model", ""))}). '
                 f'Check sources before acting on anything.</span><span>{escape(issue["date"])}</span></footer></div>')
    return _page(f'{issue["title"]} — {issue["date"]}', "".join(parts))


def render_index(nl, issues):
    parts = [f'<header class="mast"><div class="wrap"><div class="row"><div>'
             f'<h1>{escape(nl["title"])}</h1><p class="sub">{escape(nl.get("subtitle", ""))}</p>'
             f'</div>{SHAPES}</div></div></header><div class="wrap">']
    if issues:
        parts.append('<a class="latest" href="latest.html">Read the latest issue</a><ol class="issues">')
        for iss in issues:
            heads = [st["headline"] for sec in iss["sections"] for st in sec["stories"]][:3]
            parts.append(f'<li><a href="issues/{escape(iss["date"])}.html">'
                         f'<span class="idate">{escape(iss["date"])}</span>'
                         f'<span class="iheads">{escape(" · ".join(heads))}</span></a></li>')
        parts.append('</ol>')
    else:
        parts.append('<p class="intro">No issues yet.</p>')
    parts.append('<footer><span>Family network only.</span></footer></div>')
    return _page(nl["title"], "".join(parts))
