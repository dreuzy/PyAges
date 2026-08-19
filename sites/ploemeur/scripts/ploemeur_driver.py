"""Command-line entrypoint for the Ploemeur workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from sites.ploemeur.config.models import PloemeurDriverConfig
from sites.ploemeur.site_api import PloemeurSite


def _load_driver_config(params_path: str | None) -> PloemeurDriverConfig:
    data = {"params": params_path} if params_path else {}
    try:
        return PloemeurDriverConfig.model_validate(data)
    except ValidationError as exc:
        raise SystemExit(f"Invalid Ploemeur driver configuration:\n{exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--params",
        help="Repository-relative or absolute workflow YAML path.",
    )
    args = parser.parse_args()
    config = _load_driver_config(args.params)
    PloemeurSite().run(Path(config.params))


if __name__ == "__main__":
    main()
