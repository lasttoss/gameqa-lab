"""Command line entry point: `python -m qa <command>`."""
from __future__ import annotations

import sys
from pathlib import Path

from qa import gate, htmlreport, report
from qa.gfxinfo import parse_framestats, parse_summary
from qa.rtp import confidence_interval, measure, read_rounds

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def _perf(args: list[str]) -> int:
    if not args:
        print("usage: python -m qa perf <gfxinfo.txt> [--summary]", file=sys.stderr)
        return 2
    path = Path(args[0])
    cfg = gate.load_config(ROOT / "config.json")
    text = path.read_text(encoding="utf-8")
    if "--summary" in args:
        checks = gate.check_summary(parse_summary(text), cfg)
        title = f"Perf gate from device summary: {path.name}"
    else:
        checks = gate.check_frames(parse_framestats(text), cfg)
        title = f"Perf gate from framestats: {path.name}"
    print(report.render(checks, title))
    return report.exit_code(checks)


def _sim(args: list[str]) -> int:
    if not args:
        print("usage: python -m qa sim <simulation.csv>", file=sys.stderr)
        return 2
    path = Path(args[0])
    cfg = gate.load_config(ROOT / "config.json")
    stats = measure(read_rounds(path))
    low, high = confidence_interval(stats)
    checks = gate.check_simulation(stats, cfg)
    print(report.render(checks, f"Simulation gate: {path.name}"))
    print(
        f"       rounds={stats.rounds} rtp={stats.rtp:.4f} "
        f"ci95=[{low:.4f}, {high:.4f}] hit={stats.hit_frequency:.4f} "
        f"volatility={stats.volatility:.3f} max_x={stats.max_win_multiplier:.1f}"
    )
    return report.exit_code(checks)


def _collect() -> tuple[list[gate.Check], str]:
    cfg = gate.load_config(ROOT / "config.json")
    frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
    summary = parse_summary((FIXTURES / "gfxinfo_summary.txt").read_text(encoding="utf-8"))
    stats = measure(read_rounds(FIXTURES / "simulation.csv"))
    checks = gate.check_frames(frames, cfg) + gate.check_summary(summary, cfg) + gate.check_simulation(stats, cfg)
    detail = (
        f"frames={frames.count} p50={frames.percentile(50):.2f}ms "
        f"p90={frames.percentile(90):.2f}ms p99={frames.percentile(99):.2f}ms | "
        f"rounds={stats.rounds} rtp={stats.rtp:.4f} hit={stats.hit_frequency:.4f} "
        f"volatility={stats.volatility:.3f}"
    )
    return checks, detail


def _html(args: list[str]) -> int:
    out = Path(args[0]) if args else ROOT / "out" / "report.html"
    video = None
    shots: list[Path] = []
    for arg in args[1:]:
        if arg.startswith("--video="):
            video = Path(arg.split("=", 1)[1])
        elif arg.startswith("--shots="):
            shots = [Path(p) for p in arg.split("=", 1)[1].split(",") if p]
    checks, detail = _collect()
    meta = htmlreport.RunMeta(
        title="Slot build gate",
        source="recorded fixtures (tests/fixtures) — not a device capture",
        device="not attached",
        video=video,
        shots=tuple(shots),
    )
    extras = f'<h2>Measured</h2><p class="muted">{detail}</p>'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(htmlreport.render(checks, meta, ROOT, extras), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(checks)} checks)")
    return report.exit_code(checks)


def _demo(_: list[str]) -> int:
    cfg = gate.load_config(ROOT / "config.json")
    frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
    summary = parse_summary((FIXTURES / "gfxinfo_summary.txt").read_text(encoding="utf-8"))
    stats = measure(read_rounds(FIXTURES / "simulation.csv"))
    checks = gate.check_frames(frames, cfg) + gate.check_summary(summary, cfg) + gate.check_simulation(stats, cfg)
    print(report.render(checks, "demo: recorded fixtures (not measured on a device)"))
    return report.exit_code(checks)


COMMANDS = {"perf": _perf, "sim": _sim, "demo": _demo, "html": _html}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: python -m qa {demo|perf <file>|sim <csv>|html [out.html]}")
        return 0
    command, rest = argv[0], argv[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
