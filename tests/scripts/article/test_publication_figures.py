# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Rendering-only tests for the manuscript publication figures."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.container import ErrorbarContainer
from matplotlib.text import Text
from PIL import Image

from scripts.article import postprocess_existing
from scripts.article import run_final_holten_h4 as holten
from scripts.article import run_final_shifted_exponential as shifted
from scripts.article import run_holten_prior_robustness as prior
from scripts.article import run_ploemeur_shifted_exponential_final as ploemeur
from scripts.common.publication_plotting import (
    PUBLICATION_RC,
    assert_minimum_text_size,
    mm_to_in,
    save_pdf_png,
)


def _capture_exports(monkeypatch, module):
    exports = []

    def capture(figure, output, stem, **unused):
        assert_minimum_text_size(figure)
        exports.append(
            {
                "stem": stem,
                "size": figure.get_size_inches().copy(),
                "texts": [text.get_text() for text in figure.findobj(match=Text)],
                "labels": [axis.get_xlabel() for axis in figure.axes]
                + [axis.get_ylabel() for axis in figure.axes],
                "figure": figure,
            }
        )
        return output / f"{stem}.pdf", output / f"{stem}.png"

    monkeypatch.setattr(module, "save_pdf_png", capture)
    return exports


def _holten_comparison() -> pd.DataFrame:
    rows = []
    wells = ("59-05", "67-19", "72-22", "73-29", "85-33", "85-34", "85-35")
    for well_index, well in enumerate(wells):
        for fraction_index, fraction in enumerate(holten.BIN_ORDER):
            median = 0.08 + 0.025 * well_index + 0.02 * fraction_index
            rows.append(
                {
                    "well": well,
                    "fraction": fraction,
                    "pyages_median": median,
                    "pyages_q10": median - 0.02,
                    "pyages_q90": median + 0.02,
                    "visser": median + 0.005,
                }
            )
    return pd.DataFrame(rows)


def _prior_comparison() -> pd.DataFrame:
    frame = _holten_comparison().drop(
        columns=["pyages_median", "pyages_q10", "pyages_q90", "visser"]
    )
    values = np.linspace(0.08, 0.82, len(frame))
    for prefix, offset in (("reference", 0.0), ("dirichlet", 0.01)):
        frame[f"{prefix}_median"] = values + offset
        frame[f"{prefix}_q10"] = values + offset - 0.015
        frame[f"{prefix}_q90"] = values + offset + 0.015
    return frame


def _posterior_summaries(comparison: pd.DataFrame, prefix: str) -> pd.DataFrame:
    return comparison.rename(
        columns={
            "fraction": "parameter",
            f"{prefix}_median": "median",
            f"{prefix}_q10": "q10",
            f"{prefix}_q90": "q90",
        }
    )[["well", "parameter", "median", "q10", "q90"]]


def test_publication_export_preserves_physical_size_dpi_and_truetype_fonts(tmp_path):
    with plt.rc_context(PUBLICATION_RC):
        figure, axis = plt.subplots(figsize=(mm_to_in(50), mm_to_in(30)))
        axis.plot([0.0, 1.0], [0.0, 1.0])
        axis.set_xlabel("Readable label")
        pdf_path, png_path = save_pdf_png(figure, tmp_path, "publication_probe")
        plt.close(figure)

    with Image.open(png_path) as image:
        assert image.size[0] == pytest.approx(round(mm_to_in(50) * 600), abs=1)
        assert image.info["dpi"][0] == pytest.approx(600, abs=1)
    pdf = pdf_path.read_bytes()
    assert pdf.startswith(b"%PDF")
    assert b"/FontFile2" in pdf


