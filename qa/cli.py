"""Command line entry point: `python -m qa <command>`."""
from __future__ import annotations

import sys
from pathlib import Path

from qa import gate, htmlreport, report
from qa.audio import inventory
from qa.gfxinfo import parse_framestats, parse_summary
from qa.rtp import confidence_interval, measure, read_rounds

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_CONFIG = ROOT / "config.json"


def _split_config(args: list[str]) -> tuple[list[str], Path]:
    """Every subcommand accepts --config <path>, so a release gate can be tried
    without editing the committed one."""
    rest: list[str] = []
    config = DEFAULT_CONFIG
    index = 0
    while index < len(args):
        if args[index] == "--config" and index + 1 < len(args):
            config = Path(args[index + 1])
            index += 2
            continue
        rest.append(args[index])
        index += 1
    return rest, config


def _perf(args: list[str]) -> int:
    args, config = _split_config(args)
    if not args:
        print("usage: python -m qa perf <gfxinfo.txt> [--summary]", file=sys.stderr)
        return 2
    path = Path(args[0])
    cfg = gate.load_config(config)
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
    args, config = _split_config(args)
    if not args:
        print("usage: python -m qa sim <simulation.csv>", file=sys.stderr)
        return 2
    path = Path(args[0])
    cfg = gate.load_config(config)
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


def _collect(config: Path = DEFAULT_CONFIG) -> tuple[list[gate.Check], str]:
    cfg = gate.load_config(config)
    frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
    summary = parse_summary((FIXTURES / "gfxinfo_summary.txt").read_text(encoding="utf-8"))
    stats = measure(read_rounds(FIXTURES / "simulation.csv"))
    clips = inventory(FIXTURES / "audio")
    checks = (
        gate.check_frames(frames, cfg)
        + gate.check_summary(summary, cfg)
        + gate.check_simulation(stats, cfg)
        + gate.check_audio(clips, cfg)
    )
    detail = (
        f"frames={frames.count} p50={frames.percentile(50):.2f}ms "
        f"p90={frames.percentile(90):.2f}ms p99={frames.percentile(99):.2f}ms | "
        f"rounds={stats.rounds} rtp={stats.rtp:.4f} hit={stats.hit_frequency:.4f} "
        f"volatility={stats.volatility:.3f} | audio={len(clips)} clips "
        f"{', '.join(f'{c.path.stem}:{c.duration_ms:.0f}ms/{c.rms_db:.1f}dB' for c in clips if c.decodable)}"
    )
    return checks, detail


def _audio(args: list[str]) -> int:
    args, config = _split_config(args)
    if not args:
        print("usage: python -m qa audio <dir with wav files>", file=sys.stderr)
        return 2
    directory = Path(args[0])
    cfg = gate.load_config(config)
    clips = inventory(directory)
    checks = gate.check_audio(clips, cfg)
    print(report.render(checks, f"audio: {directory}"))
    for clip in clips:
        if clip.decodable:
            print(f"  {clip.path.name:24} {clip.duration_ms:8.1f} ms  {clip.sample_rate} Hz  "
                  f"{clip.channels}ch  {clip.encoding:8} rms {clip.rms_db:6.1f} dB  peak {clip.peak:.4f}  "
                  f"rail {100 * (clip.full_scale_ratio or 0):.2f}% run={clip.longest_run}")
        else:
            if clip.duration_ms is None:
                print(f"  {clip.path.name:24} unreadable header")
            else:
                print(f"  {clip.path.name:24} {clip.duration_ms:8.1f} ms  {clip.sample_rate} Hz  "
                      f"{clip.channels}ch  {clip.encoding}  header only, not judged")
    return report.exit_code(checks)


def _html(args: list[str]) -> int:
    args, config = _split_config(args)
    out = Path(args[0]) if args and not args[0].startswith("--") else ROOT / "out" / "report.html"
    video = None
    shots: list[Path] = []
    sources: dict[str, str] = {}
    device = "not attached"
    for arg in args:
        if arg.startswith("--video="):
            video = Path(arg.split("=", 1)[1])
        elif arg.startswith("--shots="):
            shots = [Path(p) for p in arg.split("=", 1)[1].split(",") if p]
        elif arg.startswith("--device="):
            device = arg.split("=", 1)[1]
        elif arg.startswith("--") and "=" in arg:
            key, value = arg[2:].split("=", 1)
            sources[key] = value

    if sources:
        cfg = gate.load_config(config)
        checks: list[gate.Check] = []
        detail: list[str] = []
        if "perf" in sources:
            frames = parse_framestats(Path(sources["perf"]).read_text(encoding="utf-8"))
            checks += gate.check_frames(frames, cfg)
            detail.append(f"frames={frames.count} p50={frames.percentile(50):.2f}ms "
                          f"p90={frames.percentile(90):.2f}ms p99={frames.percentile(99):.2f}ms")
        if "summary" in sources:
            summary = parse_summary(Path(sources["summary"]).read_text(encoding="utf-8"))
            checks += gate.check_summary(summary, cfg)
            detail.append(f"device summary: {summary.total_frames} frames, {summary.janky_frames} janky")
        if "sim" in sources:
            stats = measure(read_rounds(Path(sources["sim"])))
            checks += gate.check_simulation(stats, cfg)
            detail.append(f"rounds={stats.rounds} rtp={stats.rtp:.4f}")
        if "audio" in sources:
            clips = inventory(Path(sources["audio"]))
            checks += gate.check_audio(clips, cfg)
            detail.append(f"audio={len(clips)} files")
        text = " | ".join(detail)
        source = "measured on: " + ", ".join(sorted(sources))
    else:
        checks, text = _collect(config)
        source = "recorded fixtures (tests/fixtures) — not a device capture"

    meta = htmlreport.RunMeta(
        title="Build gate",
        source=source,
        device=device,
        video=video,
        shots=tuple(shots),
    )
    extras = f'<h2>Measured</h2><p class="muted">{text}</p>'
    shown = config if config is not None else ROOT / "config.json"
    try:
        shown = Path(shown).resolve().relative_to(ROOT)
    except (ValueError, OSError):
        shown = Path(shown).name
    extras += f'<h2>Thresholds</h2><p class="muted">{shown}</p>'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(htmlreport.render(checks, meta, ROOT, extras), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(checks)} checks)")
    return report.exit_code(checks)


def _demo(args: list[str]) -> int:
    _, config = _split_config(args)
    cfg = gate.load_config(config)
    frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
    summary = parse_summary((FIXTURES / "gfxinfo_summary.txt").read_text(encoding="utf-8"))
    stats = measure(read_rounds(FIXTURES / "simulation.csv"))
    clips = inventory(FIXTURES / "audio")
    checks = (
        gate.check_frames(frames, cfg)
        + gate.check_summary(summary, cfg)
        + gate.check_simulation(stats, cfg)
        + gate.check_audio(clips, cfg)
    )
    print(report.render(checks, "demo: recorded fixtures (not measured on a device)"))
    return report.exit_code(checks)


COMMANDS = {"perf": _perf, "sim": _sim, "demo": _demo, "html": _html, "audio": _audio}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: python -m qa {demo|perf <file>|sim <csv>|audio <dir>|html [out.html]} [--config path]")
        return 0
    command, rest = argv[0], argv[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"unknown command: {command}", file=sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
