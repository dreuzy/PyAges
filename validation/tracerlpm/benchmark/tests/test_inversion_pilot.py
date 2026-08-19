from pathlib import Path

import yaml

from validation.tracerlpm.benchmark.scripts.check_robustness_progress import check
from validation.tracerlpm.benchmark.scripts.generate_inversion_pilot import (
    expanded_cases,
    generate,
)
from validation.tracerlpm.benchmark.scripts.invert_pyage_pilot import invert


def test_emm_inversion_pilot_recovers_truth(tmp_path: Path):
    observations = tmp_path / "observations"
    first = generate(output_dir=observations)
    second = generate(output_dir=tmp_path / "observations-second")
    assert first["cases"][0]["sha256"] == second["cases"][0]["sha256"]

    result = invert(observation_dir=observations, result_dir=tmp_path / "results")[
        "cases"
    ][0]
    assert first["cases"][0]["row_count"] == 3
    assert result["optimizer_success"]
    assert result["attempt_count"] == 3
    assert result["tau_absolute_error"] < 0.5
    assert result["maximum_recalculated_relative_error"] < 0.01


def test_epm_inversion_pilot_recovers_both_parameters(tmp_path: Path):
    observations = tmp_path / "observations"
    generate(output_dir=observations)
    results = invert(observation_dir=observations, result_dir=tmp_path / "results")[
        "cases"
    ]
    result = next(item for item in results if item["model"] == "EPM")
    assert result["optimizer_success"]
    assert result["parameter_absolute_errors"]["tau"] < 2e-3
    assert result["parameter_absolute_errors"]["eta"] < 2e-3
    assert len(result["concentrations"]) == 3


def test_dm_inversion_pilot_recovers_both_parameters(tmp_path: Path):
    observations = tmp_path / "observations"
    generate(output_dir=observations)
    results = invert(observation_dir=observations, result_dir=tmp_path / "results")[
        "cases"
    ]
    result = next(item for item in results if item["model"] == "DM")
    assert result["optimizer_success"]
    assert result["parameter_absolute_errors"]["tau"] < 1e-3
    assert result["parameter_absolute_errors"]["DP"] < 1e-3
    assert len(result["concentrations"]) == 3


def test_noisy_observations_are_reproducible(tmp_path: Path):
    config = Path(
        "validation/tracerlpm/benchmark/configs/inversion-noisy-campaign.yaml"
    )
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    first, second = (
        generate(config_path=config, output_dir=first_dir),
        generate(config_path=config, output_dir=second_dir),
    )
    assert [case["sha256"] for case in first["cases"]] == [
        case["sha256"] for case in second["cases"]
    ]
    csv_text = (first_dir / "inversion-epm-tau20-r2-noise01-seed101.csv").read_text(
        encoding="utf-8"
    )
    assert "gaussian_relative" in csv_text
    assert "noise_realization_fraction" in csv_text


def test_monte_carlo_templates_expand_to_sixty_unique_cases():
    config = yaml.safe_load(
        Path(
            "validation/tracerlpm/benchmark/configs/inversion-monte-carlo-01.yaml"
        ).read_text(encoding="utf-8")
    )
    cases = expanded_cases(config)
    assert len(cases) == 60
    assert len({case["case_id"] for case in cases}) == 60
    assert {case["model"] for case in cases} == {"EPM", "DM"}


def test_sf6_monte_carlo_is_a_four_tracer_paired_campaign():
    config = yaml.safe_load(
        Path(
            "validation/tracerlpm/benchmark/configs/inversion-monte-carlo-01-sf6.yaml"
        ).read_text(encoding="utf-8")
    )
    assert [tracer["name"] for tracer in config["tracers"]] == [
        "cfc11",
        "cfc12",
        "cfc113",
        "sf6",
    ]
    cases = expanded_cases(config)
    assert len(cases) == 60
    assert {case["noise"]["seed"] for case in cases} == set(range(201, 231))


def test_robustness_matrices_expand_to_expected_unique_cases():
    width_config = yaml.safe_load(
        Path(
            "validation/tracerlpm/benchmark/configs/robustness-width-noise.yaml"
        ).read_text(encoding="utf-8")
    )
    age_config = yaml.safe_load(
        Path(
            "validation/tracerlpm/benchmark/configs/robustness-age-noise.yaml"
        ).read_text(encoding="utf-8")
    )
    width_cases = expanded_cases(width_config)
    age_cases = expanded_cases(age_config)
    assert len(width_cases) == 320
    assert len(age_cases) == 160
    assert len({case["case_id"] for case in width_cases + age_cases}) == 480
    assert {case["model"] for case in width_cases + age_cases} == {"EPM", "DM"}
    assert {case["noise"]["relative_standard_deviation"] for case in width_cases} == {
        0.01,
        0.05,
        0.10,
        0.20,
    }
    assert {case["true_parameters"]["tau"] for case in age_cases} == {5.0, 50.0}
    epm_widths = {
        case["true_parameters"]["eta"] - 1.0
        for case in width_cases
        if case["model"] == "EPM"
    }
    dm_widths = {
        case["true_parameters"]["DP"] for case in width_cases if case["model"] == "DM"
    }
    assert {round(value, 12) for value in epm_widths} == {0.05, 0.5, 2.0, 9.0}
    assert dm_widths == {0.02, 0.2, 0.5, 1.0}
    for config in (width_config, age_config):
        assert [tracer["name"] for tracer in config["tracers"]] == [
            "cfc11",
            "cfc12",
            "cfc113",
            "sf6",
        ]
        assert config["tracerlpm"]["target_tracers"] == [
            "CFC-11",
            "CFC-12",
            "CFC-113",
            "SF6",
        ]


def test_robustness_progress_declares_the_exact_expected_case_set():
    progress = check()
    assert progress["expected"] == 480
    assert progress["epm_present"] <= 240
    assert progress["dm_present"] <= 240
    assert progress["present"] + len(progress["missing"]) == 480
