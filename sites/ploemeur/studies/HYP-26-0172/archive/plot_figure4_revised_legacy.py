"""Legacy Figure 4 builder retained to document the pre-matrix workflow.

New figures must be built from durable derived tables with
``postprocessing/build_products.py``. This script deliberately remains able to
read the historical result folders so an old analysis can still be audited.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import pandas as pd
from PIL import Image


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_F11_ROOT = REPOSITORY_ROOT / "results" / "figure3_F11_10000"
DEFAULT_F09_ROOT = REPOSITORY_ROOT / "results" / "figure3_F09_10000"
DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "results" / "HYP-26-0172" / "legacy_figures"
)

COLOR_CONDITIONED = "blue"
COLOR_UNCONSTRAINED = "red"
COLOR_FULL_SERIES = "0.6"


def _latest_stats_file(results_root: Path, scenario: str) -> Path:
    """Return the newest shifted-exponential summary for one scenario."""
    matches = list(
        (results_root / scenario).glob("*/exp_shifted_stats_quantiles.txt")
    )
    if not matches:
        raise FileNotFoundError(
            f"No exp_shifted_stats_quantiles.txt found under "
            f"{results_root / scenario}"
        )
    return max(matches, key=lambda path: path.stat().st_mtime)


def load_figure4_statistics(results_root: Path) -> dict[str, pd.DataFrame]:
    """Load only the three existing numerical summaries used by Figure 4."""
    files = {
        "full_series": _latest_stats_file(
            results_root, "ploemeur_apriori_double_0.2span_full"
        ),
        "conditioned": _latest_stats_file(
            results_root,
            "ploemeur_apriori_double_0.2successive_with_prior",
        ),
        "unconstrained": _latest_stats_file(
            results_root, "ploemeur_0.2successive"
        ),
    }
    return {
        name: pd.read_csv(path, sep=None, engine="python")
        for name, path in files.items()
    }


def _plot_panel(
    ax: plt.Axes,
    statistics: dict[str, pd.DataFrame],
    title: str,
    show_legend: bool,
) -> None:
    """Plot one well without changing any stored value or uncertainty."""
    full_series = statistics["full_series"]
    conditioned = statistics["conditioned"]
    unconstrained = statistics["unconstrained"]

    # Preserve the historical tracer_stat convention: the second span_full
    # row supplies the full-series median and standard deviation.
    full_row = full_series.iloc[1] if len(full_series) >= 2 else full_series.iloc[0]
    median = float(full_row["median_mean"])
    std = float(full_row["median_std"])
    dates = [2004, 2026]

    ax.fill_between(
        dates,
        [median - std, median - std],
        [median + std, median + std],
        color=COLOR_FULL_SERIES,
        alpha=0.3,
    )
    ax.plot(dates, [median, median], color=COLOR_FULL_SERIES, linewidth=2)

    ax.errorbar(
        conditioned["date"],
        conditioned["median_mean"],
        yerr=conditioned["median_std"],
        fmt="o",
        color=COLOR_CONDITIONED,
        ecolor=COLOR_CONDITIONED,
        elinewidth=2,
        capsize=5,
        markersize=8,
    )
    ax.errorbar(
        unconstrained["date"],
        unconstrained["median_mean"],
        yerr=unconstrained["median_std"],
        fmt="o",
        color=COLOR_UNCONSTRAINED,
        ecolor=COLOR_UNCONSTRAINED,
        elinewidth=2,
        capsize=5,
        markersize=8,
    )

    ax.set_title(title, loc="left", fontsize=13, fontweight="bold")
    ax.set_xlim(2004, 2026)
    ax.set_xticks([2008, 2013, 2019, 2024])
    ax.tick_params(axis="both", labelsize=10)
    ax.grid(True, alpha=0.25)

    if show_legend:
        handles = [
            Patch(
                facecolor=COLOR_FULL_SERIES,
                edgecolor="none",
                alpha=0.3,
                label="Full series",
            ),
            Line2D(
                [], [], marker="o", linestyle="none",
                color=COLOR_CONDITIONED, label="Conditioned",
            ),
            Line2D(
                [], [], marker="o", linestyle="none",
                color=COLOR_UNCONSTRAINED, label="Unconstrained",
            ),
        ]
        ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=10)


def make_figure4(
    f11_root: Path = DEFAULT_F11_ROOT,
    f09_root: Path = DEFAULT_F09_ROOT,
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
) -> tuple[Path, Path, Path]:
    """Create and export the revised article Figure 4."""
    f11_statistics = load_figure4_statistics(f11_root)
    f09_statistics = load_figure4_statistics(f09_root)

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        sharex=True,
        figsize=(8, 7),
        constrained_layout=True,
    )
    _plot_panel(axes[0], f11_statistics, "(a) F11", show_legend=False)
    _plot_panel(axes[1], f09_statistics, "(b) F09", show_legend=True)
    axes[0].set_xlabel("")
    axes[1].set_xlabel("Date", fontsize=12)
    axes[1].tick_params(axis="x", labelbottom=True)
    fig.supylabel("Median transit time (years)", fontsize=12)

    output_directory.mkdir(parents=True, exist_ok=True)
    png_path = output_directory / "Figure4_revised.png"
    pdf_path = output_directory / "Figure4_revised.pdf"
    tif_path = output_directory / "Figure4_revised.tif"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(
        tif_path,
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
        pil_kwargs={"compression": "tiff_lzw"},
    )
    plt.close(fig)

    # Remove the alpha channel explicitly: the journal requests a flattened
    # TIFF rather than a layered/transparent image.
    with Image.open(tif_path) as tif_image:
        flattened = tif_image.convert("RGB")
        flattened.save(tif_path, dpi=(600, 600), compression="tiff_lzw")
    return pdf_path, png_path, tif_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--f11-root", type=Path, default=DEFAULT_F11_ROOT)
    parser.add_argument("--f09-root", type=Path, default=DEFAULT_F09_ROOT)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    args = parser.parse_args()

    for output in make_figure4(args.f11_root, args.f09_root, args.output_directory):
        print(output)


if __name__ == "__main__":
    main()
