from __future__ import annotations

from app.cli import app
from app.utils.logging import configure_utf8_output

if __name__ == "__main__":
    configure_utf8_output()
    app()