def test_figure2_exports_canonical_width_and_two_editorial_alternatives(
    monkeypatch, tmp_path
):
    exports = _capture_exports(monkeypatch, shifted)
    surface = pd.DataFrame(
        [[3.0, 2.0], [2.0, 1.0]],
        index=pd.Index([0.0, 50.0], name="shift"),
        columns=pd.Index([0.0, 50.0], name="mu"),
    )
    posterior = pd.DataFrame({"mu": [9.5, 10.0], "t0": [30.5, 30.0]})

    shifted._render_figure2(surface, posterior, tmp_path)

    by_stem = {item["stem"]: item for item in exports}
    assert set(by_stem) == {
        "figure2_shifted_exponential_120mm",
        "figure2_shifted_exponential_100mm",
        "figure2_shifted_exponential_final",
    }
    for stem, width in (
        ("figure2_shifted_exponential_100mm", 100),
        ("figure2_shifted_exponential_final", 110),
        ("figure2_shifted_exponential_120mm", 120),
    ):
        actual = by_stem[stem]["size"][0]
        assert actual == pytest.approx(width / 25.4)
    all_labels = " ".join(by_stem["figure2_shifted_exponential_final"]["labels"])
    assert "Exponential timescale" in all_labels
    assert "Shift" in all_labels


def test_figure3_exports_preferred_and_fallback_layouts(monkeypatch, tmp_path):
    exports = _capture_exports(monkeypatch, holten)

    holten._figure3(_holten_comparison(), tmp_path)

    assert [item["stem"] for item in exports] == [
        "figure3_holten_final",
        "figure3_holten_alt_2x2",
    ]
    final = exports[0]
    assert final["size"][0] == pytest.approx(165 / 25.4)
    combined = " ".join(final["texts"] + final["labels"])
    assert "(a) 0–20 yr" in combined
    assert "(d) >60 yr" in combined
    assert "Age fraction" in combined
    assert "H4" not in combined
    assert "q10" not in combined


def test_prior_sensitivity_matches_figure3_template(monkeypatch, tmp_path):
    exports = _capture_exports(monkeypatch, prior)
    comparison = _prior_comparison()

    prior.make_figure(
        tmp_path,
        comparison,
        reference_summaries=_posterior_summaries(comparison, "reference"),
        dirichlet_summaries=_posterior_summaries(comparison, "dirichlet"),
    )

    assert [item["stem"] for item in exports] == ["figureC1_holten_prior_sensitivity"]
    export = exports[0]
    figure = export["figure"]
    combined = " ".join(export["texts"] + export["labels"])
    assert export["size"] == pytest.approx(
        np.array([prior.FIGURE_C1_WIDTH_MM, prior.FIGURE_C1_HEIGHT_MM]) / 25.4
    )
    assert len(figure.axes) == 4
    assert [axis.get_title() for axis in figure.axes] == list(
        prior.FIGURE_C1_PANEL_TITLES
    )
    assert [label.get_text() for label in figure.axes[0].get_yticklabels()] == [
        "59-05",
        "67-19",
        "72-22",
        "73-29",
        "85-33",
        "85-34",
        "85-35",
    ]
    for axis in figure.axes:
        assert axis.get_xlim() == pytest.approx((0.0, 1.0))
        assert axis.get_xticks() == pytest.approx((0.0, 0.5, 1.0))
        assert all(line.get_visible() for line in axis.get_xgridlines())
        assert not any(line.get_visible() for line in axis.get_ygridlines())
        intervals = [
            container
            for container in axis.containers
            if isinstance(container, ErrorbarContainer)
        ]
        assert len(intervals) == 14
        assert {container.lines[0].get_marker() for container in intervals} == {
            "o",
            "D",
        }
    assert figure._suptitle is None
    assert figure._supxlabel.get_text() == "Age fraction"
    assert all(not axis.get_xlabel() for axis in figure.axes)
    assert "H4" not in combined
    assert "q10" not in combined
    assert "Latent-uniform prior" in combined
    assert "Dirichlet(1,1,1,1) prior" in combined
    assert "Sensitivity of Holten posterior age fractions" not in combined
    assert "Posterior median and" not in combined


