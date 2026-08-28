# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for the plain-text LPM result writer."""

from __future__ import annotations

from io import StringIO

import pytest

from pyages.data_io.lpm_results import write_lpm
from pyages.lpm import build_lpm


def test_write_lpm_accepts_an_open_text_stream() -> None:
    model = build_lpm("exp")
    stream = StringIO()

    write_lpm(model, stream)

    assert stream.getvalue() == f"lpm\texp\nmu\t{model.p['mu']}\tyear\n"


def test_write_lpm_detects_a_path_and_creates_its_parent(tmp_path) -> None:
    model = build_lpm("exp")
    target = tmp_path / "nested" / "model.txt"

    write_lpm(model, target)

    assert target.read_text(encoding="utf-8") == (
        f"lpm\texp\nmu\t{model.p['mu']}\tyear\n"
    )


def test_write_lpm_rejects_an_unknown_target_type() -> None:
    model = build_lpm("exp")

    with pytest.raises(TypeError, match="writable text stream"):
        write_lpm(model, object())
