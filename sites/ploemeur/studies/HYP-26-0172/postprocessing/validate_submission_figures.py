"""Validate journal-ready TIFF figures against Hydrological Processes rules."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DIRECTORY = REPO_ROOT / "results" / "HYP-26-0172" / "figures"
REQUIRED_STEMS = {"Figure3", "Figure4", "Figure5", "Figure6", "FigureA1"}


def validate(directory: Path) -> list[str]:
    errors: list[str] = []
    found = {path.stem for path in directory.glob("*.tif")}
    missing = REQUIRED_STEMS - found
    if missing:
        errors.append(f"missing TIFF figures: {sorted(missing)}")
    for path in sorted(directory.glob("*.tif")):
        with Image.open(path) as image:
            dpi = image.info.get("dpi", (0, 0))
            if min(dpi) < 599.5:
                errors.append(f"{path.name}: resolution is {dpi}, expected 600 DPI")
            if image.mode != "RGB":
                errors.append(f"{path.name}: mode is {image.mode}, expected flattened RGB")
            if "A" in image.getbands():
                errors.append(f"{path.name}: contains an alpha channel")
            if getattr(image, "n_frames", 1) != 1:
                errors.append(f"{path.name}: contains {image.n_frames} frames")
            if image.info.get("compression") != "tiff_lzw":
                errors.append(f"{path.name}: compression is {image.info.get('compression')}, expected tiff_lzw")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    errors = validate(args.directory)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {len(list(args.directory.glob('*.tif')))} flattened 600-DPI TIFF figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