def test_prior_sensitivity_rejects_a_value_not_in_posterior_summaries(tmp_path):
    comparison = _prior_comparison()
    reference = _posterior_summaries(comparison, "reference")
    dirichlet = _posterior_summaries(comparison, "dirichlet")
    comparison.loc[0, "reference_median"] += 0.001

    with pytest.raises(ValueError, match="does not match its final posterior"):
        prior.make_figure(
            tmp_path,
            comparison,
            reference_summaries=reference,
            dirichlet_summaries=dirichlet,
        )


@pytest.mark.parametrize("mutation", ["missing", "wrong_order"])
def test_prior_sensitivity_rejects_incomplete_or_reordered_points(tmp_path, mutation):
    comparison = _prior_comparison()
    reference = _posterior_summaries(comparison, "reference")
    dirichlet = _posterior_summaries(comparison, "dirichlet")
    if mutation == "missing":
        comparison = comparison.iloc[:-1]
    else:
        comparison = comparison.iloc[::-1]

    with pytest.raises(ValueError, match="exactly the configured Holten"):
        prior.make_figure(
            tmp_path,
            comparison,
            reference_summaries=reference,
            dirichlet_summaries=dirichlet,
        )


def test_figure4_uses_six_panels_and_only_calibration_terminology(
    monkeypatch, tmp_path
):
    exports = _capture_exports(monkeypatch, ploemeur)
    observations = pd.DataFrame(
        [
            {"element": tracer, "date": year, "concentration": value}
            for tracer_index, tracer in enumerate(ploemeur.TRACERS)
            for year, value in ((2014.5, 20.0 + tracer_index), (2020.0, 18.0))
        ]
    )
    paths = {}
    for well in ("F09", "F11"):
        path = tmp_path / f"{well}.txt"
        observations.to_csv(path, sep="\t", index=False)
        paths[well] = path
    monkeypatch.setattr(ploemeur, "_observation_path", paths.__getitem__)
    monkeypatch.setattr(ploemeur, "INSERTION_OUTPUT", tmp_path / "insertion")
    monkeypatch.setattr(ploemeur.shutil, "copy2", lambda *unused: None)
    intervals = pd.DataFrame(
        [
            {
                "well": well,
                "tracer": tracer,
                "calibration": calibration,
                "date": year,
                "median": 20.0,
                "q10": 18.0,
                "q90": 22.0,
            }
            for well in ("F11", "F09")
            for tracer in ploemeur.TRACERS
            for calibration in ("full_record", "2014_2015_independent")
            for year in (1990.0, 2025.0)
        ]
    )

    ploemeur._render_figure4(tmp_path, intervals)

    assert [item["stem"] for item in exports] == ["figure4_ploemeur_final"]
    final = exports[0]
    assert final["size"][0] == pytest.approx(165 / 25.4)
    combined = " ".join(final["texts"] + final["labels"])
    for panel in "abcdef":
        assert f"({panel})" in combined
    assert "Sampling year" in combined
    assert "Atmospheric-equivalent mixing ratio (pptv)" in combined
    assert "2014–2015-only calibration" in combined
    assert "Independent 2014" not in combined


def test_postprocessor_resolves_external_campaign_root(monkeypatch, tmp_path):
    selected = []
    monkeypatch.setattr(postprocess_existing, "shifted", selected.append)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "postprocess_existing.py",
            "s3_2_shifted_exponential",
            "--campaign-root",
            str(tmp_path),
        ],
    )

    assert postprocess_existing.main() == 0
    assert selected == [(tmp_path / "shifted_exponential").resolve()]


def test_figure1_source_declares_readable_sans_serif_typography():
    source = (
        Path(__file__).resolve().parents[3] / "docs" / "figures" / "figure1_overview.md"
    ).read_text(encoding="utf-8")

    assert '"fontFamily": "Arial, Helvetica, sans-serif"' in source
    assert '"fontSize": "18px"' in source
