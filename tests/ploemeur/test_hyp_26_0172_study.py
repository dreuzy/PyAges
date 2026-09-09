# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import subprocess
import sys
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "sites" / "ploemeur" / "studies" / "HYP-26-0172" / "scripts"
POSTPROCESSING = SCRIPTS.parent / "postprocessing"
STUDY = SCRIPTS.parent
MODULE_ROOT = "sites.ploemeur.studies.HYP-26-0172"
RUN_ALL = import_module(f"{MODULE_ROOT}.scripts.run_all")
RUN_MATRIX = import_module(f"{MODULE_ROOT}.scripts.run_matrix")
STUDY_COMMON = import_module(f"{MODULE_ROOT}.scripts.study_common")
PRODUCT_EXTRACTION = import_module(f"{MODULE_ROOT}.postprocessing.product_extraction")


def test_study_matrix_validates():
    result = subprocess.run(
        [sys.executable, "-m", f"{MODULE_ROOT}.scripts.validate_study"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validated 10 experiments" in result.stdout


def test_study_configs_enable_managed_multichain_convergence():
    for row in STUDY_COMMON.load_matrix():
        params = STUDY_COMMON.load_yaml(
            STUDY_COMMON.resolve_repo_path(row["params_path"])
        )
        mh = params["calibration"]["metropolis_hastings"]
        assert mh["nsteps"] == 40_000
        assert mh["chains"] == 4
        assert mh["pilot"]["enabled"] is True
        assert mh["pilot"]["nsteps"] == 2_000
        assert mh["diagnostics"] == {
            "max_rhat": 1.01,
            "min_bulk_ess": 300,
            "min_tail_ess": 300,
            "require_convergence": True,
        }


def test_smoke_profile_keeps_diagnostics_but_allows_exploratory_pooling(
    monkeypatch, tmp_path
):
    row = STUDY_COMMON.load_matrix()[0]
    monkeypatch.setattr(RUN_MATRIX, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        RUN_MATRIX, "profile_results_root", lambda profile: tmp_path / "results"
    )
    monkeypatch.setattr(RUN_MATRIX, "checksums", lambda paths: {})
    monkeypatch.setattr(RUN_MATRIX, "git_value", lambda *args: "test")
    monkeypatch.setattr(
        RUN_MATRIX.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="", returncode=0),
    )

    run_dir, _, manifest = RUN_MATRIX.prepare_run(row, False, "smoke", 100)
    resolved = yaml.safe_load(
        (run_dir / "resolved_config.yaml").read_text(encoding="utf-8")
    )
    mh = resolved["calibration"]["metropolis_hastings"]

    assert mh["nsteps"] == 100
    assert mh["thinning"] == 1
    assert mh["chains"] == 4
    assert mh["pilot"]["nsteps"] == 100
    assert mh["diagnostics"]["require_convergence"] is False
    assert manifest["nsteps"] == 100
    assert manifest["chains"] == 4
    assert manifest["require_convergence"] is False


def test_run_matrix_is_dry_by_default():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            f"{MODULE_ROOT}.scripts.run_matrix",
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


def test_run_matrix_accepts_isolated_profile():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            f"{MODULE_ROOT}.scripts.run_matrix",
            "--experiment-id",
            "main_F09_exp_ig_3cfc_err20_seed12345",
            "--profile",
            "cdf_v2",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[cdf_v2, steps=configured]" in result.stdout


def test_run_matrix_rejects_unsafe_profile():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            f"{MODULE_ROOT}.scripts.run_matrix",
            "--profile",
            "../outside",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0


def test_run_matrix_rejects_removed_mh_nsteps_alias():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            f"{MODULE_ROOT}.scripts.run_matrix",
            "--mh-nsteps",
            "100",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "unrecognized arguments: --mh-nsteps 100" in result.stderr


def test_run_all_sequences_simulation_postprocessing_and_validation(monkeypatch):
    commands = []

    def record(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(RUN_ALL.subprocess, "run", record)
    assert RUN_ALL.run_pipeline(profile="smoke", max_workers=1) == 0

    modules = [command[2] for command, _ in commands]
    assert modules == [
        f"{MODULE_ROOT}.scripts.validate_study",
        f"{MODULE_ROOT}.scripts.supervise_runs",
        f"{MODULE_ROOT}.postprocessing.build_products",
        f"{MODULE_ROOT}.postprocessing.validate_submission_figures",
    ]
    assert commands[1][0][-4:] == ["--profile", "smoke", "--max-workers", "1"]
    assert commands[2][0][-2:] == ["--profile", "smoke"]
    assert commands[3][0][-2] == "--directory"
    assert Path(commands[3][0][-1]) == (
        RUN_ALL.profile_results_root("smoke") / "figures"
    )
    assert all(
        kwargs == {"cwd": RUN_ALL.REPO_ROOT, "check": False} for _, kwargs in commands
    )


def test_run_all_stops_at_first_failed_stage(monkeypatch):
    return_codes = iter((0, 7, 0, 0))
    commands = []

    def fail_simulations(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=next(return_codes))

    monkeypatch.setattr(RUN_ALL.subprocess, "run", fail_simulations)
    assert RUN_ALL.run_pipeline(profile="production", max_workers=2) == 7
    assert len(commands) == 2


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
            "-m",
            f"{MODULE_ROOT}.postprocessing.validate_submission_figures",
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


def test_product_extraction_summarizes_managed_mcmc_diagnostics(tmp_path):
    method = (
        tmp_path
        / "runs"
        / "experiment"
        / "workflow"
        / "ploemeur_0.2successive"
        / "2026-01-01"
        / "F11_2018_2019"
        / "exp_shifted"
        / "Metropolis_Hastings"
    )
    method.mkdir(parents=True)
    (method / "results_calibration.txt").write_text(
        "qualification_status\tqualified\nchain_count\t4\nmean_acceptance_rate\t0.31\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "parameter": ["mu", "shift"],
            "rhat": [1.004, 1.008],
            "bulk_ess": [450.0, 420.0],
            "tail_ess": [390.0, 370.0],
            "mcse_mean": [0.12, 0.08],
            "posterior_sd": [2.0, 1.0],
            "included_in_qualification": [True, True],
            "qualified": [True, True],
        }
    ).to_csv(method / "mcmc_diagnostics.tsv", sep="\t", index=False)
    pd.DataFrame({"p50": [10.0], "mean": [11.0]}).to_csv(
        method / "distributions_stats.txt", sep="\t", index=False
    )

    path = PRODUCT_EXTRACTION.collect_diagnostics(tmp_path, tmp_path / "derived")
    row = pd.read_csv(path).iloc[0]

    assert row["qualification_status"] == "qualified"
    assert row["chain_count"] == 4
    assert row["mean_acceptance_rate"] == 0.31
    assert "success_rate" not in row.index
    assert row["max_rhat"] == 1.008
    assert row["min_bulk_ess"] == 420.0
    assert row["min_tail_ess"] == 370.0
    assert row["max_mcse_mean"] == 0.12
    assert bool(row["diagnostics_qualified"])
    assert bool(row["finite_posterior"])


def test_product_extraction_rejects_legacy_acceptance_schema(tmp_path):
    method = (
        tmp_path
        / "runs"
        / "legacy"
        / "workflow"
        / "scenario"
        / "date"
        / "case"
        / "exp_shifted"
        / "Metropolis_Hastings"
    )
    method.mkdir(parents=True)
    (method / "results_calibration.txt").write_text(
        "time_perform\t1.5\nsuccess_rate\t0.27\n", encoding="utf-8"
    )
    pd.DataFrame({"p50": [10.0]}).to_csv(
        method / "distributions_stats.txt", sep="\t", index=False
    )

    with pytest.raises(
        ValueError, match="does not follow the current MH result schema"
    ):
        PRODUCT_EXTRACTION.collect_diagnostics(tmp_path, tmp_path / "derived")


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
