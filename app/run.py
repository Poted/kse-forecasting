"""Polecenie `kse-app`: uruchamia dashboard Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path

DASHBOARD = Path(__file__).with_name("dashboard.py")


def main() -> None:
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(DASHBOARD), "--server.headless", "true", *sys.argv[1:]]
    sys.exit(stcli.main())
