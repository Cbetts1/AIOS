"""ANSI color utilities for AURA OS terminal output.

Provides a lightweight, zero-dependency color system with automatic
detection of terminal color support.  Degrades gracefully when output
is piped or redirected.
"""

import os
import sys

# ──────────────────────────────────────────────────────────────────────
# Colour support detection
# ──────────────────────────────────────────────────────────────────────

def _supports_color() -> bool:
    """Return *True* if the current stdout appears to support ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


_COLOR_ENABLED = _supports_color()


# ──────────────────────────────────────────────────────────────────────
# ANSI escape sequences
# ──────────────────────────────────────────────────────────────────────

_CODES = {
    "reset":     "\033[0m",
    "bold":      "\033[1m",
    "dim":       "\033[2m",
    "italic":    "\033[3m",
    "underline": "\033[4m",
    # Foreground
    "black":     "\033[30m",
    "red":       "\033[31m",
    "green":     "\033[32m",
    "yellow":    "\033[33m",
    "blue":      "\033[34m",
    "magenta":   "\033[35m",
    "cyan":      "\033[36m",
    "white":     "\033[37m",
    # Bright foreground
    "bright_red":     "\033[91m",
    "bright_green":   "\033[92m",
    "bright_yellow":  "\033[93m",
    "bright_blue":    "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan":    "\033[96m",
    "bright_white":   "\033[97m",
}


def _wrap(code_name: str, text: str) -> str:
    """Wrap *text* in the ANSI escape for *code_name*, if colours are enabled."""
    if not _COLOR_ENABLED:
        return text
    return f"{_CODES[code_name]}{text}{_CODES['reset']}"


# ──────────────────────────────────────────────────────────────────────
# Public helpers
# ──────────────────────────────────────────────────────────────────────

def bold(text: str) -> str:
    return _wrap("bold", text)

def dim(text: str) -> str:
    return _wrap("dim", text)

def red(text: str) -> str:
    return _wrap("red", text)

def green(text: str) -> str:
    return _wrap("green", text)

def yellow(text: str) -> str:
    return _wrap("yellow", text)

def blue(text: str) -> str:
    return _wrap("blue", text)

def magenta(text: str) -> str:
    return _wrap("magenta", text)

def cyan(text: str) -> str:
    return _wrap("cyan", text)

def bright_cyan(text: str) -> str:
    return _wrap("bright_cyan", text)

def bright_green(text: str) -> str:
    return _wrap("bright_green", text)

def bright_yellow(text: str) -> str:
    return _wrap("bright_yellow", text)

def bright_blue(text: str) -> str:
    return _wrap("bright_blue", text)

def bright_red(text: str) -> str:
    return _wrap("bright_red", text)

def bright_white(text: str) -> str:
    return _wrap("bright_white", text)


# ──────────────────────────────────────────────────────────────────────
# Semantic helpers (use these in application code)
# ──────────────────────────────────────────────────────────────────────

def success(text: str) -> str:
    """Format text as a success message (green)."""
    return green(text)

def error(text: str) -> str:
    """Format text as an error message (red)."""
    return red(text)

def warning(text: str) -> str:
    """Format text as a warning message (yellow)."""
    return yellow(text)

def info(text: str) -> str:
    """Format text as an informational message (cyan)."""
    return cyan(text)

def header(text: str) -> str:
    """Format text as a section header (bold bright-cyan)."""
    if not _COLOR_ENABLED:
        return text
    return f"{_CODES['bold']}{_CODES['bright_cyan']}{text}{_CODES['reset']}"

def label(text: str) -> str:
    """Format text as a label (bold)."""
    return bold(text)

def muted(text: str) -> str:
    """Format text as secondary / muted (dim)."""
    return dim(text)


# ──────────────────────────────────────────────────────────────────────
# Progress bar helper
# ──────────────────────────────────────────────────────────────────────

def progress_bar(percent: float, width: int = 20) -> str:
    """Return a coloured progress bar string.

    Example: ``▓▓▓▓▓▓▓▓░░░░░░░░░░░░  40%``
    """
    filled = int(width * percent / 100)
    empty = width - filled

    if percent < 50:
        color = "green"
    elif percent < 80:
        color = "yellow"
    else:
        color = "red"

    bar = "▓" * filled + "░" * empty
    bar_str = _wrap(color, bar)
    pct_str = _wrap("bold", f"{percent:5.1f}%")
    return f"{bar_str} {pct_str}"
