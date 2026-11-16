"""Render one self-contained HTML artefact: table, bars, and the run video.

No external CSS, no fonts, no CDN: the file opens on a laptop that has no network,
which is how a QA report is actually reviewed. Everything measured is printed
next to its limit; the footer says what the numbers do not prove.
"""
from __future__ import annotations

import datetime as dt
import html
import subprocess
from dataclasses import dataclass
from pathlib import Path

from qa.gate import Check


@dataclass(frozen=True)
class RunMeta:
    title: str
    source: str
    device: str = "not attached (fixtures)"
    video: Path | None = None
    shots: tuple[Path, ...] = ()


def _git_sha(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _bar(check: Check) -> str:
    limit = abs(check.limit) or 1.0
    value = abs(check.value)
    pct = max(2.0, min(100.0, 100.0 * value / limit))
    colour = "#1f7a4d" if check.passed else "#b3261e"
    return (
        f'<div class="bar"><span style="width:{pct:.1f}%;background:{colour}"></span>'
        f'<i style="left:{min(99.4, 100.0 * min(value, limit) / limit):.1f}%"></i></div>'
    )


def _rows(checks: list[Check]) -> str:
    out = []
    for check in checks:
        badge = "pass" if check.passed else "fail"
        out.append(
            f'<tr><td><span class="badge {badge}">{"PASS" if check.passed else "FAIL"}</span></td>'
            f'<td class="name">{html.escape(check.name)}</td>'
            f'<td class="num">{check.value:,.3f}</td>'
            f'<td class="num">{check.limit:,.3f}</td>'
            f'<td>{_bar(check)}</td>'
            f'<td class="detail">{html.escape(check.detail)}</td></tr>'
        )
    return "\n".join(out)


def render(checks: list[Check], meta: RunMeta, root: Path, extras: str = "") -> str:
    failed = sum(1 for c in checks if not c.passed)
    status = "GATE PASSED" if failed == 0 else f"GATE FAILED ({failed})"
    colour = "#1f7a4d" if failed == 0 else "#b3261e"
    stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    video_block = ""
    if meta.video and meta.video.exists():
        video_block = (
            f'<h2>Run video</h2><p class="muted">{html.escape(meta.video.name)} — '
            f'frames inside this window are the ones measured above.</p>'
            f'<video controls preload="metadata" src="{html.escape(meta.video.name)}"></video>'
        )
    shots_block = ""
    present = [p for p in meta.shots if p.exists()]
    if present:
        figures = "".join(
            f'<figure><img src="{html.escape(p.name)}" alt="{html.escape(p.stem)}">'
            f'<figcaption>{html.escape(p.stem)}</figcaption></figure>'
            for p in present
        )
        shots_block = f"<h2>Scene checkpoints</h2><div class=\"shots\">{figures}</div>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(meta.title)} — QA report</title>
<style>
 :root {{ --ink:#2d3142; --muted:#5b6478; --rule:#d7d9e0; --paper:#ffffff; --soft:#f5f6f8; }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; padding:32px 28px 48px; background:var(--paper); color:var(--ink);
        font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
 h1 {{ font-size:20px; margin:0 0 4px; letter-spacing:-.01em; }}
 h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted);
       margin:32px 0 10px; border-bottom:1px solid var(--rule); padding-bottom:6px; }}
 .meta {{ color:var(--muted); font-size:12.5px; }}
 .status {{ display:inline-block; margin:18px 0 0; padding:8px 14px; border-radius:4px;
            background:var(--soft); border-left:4px solid {colour}; font-weight:600;
            letter-spacing:.02em; font-size:13px; }}
 table {{ width:100%; border-collapse:collapse; margin-top:6px; font-size:13px; }}
 th {{ text-align:left; font-weight:600; color:var(--muted); font-size:11.5px;
       text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid var(--rule); padding:6px 8px; }}
 td {{ padding:7px 8px; border-bottom:1px solid #eef0f3; vertical-align:middle; }}
 td.num {{ font-variant-numeric:tabular-nums; text-align:right; width:88px; }}
 td.name {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; }}
 td.detail {{ color:var(--muted); font-size:12px; }}
 .badge {{ display:inline-block; padding:2px 7px; border-radius:3px; font-size:10.5px;
           font-weight:700; letter-spacing:.06em; }}
 .badge.pass {{ background:#e6f2ea; color:#1f7a4d; }}
 .badge.fail {{ background:#fbe9e7; color:#b3261e; }}
 .bar {{ position:relative; height:8px; background:#eef0f3; border-radius:2px; min-width:120px; }}
 .bar span {{ position:absolute; left:0; top:0; bottom:0; border-radius:2px; }}
 .bar i {{ position:absolute; top:-3px; bottom:-3px; width:1px; background:var(--muted); }}
 video {{ width:100%; max-width:720px; border:1px solid var(--rule); border-radius:4px; }}
 .shots {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:12px; }}
 figure {{ margin:0; border:1px solid var(--rule); border-radius:4px; overflow:hidden; }}
 figure img {{ width:100%; display:block; }}
 figcaption {{ font-size:11.5px; color:var(--muted); padding:6px 8px; background:var(--soft); }}
 .muted {{ color:var(--muted); font-size:12.5px; }}
 footer {{ margin-top:36px; padding-top:14px; border-top:1px solid var(--rule);
           color:var(--muted); font-size:12px; }}
</style></head><body>
<h1>{html.escape(meta.title)}</h1>
<div class="meta">{html.escape(meta.source)} · device: {html.escape(meta.device)} ·
 commit {html.escape(_git_sha(root))} · {html.escape(stamp)}</div>
<div class="status">{html.escape(status)}</div>

<h2>Checks</h2>
<table>
<thead><tr><th>result</th><th>check</th><th>value</th><th>limit</th><th>against limit</th><th>note</th></tr></thead>
<tbody>
{_rows(checks)}
</tbody></table>
{extras}
{video_block}
{shots_block}
<footer>
Thresholds come from <code>config.json</code>; the marker on each bar is the limit.
Nothing here was measured on a production slot build unless the device line says so,
and audio is not checked yet. A report that cannot fail is decoration —
<code>make guard</code> proves this one can.
</footer>
</body></html>
"""
