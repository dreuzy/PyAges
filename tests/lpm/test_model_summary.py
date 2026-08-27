# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Text and diagnostic orchestration tests for LPM summaries."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from pyages.lpm import factory
from pyages.lpm.plotting import model_curves
from pyages.lpm.reporting import model_summary


def _model(**parameters):
    return SimpleNamespace(
        name="audit",
        p=parameters,
        parameter_units={name: "years" for name in parameters},
        moments_name=lambda: ["mean", "variance"],
        moments=lambda: [12.0, 4.0],
    )


def test_model_summary_respects_text_flag(capsys) -> None:
    model = _model(mu=12.0, shift=2.0)

    model_summary.print_model_summary(model, SimpleNamespace(text=False))
    assert capsys.readouterr().out == ""

    model_summary.print_model_summary(model, SimpleNamespace(text=True))
    output = capsys.readouterr().out
    assert "LPM type: audit" in output
    assert "mu" in output
    assert "12.0" in output
    assert "years" in output


def test_parameter_and_moment_summaries_render_expected_values(capsys) -> None:
    calibrated = _model(mu=12.0)
    reference = _model(mu=10.0)

    model_summary.print_parameter_comparison(calibrated)
    model_summary.print_parameter_comparison(calibrated, reference)
    model_summary.print_moment_summary(calibrated)

    output = capsys.readouterr().out
    assert "mu \t 12.00" in output
    assert "target  10.00" in output
    assert "calibrated 12.00" in output
    assert "difference rate 2.0e-01" in output
    assert "mean  12.0" in output
    assert "variance  4.0" in output


def test_run_model_diagnostic_dispatches_requested_outputs(monkeypatch) -> None:
    model = _model(mu=12.0)
    model.moments = Mock(return_value=[12.0, 4.0])
    plot = Mock()
    text = Mock()
    moments = Mock()
    monkeypatch.setattr(factory, "build_random_lpm", lambda name: model)
    monkeypatch.setattr(model_curves, "plot_pdf_cdf", plot)
    monkeypatch.setattr(model_summary, "print_model_summary", text)
    monkeypatch.setattr(model_summary, "print_moment_summary", moments)
    display = SimpleNamespace(figure=True, text=True)

    model_summary.run_model_diagnostic("audit", display)

    model.moments.assert_called_once_with()
    plot.assert_called_once_with(model, display)
    text.assert_called_once_with(model, display)
    moments.assert_called_once_with(model)
