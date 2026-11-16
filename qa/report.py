"""Render checks as one block of text, and decide the exit code."""
from __future__ import annotations

from qa.gate import Check


def render(checks: list[Check], title: str) -> str:
    width = max((len(c.name) for c in checks), default=10)
    lines = [title, "-" * len(title)]
    for check in checks:
        mark = "PASS" if check.passed else "FAIL"
        lines.append(
            f"{mark}  {check.name:<{width}}  value {check.value:>10.3f}  "
            f"limit {check.limit:>10.3f}  {check.detail}".rstrip()
        )
    failed = sum(1 for c in checks if not c.passed)
    lines.append("")
    lines.append(f"RESULT gate=armed checks={len(checks)} failed={failed}")
    return "\n".join(lines)


def exit_code(checks: list[Check]) -> int:
    return 0 if all(c.passed for c in checks) else 1
