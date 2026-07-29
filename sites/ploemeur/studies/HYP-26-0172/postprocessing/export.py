"""Publication export policy for HYP-26-0172 figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image


def export_figure(fig: plt.Figure, directory: Path, stem: str) -> list[Path]:
    """Write review and journal formats from the same Matplotlib figure."""
    directory.mkdir(parents=True, exist_ok=True)
    png_path = directory / f"{stem}.png"
    pdf_path = directory / f"{stem}.pdf"
    tif_path = directory / f"{stem}.tif"
    fig.savefig(
        png_path,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    fig.savefig(
        pdf_path,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    fig.savefig(
        tif_path,
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
        pil_kwargs={"compression": "tiff_lzw"},
    )
    plt.close(fig)

    # Guarantee the journal artifact is a single flattened RGB frame.
    with Image.open(tif_path) as image:
        image.convert("RGB").save(
            tif_path,
            dpi=(600, 600),
            compression="tiff_lzw",
        )
    return [png_path, pdf_path, tif_path]
