"""Wait for production simulations, then build all derived products and figures."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
RESULTS_ROOT = REPO_ROOT / "results" / "HYP-26-0172"
STATUS_PATH = RESULTS_ROOT / "supervisor_status.json"
FINALIZER_STATUS = RESULTS_ROOT / "finalizer_status.json"


def write_status(state: str, **extra) -> None:
    value = {"state": state, "updated_at_utc": datetime.now(timezone.utc).isoformat(), **extra}
    FINALIZER_STATUS.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    write_status("waiting", supervisor_status=str(STATUS_PATH.relative_to(REPO_ROOT)))
    while True:
        if STATUS_PATH.is_file():
            status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            state = status.get("state")
            if state == "completed":
                break
            if state == "completed_with_failures":
                write_status("blocked", reason="one or more production experiments failed")
                return 1
        time.sleep(60)
    write_status("building")
    command = [
        sys.executable,
        str(REPO_ROOT / "sites" / "ploemeur" / "studies" / "HYP-26-0172" / "postprocessing" / "build_products.py"),
        "--profile", "production",
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    write_status("completed" if result.returncode == 0 else "failed", return_code=result.returncode)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
