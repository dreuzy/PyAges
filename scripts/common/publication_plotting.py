# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Shared publication-figure sizing, typography, and export helpers."""

from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.text import Text

PUBLICATION_RC = {
    "font.family": "sans-serif",
    "font.size": 9.0,
    "axes.labelsize": 9.0,
    "axes.titlesize": 9.0,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
}


def mm_to_in(mm: float) -> float:
    """Convert millimetres to inches for Matplotlib physical sizing."""

    return mm / 25.4


def assert_minimum_text_size(figure: Figure, minimum: float = 8.5) -> None:
    """Reject a figure containing visible, non-empty text below ``minimum`` pt."""

    undersized = sorted(
        {
            (text.get_text(), float(text.get_fontsize()))
            for text in figure.findobj(match=Text)
            if text.get_visible()
            and text.get_text().strip()
            and float(text.get_fontsize()) < minimum
        },
        key=lambda item: (item[1], item[0]),
    )
    if undersized:
        details = ", ".join(f"{label!r} ({size:g} pt)" for label, size in undersized)
        raise ValueError(f"Figure contains text below {minimum:g} pt: {details}")


def save_pdf_png(
    figure: Figure,
    output_directory: Path,
    stem: str,
    *,
    dpi: int = 600,
) -> tuple[Path, Path]:
    """Save exact-size PDF and 600-dpi PNG publication outputs."""

    output_directory.mkdir(parents=True, exist_ok=True)
    figure.canvas.draw()
    assert_minimum_text_size(figure)
    pdf_path = output_directory / f"{stem}.pdf"
    png_path = output_directory / f"{stem}.png"
    options = {"facecolor": "white", "bbox_inches": None}
    figure.savefig(pdf_path, dpi=dpi, **options)
    figure.savefig(png_path, dpi=dpi, **options)
    return pdf_path, png_path
