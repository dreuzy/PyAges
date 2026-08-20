"""Tests that LPM plotting saves output files when enabled."""

from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg", force=True)

from pyage.config.runtime import DisplayOptions
from pyage.lpm.lpm_build import test as lpm_test


@pytest.mark.parametrize("lpm_type", ["exp"])
def test_lpm_display_outputs(tmp_path: Path, lpm_type: str) -> None:
    display = DisplayOptions()
    display.figure = True
    display.figure_save = True
    display.figure_close = True
    display.text = False
    display.directory = tmp_path

    lpm_test(lpm_type, display)

    files = [f for f in tmp_path.iterdir() if f.is_file()]
    assert files, "Expected figure output files to be saved"
    assert any(lpm_type in f.name for f in files), "Expected LPM figure files"
    assert len(files) >= 2, "Expected at least two figures (pdf/cdf)"
