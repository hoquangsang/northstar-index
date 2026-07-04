from __future__ import annotations

import sys
from io import TextIOWrapper

from rich.console import Console

console = Console()


def configure_utf8_output() -> None:
    """Use UTF-8 for CLI output on Windows terminals with a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
