# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build the HYP-26-0172 observation-only Figures 2 and S1."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .plot_cfc11_vs_cfc12 import make_figure

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
SUBMISSION_DIRECTORY = REPOSITORY_ROOT / "results" / "HYP-26-0172" / "figures"
SOURCE_F11 = SUBMISSION_DIRECTORY / "Figure_F11_atmospheric_inputs.tif"
SOURCE_F09 = SUBMISSION_DIRECTORY / "Figure_F09_atmospheric_inputs.tif"


def _load_flattened_rgb(path: Path) -> tuple[Image.Image, tuple[float, float]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as source:
        dpi = source.info.get("dpi", (0.0, 0.0))
        if min(dpi) < 599.5:
            raise ValueError(f"{path.name} is only {dpi} DPI; expected 600 DPI")
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError(f"{path.name} is not a single flattened frame")
        return source.convert("RGB"), dpi


def build_figure2() -> Path:
    """Stack the native three-panel F11 and F09 bands without resampling."""
    f11, dpi_f11 = _load_flattened_rgb(SOURCE_F11)
    f09, dpi_f09 = _load_flattened_rgb(SOURCE_F09)
    if f11.width != f09.width:
        raise ValueError(
            f"Figure 2 bands have different widths: {f11.width}, {f09.width}"
        )
    if tuple(round(value) for value in dpi_f11) != tuple(
        round(value) for value in dpi_f09
    ):
        raise ValueError(
            f"Figure 2 bands have different resolutions: {dpi_f11}, {dpi_f09}"
        )

    # A small white gutter separates the two rows while retaining every source
    # pixel. F11 is the top row and F09 the bottom row, matching the manuscript.
    gutter = 120
    composite = Image.new("RGB", (f11.width, f11.height + gutter + f09.height), "white")
    composite.paste(f11, (0, 0))
    composite.paste(f09, (0, f11.height + gutter))
    output = SUBMISSION_DIRECTORY / "Figure2.tif"
    composite.save(output, dpi=(600, 600), compression="tiff_lzw")
    preview = composite.copy()
    preview.thumbnail((2700, 2700))
    preview.save(SUBMISSION_DIRECTORY / "Figure2_preview.png", dpi=(150, 150))
    return output


def build_figure_s1() -> Path:
    """Regenerate the F11/F09 tracer–tracer diagram from source data."""
    _, _, generated = make_figure(include_f09=True)
    output = SUBMISSION_DIRECTORY / "FigureS1.tif"
    with Image.open(generated) as source:
        source.convert("RGB").save(output, dpi=(600, 600), compression="tiff_lzw")
    return output


def main() -> None:
    SUBMISSION_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for output in (build_figure2(), build_figure_s1()):
        print(output)


if __name__ == "__main__":
    main()
