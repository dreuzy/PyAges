from __future__ import annotations

from examples.natural.holten.holten_benchmark import (
    build_pre_model_figures,
    build_reference_comparison_figures,
    write_benchmark_summary,
)
from examples.natural.holten.holten_case import build_context, load_yaml, write_well_launcher_config
from examples.natural.holten.run_holten import write_prepared_artifacts
from scripts.common.launcher_params import load_params
from tests.examples.holten_test_support import (
    EXPECTED_PRE_MODEL_FIGURES,
    EXPECTED_SELECTED_WELLS,
    holten_sandbox,
    local_4bin_outputs,
    prepared_holten_case,
    reference_comparison,
)


def test_holten_context_smoke(holten_sandbox):
    context = build_context(holten_sandbox["config_path"])

    assert context.paths.example_dir == holten_sandbox["example_dir"]
    assert context.params.dataset_name == "holten_2010_selected_wells.txt"
    assert context.params.lpm_model_name == "uniform"
    assert context.paths.data_dir == context.params.dataset_data_dir
    assert context.paths.lpm_data_dir == context.params.directory_lpm
    assert context.tracer_source_dirs["3H"] == holten_sandbox["example_dir"] / "tracers" / "3H"
    assert context.tracer_source_dirs["kr85"] == holten_sandbox["example_dir"] / "tracers" / "kr85"
    assert context.tracer_source_dirs["39Ar"] == holten_sandbox["repo_root"] / "data_core" / "data_tracer" / "39Ar"
    assert context.selected_wells == EXPECTED_SELECTED_WELLS
    assert context.calibration_tracers == ["3H", "kr85", "39Ar"]
    assert context.launcher_inline is False
    assert context.paths.reference_results_path.exists()


def test_holten_prepare_smoke(prepared_holten_case):
    prepared = prepared_holten_case

    assert prepared.context.selected_wells == EXPECTED_SELECTED_WELLS
    assert prepared.observed_aggregated.shape == (21, 6)
    assert prepared.preparation_log.shape == (21, 8)
    assert prepared.helium_diagnostics.shape == (7, 18)
    assert set(prepared.observed_by_well) == set(EXPECTED_SELECTED_WELLS)
    assert prepared.context.paths.aggregated_dataset_path.exists()

    for well_id in EXPECTED_SELECTED_WELLS:
        assert (prepared.context.paths.data_dir / f"holten_2010_{well_id}.txt").exists()

    for tracer_name in prepared.context.calibration_tracers:
        tracer_dir = prepared.context.paths.prepared_tracer_dir / tracer_name
        assert (tracer_dir / f"{tracer_name}.yaml").exists()
        if tracer_name in {"3H", "kr85"}:
            assert (tracer_dir / "recharge.csv").exists()
        else:
            assert not (tracer_dir / "recharge.csv").exists()


def test_generated_launcher_yaml_uses_prepared_tracer_directory(prepared_holten_case):
    prepared = prepared_holten_case
    config_path = write_well_launcher_config(prepared.context, prepared.context.selected_wells[0])
    params = load_params(prepared.context.paths.repo_root, config_path)

    assert params.tracer_data_dir == prepared.context.paths.prepared_tracer_dir


def test_prepared_case_subset_returns_filtered_clone(prepared_holten_case):
    subset = prepared_holten_case.subset(["67-19", "85-33"])

    assert subset is not prepared_holten_case
    assert subset.context.selected_wells == ["67-19", "85-33"]
    assert set(subset.observed_by_well) == {"67-19", "85-33"}
    assert subset.observed_aggregated["well_id"].isin({"67-19", "85-33"}).all()
    assert prepared_holten_case.context.selected_wells == EXPECTED_SELECTED_WELLS


def test_prepared_tracer_yaml_keeps_metadata(prepared_holten_case):
    prepared = prepared_holten_case
    for tracer_name in prepared.context.calibration_tracers:
        payload = load_yaml(prepared.context.paths.prepared_tracer_dir / tracer_name / f"{tracer_name}.yaml")
        assert "holten" in payload
        assert "source" in payload["holten"]


def test_holten_pre_model_figures_smoke(prepared_holten_case, tmp_path):
    output_dir = tmp_path / "pre_model"
    generated = build_pre_model_figures(prepared_holten_case, output_dir)

    assert {path.name for path in generated} == EXPECTED_PRE_MODEL_FIGURES
    assert all(path.exists() for path in generated)


def test_holten_benchmark_artifacts_smoke(
    prepared_holten_case,
    local_4bin_outputs,
    reference_comparison,
    tmp_path,
):
    benchmark_root = tmp_path / "benchmark"
    write_prepared_artifacts(prepared_holten_case, benchmark_root)

    prepared_dir = benchmark_root / "prepared"
    assert (prepared_dir / "preparation_log.txt").exists()
    assert (prepared_dir / "holten_2010_selected_wells.txt").exists()
    assert (prepared_dir / "helium_diagnostics.txt").exists()

    figures = build_reference_comparison_figures(
        prepared_holten_case,
        reference_comparison,
        benchmark_root / "comparison",
    )
    csv_path, txt_path = write_benchmark_summary(reference_comparison, benchmark_root / "comparison")

    assert set(figures) == {"local_vs_reference_4bin_chi2", "published_model_scores"}
    assert all(path.exists() for path in figures.values())
    assert csv_path.exists()
    assert txt_path.exists()
    assert local_4bin_outputs["paths"]["summary"].exists()
