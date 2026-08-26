"""Launch a full calculation in a fresh, timestamped result directory."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _fresh_output(case_id: str, under_robustness: bool = False) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    external_root = Path(
        os.environ.get(
            "PYAGE_ARTICLE_RESULTS_DIR", ROOT.parent / "pyage-article-results"
        )
    ).resolve()
    base = external_root / (
        "robustness/reproductions" if under_robustness else "article_reproductions"
    )
    output = base / case_id / stamp
    if output.exists():
        raise FileExistsError(f"Refusing to reuse full-run directory: {output}")
    return output


def _subprocess(script: str, case_id: str) -> int:
    output = _fresh_output(case_id)
    command = [sys.executable, script, "all", "--output", str(output)]
    print("Fresh full-run output:", output, flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case",
        choices=(
            "s3_1_tracerlpm",
            "s3_2_shifted_exponential",
            "s4_1_holten",
            "s4_2_ploemeur",
            "holten_prior_dirichlet1",
        ),
    )
    args = parser.parse_args()
    if args.case == "s3_1_tracerlpm":
        raise SystemExit(
            "A full s3_1_tracerlpm rerun is not yet portable: execute the "
            "external TracerLPM/Excel campaign described in "
            "validation/tracerlpm/README.md, then run `python "
            "article/run_case.py postprocess s3_1_tracerlpm`."
        )
    scripts = {
        "s3_2_shifted_exponential": "scripts/run_final_shifted_exponential.py",
        "s4_1_holten": "scripts/run_final_holten_h4.py",
        "s4_2_ploemeur": "scripts/run_ploemeur_shifted_exponential_final.py",
    }
    if args.case in scripts:
        return _subprocess(scripts[args.case], args.case)

    from scripts import run_holten_prior_robustness as runner

    output = _fresh_output(args.case, under_robustness=True)
    runner.OUTPUT = output
    print("Fresh full-run output:", output, flush=True)
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
