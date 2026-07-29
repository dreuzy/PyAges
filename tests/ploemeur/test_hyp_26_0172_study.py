from pathlib import Path
import subprocess
import sys

from PIL import Image
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "sites" / "ploemeur" / "studies" / "HYP-26-0172" / "scripts"
POSTPROCESSING = SCRIPTS.parent / "postprocessing"
STUDY = SCRIPTS.parent


def test_study_matrix_validates():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_study.py")],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validated 13 experiments" in result.stdout


def test_run_matrix_is_dry_by_default():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_matrix.py"),
            "--select",
            "article_outputs=Figure6",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "regime_F38_exp_3cfc_err20_seed12345" in result.stdout
    assert "regime_PE_exp_3cfc_err20_seed12345" in result.stdout
    assert "[production, steps=configured]" in result.stdout


def test_submission_tiff_validator(tmp_path):
    for stem in ("Figure3", "Figure4", "Figure5", "Figure6", "FigureA1"):
        Image.new("RGB", (20, 20), "white").save(
            tmp_path / f"{stem}.tif",
            dpi=(600, 600),
            compression="tiff_lzw",
        )
    result = subprocess.run(
        [
            sys.executable,
            str(POSTPROCESSING / "validate_submission_figures.py"),
            "--directory",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validated 5 flattened 600-DPI TIFF figures" in result.stdout


def test_figure_contract_references_local_builders():
    contract = yaml.safe_load((STUDY / "figures.yaml").read_text(encoding="utf-8"))
    figures = contract["figures"]
    assert set(figures) == {
        "Figure2",
        "Figure3",
        "Figure4",
        "Figure5",
        "Figure6",
        "FigureA1",
        "FigureS1",
    }
    for specification in figures.values():
        assert (STUDY / specification["builder"]).is_file()
