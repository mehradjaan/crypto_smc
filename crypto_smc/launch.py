#!/usr/bin/env python3
"""Windows/mac/Linux launcher for SmartFlow. Called by start.bat."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "smartflow_start.log"


def log(msg: str) -> None:
    print(msg, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def wait() -> None:
    try:
        input("\nPress Enter to close this window...")
    except EOFError:
        time.sleep(8)


def main() -> int:
    os.chdir(ROOT)
    try:
        LOG.write_text("", encoding="utf-8")
    except OSError:
        pass

    log("=== SmartFlow ===")
    log(f"Folder: {ROOT}")
    log(f"Python: {sys.executable}")
    log(f"Version: {sys.version}")

    if not (ROOT / "app.py").exists():
        log("ERROR: app.py not found.")
        log("Put start.bat and launch.py inside the crypto_smc folder.")
        wait()
        return 1

    log("Installing / updating packages ...")
    pip_code = subprocess.call(
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    )
    if pip_code != 0:
        log("ERROR: pip install failed. Check your internet connection.")
        wait()
        return pip_code

    def _open_browser() -> None:
        time.sleep(2.5)
        url = "http://127.0.0.1:8000"
        log(f"Opening browser: {url}")
        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001
            log(f"Could not open browser automatically: {exc}")

    threading.Thread(target=_open_browser, daemon=True).start()
    log("Server: http://127.0.0.1:8000")
    log("Keep this window open. Close it to stop the server.")
    log("")

    code = subprocess.call([sys.executable, str(ROOT / "app.py")])
    log(f"Server exited with code {code}")
    if code != 0:
        wait()
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print("ERROR:", exc)
        wait()
        sys.exit(1)
