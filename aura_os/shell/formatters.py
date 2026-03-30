"""Output formatters for AURA OS command results.

Provides helpers to produce rich, colored terminal output for tables,
key-value panels, and status information.  Falls back to plain text
when colour is unavailable.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from aura_os.shell.colors import (
    bold, bright_cyan, bright_green, bright_yellow, cyan, dim, green,
    header, info, label, muted, progress_bar, red, yellow,
)


# ──────────────────────────────────────────────────────────────────────
# Table formatter
# ──────────────────────────────────────────────────────────────────────

def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    col_widths: Optional[Sequence[int]] = None,
) -> str:
    """Format a simple table with colored headers.

    >>> print(table(["Name", "Value"], [["a", "1"], ["b", "2"]]))
    """
    if col_widths is None:
        # Auto-calculate widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

    # Header row
    hdr = "  ".join(
        bold(h.ljust(w)) for h, w in zip(headers, col_widths)
    )
    sep = dim("─" * (sum(col_widths) + 2 * (len(col_widths) - 1)))

    lines = [f"  {hdr}", f"  {sep}"]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            w = col_widths[i] if i < len(col_widths) else 0
            cells.append(str(cell).ljust(w))
        lines.append(f"  {'  '.join(cells)}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Key-value panel
# ──────────────────────────────────────────────────────────────────────

def kv_panel(
    title: str,
    items: Sequence[Tuple[str, str]],
    label_width: int = 18,
) -> str:
    """Render a colored key-value panel.

    Example::

        ╭─ System ──────────────────────────╮
        │  Platform        : linux           │
        │  Uptime          : 2d 3h 15m       │
        ╰───────────────────────────────────╯
    """
    content_width = max(
        label_width + 5 + max((len(str(v)) for _, v in items), default=0),
        len(title) + 6,
    )
    box_width = content_width + 4

    top = f"  ╭─ {header(title)} {'─' * max(0, box_width - len(title) - 6)}╮"
    bottom = f"  ╰{'─' * (box_width - 2)}╯"

    lines = [top]
    for k, v in items:
        line_content = f"  {label(k):<{label_width + 10}}  {v}"
        lines.append(f"  │{line_content}│")
    lines.append(bottom)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Section header
# ──────────────────────────────────────────────────────────────────────

def section(title: str, width: int = 50) -> str:
    """Return a colored section separator."""
    line = dim("─" * width)
    return f"  {line}\n  {header(title)}\n  {line}"


# ──────────────────────────────────────────────────────────────────────
# Badge list (for capabilities, tags, etc.)
# ──────────────────────────────────────────────────────────────────────

def badges(items: Sequence[str], per_row: int = 4) -> str:
    """Return items formatted as colored badges."""
    lines = []
    for i in range(0, len(items), per_row):
        chunk = items[i:i + per_row]
        row = "  ".join(cyan(f"[{item}]") for item in chunk)
        lines.append(f"    {row}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Status message helpers
# ──────────────────────────────────────────────────────────────────────

def success_msg(text: str) -> str:
    return f"  {green('✔')} {text}"

def error_msg(text: str) -> str:
    return f"  {red('✘')} {text}"

def warning_msg(text: str) -> str:
    return f"  {yellow('⚠')} {text}"

def info_msg(text: str) -> str:
    return f"  {cyan('ℹ')} {text}"
