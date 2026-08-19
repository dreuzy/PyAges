"""Plot the HYP-26-0172 CFC-11/CFC-12 observation diagram."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image

from pyage.config.paths import DIRECTORY_TRACER_DATA
from pyage.observations.loader import load_observation_concentrations
from pyage.tracer.tracer_root import Tracer
from sites.ploemeur.observations.ploemeur import ploemeur_ori_folder


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "results" / "HYP-26-0172" / "figures" / "supporting_information"
)
MIXING_YEARS = [1970, 1980, 1990, 2000]
ATMOSPHERIC_LABEL_YEARS = [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 12,
        "axes.labelsize": 13,
        "axes.titlesize": 14,
        "axes.linewidth": 1.0,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 10,
    }
)


def load_cfc_pairs(well: str, date_range: str) -> pd.DataFrame:
    """Load and pair measured CFC-11 and CFC-12 values by sampling date."""
    concentrations = load_observation_concentrations(
        ploemeur_ori_folder(REPOSITORY_ROOT),
        "ori_ploemeur_",
        well,
        date_range,
    )
    table = concentrations.cv.copy()
    table = table[table["element"].isin(["cfc11", "cfc12"])]
    units = table.groupby("element")["unit"].unique().to_dict()
    if any(len(values) != 1 for values in units.values()):
        raise ValueError(f"Inconsistent measurement units for {well}: {units}")

    # Each row is retained; cumcount prevents duplicate sampling dates from
    # being collapsed or averaged during the tracer pairing.
    table["replicate"] = table.groupby(["date", "element"]).cumcount()
    pairs = table.pivot(
        index=["date", "replicate"], columns="element", values="concentration"
    )
    pairs = pairs.dropna(subset=["cfc11", "cfc12"]).reset_index()
    pairs["sampling_year"] = pairs["date"]
    pairs.attrs["units"] = units
    return pairs


def atmospheric_trajectory() -> tuple[pd.DataFrame, str]:
    """Evaluate both LPM atmospheric input functions on common annual dates."""
    cfc11 = Tracer(DIRECTORY_TRACER_DATA, name="cfc11")
    cfc12 = Tracer(DIRECTORY_TRACER_DATA, name="cfc12")
    if cfc11.unit != cfc12.unit:
        raise ValueError(f"Atmospheric units differ: {cfc11.unit}, {cfc12.unit}")

    first_year = int(np.ceil(max(cfc11.datemin, cfc12.datemin)))
    last_year = int(np.floor(min(cfc11.datemax, cfc12.datemax)))
    years = np.arange(first_year, last_year + 1, dtype=float)
    trajectory = pd.DataFrame(
        {
            "year": years.astype(int),
            "cfc12": cfc12.get_concentration(years, np.zeros_like(years)),
            "cfc11": cfc11.get_concentration(years, np.zeros_like(years)),
        }
    )
    return trajectory, cfc11.unit


def make_figure(include_f09: bool = False) -> tuple[Path, Path, Path]:
    f11 = load_cfc_pairs("F11", "2004_2024")
    f09 = load_cfc_pairs("F09", "2005_2024") if include_f09 else None
    atmosphere, atmospheric_unit = atmospheric_trajectory()
    measurement_units = {
        str(value) for values in f11.attrs["units"].values() for value in values
    }
    # Historical normalized files encode the unit as 0; the raw source and
    # tracer metadata identify these atmospheric-equivalent values as pptv.
    if measurement_units not in ({"0"}, {"pptv"}) or atmospheric_unit != "pptv":
        raise ValueError(
            f"Unexpected units: measurements={measurement_units}, atmosphere={atmospheric_unit}"
        )

    fig, ax = plt.subplots(figsize=(7.2, 6.0), constrained_layout=True)
    ax.plot(
        atmosphere["cfc12"],
        atmosphere["cfc11"],
        color="black",
        linewidth=1.8,
        label="Atmospheric input trajectory",
        zorder=2,
    )

    for year in MIXING_YEARS:
        row = atmosphere.loc[atmosphere["year"] == year]
        if row.empty:
            continue
        x_end, y_end = float(row.iloc[0]["cfc12"]), float(row.iloc[0]["cfc11"])
        ax.plot(
            [0.0, x_end],
            [0.0, y_end],
            color="0.55",
            linestyle="--",
            linewidth=0.9,
            zorder=1,
        )
        ax.annotate(
            str(year),
            (x_end, y_end),
            xytext=(4, -8),
            textcoords="offset points",
            fontsize=9,
            color="0.35",
        )

    for year in ATMOSPHERIC_LABEL_YEARS:
        row = atmosphere.loc[atmosphere["year"] == year]
        if row.empty:
            continue
        x_atm, y_atm = float(row.iloc[0]["cfc12"]), float(row.iloc[0]["cfc11"])
        ax.plot(x_atm, y_atm, "o", ms=3.2, color="black", zorder=3)
        if year not in MIXING_YEARS:
            ax.annotate(
                str(year),
                (x_atm, y_atm),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=8,
            )

    if f09 is not None:
        ax.scatter(
            f09["cfc12"],
            f09["cfc11"],
            s=68,
            marker="D",
            facecolors="#f4a261",
            edgecolors="0.2",
            linewidths=0.9,
            alpha=0.9,
            label="F09",
            zorder=3,
        )

    points = ax.scatter(
        f11["cfc12"],
        f11["cfc11"],
        c=f11["sampling_year"],
        cmap="viridis",
        s=58,
        edgecolors="white",
        linewidths=0.6,
        zorder=4,
    )
    colorbar = fig.colorbar(points, ax=ax, pad=0.02)
    colorbar.set_label("Sampling year")

    handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            markersize=7,
            markerfacecolor="#2a788e",
            markeredgecolor="white",
            label="F11 measurements",
        ),
        Line2D(
            [], [], color="black", linewidth=1.8, label="Atmospheric input trajectory"
        ),
        Line2D(
            [],
            [],
            color="0.55",
            linestyle="--",
            linewidth=0.9,
            label="Mixing trajectories",
        ),
    ]
    if include_f09:
        handles.append(
            Line2D(
                [],
                [],
                marker="D",
                linestyle="none",
                markersize=7,
                markerfacecolor="#f4a261",
                markeredgecolor="0.2",
                label="F09",
            )
        )
    ax.legend(handles=handles, loc="best", frameon=False)
    ax.set_xlabel("Atmospheric-equivalent CFC-12 mixing ratio (pptv)")
    ax.set_ylabel("Atmospheric-equivalent CFC-11 mixing ratio (pptv)")
    ax.set_title("F11", fontweight="bold")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.tick_params(direction="out", width=1.0)

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stem = "F11_F09_CFC11_vs_CFC12" if include_f09 else "F11_CFC11_vs_CFC12"
    png_path = OUTPUT_DIRECTORY / f"{stem}.png"
    pdf_path = OUTPUT_DIRECTORY / f"{stem}.pdf"
    tif_path = OUTPUT_DIRECTORY / f"{stem}.tif"
    fig.savefig(
        png_path, dpi=300, bbox_inches="tight", facecolor="white", transparent=False
    )
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white", transparent=False)
    fig.savefig(
        tif_path,
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
        pil_kwargs={"compression": "tiff_lzw"},
    )
    plt.close(fig)
    with Image.open(tif_path) as image:
        image.convert("RGB").save(
            tif_path,
            dpi=(600, 600),
            compression="tiff_lzw",
        )
    return png_path, pdf_path, tif_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-f09",
        action="store_true",
        help="also create the F11 + F09 reference version",
    )
    args = parser.parse_args()

    outputs = list(make_figure(include_f09=False))
    if args.include_f09:
        outputs.extend(make_figure(include_f09=True))
    f11 = load_cfc_pairs("F11", "2004_2024")
    print(f"F11 paired observations: {len(f11)}")
    print(
        "F11 sampling dates (decimal years): "
        + ", ".join(f"{date:.9f}" for date in f11["date"])
    )
    print("Mixing years: " + ", ".join(map(str, MIXING_YEARS)))
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
