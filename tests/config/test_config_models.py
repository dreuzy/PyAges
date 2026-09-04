# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Strict contracts for user-facing YAML configuration models."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from pyages.config.models import (
    LauncherConfig,
    LauncherDatasetCfg,
    LauncherLpmCfg,
    LauncherMetropolisCfg,
    LauncherObjectiveCfg,
    LauncherReachableCfg,
    LauncherResultsCfg,
    LauncherRunCfg,
    LauncherSimplexCfg,
    MHMultichainCfg,
    MHPilotCfg,
    TemporalCalibrationCfg,
    TemporalDatasetCfg,
    TemporalFiguresCfg,
    TemporalLpmModelsCfg,
    TemporalParams,
    TemporalResultsCfg,
)
from pyages.lpm import list_available_lpms
from pyages.workflows.single_date.config import load_params_payload

ROOT = Path(__file__).resolve().parents[2]
CONFIGURATION_DOC = ROOT / "docs" / "user-guide" / "configuration.md"


def _yaml_after_heading(document: str, heading: str) -> dict:
    section = document.split(heading, maxsplit=1)[1]
    match = re.search(r"```yaml\s*\n(.*?)```", section, flags=re.DOTALL)
    assert match is not None, f"No YAML example found after {heading}"
    payload = yaml.safe_load(match.group(1))
    assert isinstance(payload, dict)
    return payload


def _defaults_after_heading(document: str, heading: str) -> dict:
    section = document.split(heading, maxsplit=1)[1].split("\n### ", maxsplit=1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("|")
    ]
    header = next(row for row in rows if row and row[0] == "Field")
    default_index = header.index("Default")
    defaults = {}
    for row in rows[2:]:
        if len(row) <= default_index:
            continue
        field = row[0].strip("`")
        raw = row[default_index].strip("`")
        defaults[field] = yaml.safe_load(raw)
    return defaults


def _model_defaults(model) -> dict:
    return {name: field.default for name, field in model.model_fields.items()}


def _required_after_heading(document: str, heading: str) -> dict[str, bool]:
    section = document.split(heading, maxsplit=1)[1].split("\n### ", maxsplit=1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("|")
    ]
    header = next(row for row in rows if row and row[0] == "Field")
    required_index = header.index("Required")
    required = {}
    for row in rows[2:]:
        if len(row) <= required_index:
            continue
        field = row[0].strip("`")
        required[field] = row[required_index].casefold() == "yes"
    return required


def _model_required(model) -> dict[str, bool]:
    return {name: field.is_required() for name, field in model.model_fields.items()}


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/templates/quickstart_single.yaml",
        "examples/templates/smoke_multichain.yaml",
        "examples/natural/albuquerque/exemple_albuquerque.yaml",
        "examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml",
        "examples/natural/albuquerque/exemple_albuquerque_shapefree_multichain.yaml",
        "examples/natural/ploemeur/exemple_ploemeur.yaml",
        "examples/natural/ploemeur/exemple_ploemeur_ig_shifted_prior_multichain.yaml",
        "examples/natural/ploemeur/exemple_ploemeur_multichain.yaml",
        "examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date.yaml",
        "examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml",
    ],
)
def test_shipped_single_date_configs_are_strictly_valid(relative_path):
    path = ROOT / relative_path
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    LauncherConfig.model_validate(payload, context={"root_dir": ROOT})


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/templates/quickstart_temporal.yaml",
        "examples/natural/ploemeur_temporal/ploemeur_temporal.yaml",
        "examples/natural/ploemeur_temporal/ploemeur_temporal_multichain.yaml",
    ],
)
def test_shipped_temporal_configs_are_strictly_valid(relative_path):
    path = ROOT / relative_path
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    TemporalParams.model_validate(payload)


def test_workflow_discriminators_have_safe_defaults_and_reject_crossed_modes():
    assert LauncherConfig().workflow.kind == "single_date"
    assert TemporalParams(dataset={"file": "sample.txt"}).workflow.kind == "temporal"

    with pytest.raises(ValidationError, match="single_date"):
        LauncherConfig.model_validate({"workflow": {"kind": "temporal"}})
    with pytest.raises(ValidationError, match="temporal"):
        TemporalParams.model_validate(
            {
                "workflow": {"kind": "single_date"},
                "dataset": {"file": "sample.txt"},
            }
        )


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (LauncherConfig, {"dataset": {}, "obsolete_option": True}),
        (
            LauncherConfig,
            {"dataset": {"name": "sample.txt", "obsolete_option": True}},
        ),
        (LauncherConfig, {"results": {"obsolete_option": True}}),
        (
            TemporalParams,
            {"dataset": {"file": "sample.txt"}, "obsolete_option": True},
        ),
        (
            TemporalParams,
            {"dataset": {"file": "sample.txt", "obsolete_option": True}},
        ),
    ],
)
def test_unknown_configuration_keys_are_rejected(model, payload):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(payload)


def test_documented_single_date_yaml_sections_form_a_valid_configuration():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    headings = (
        "### Dataset Section",
        "### LPM Section",
        "### Tracer Data Override",
        "### Run Section",
        "### Reachable Concentrations Section",
        "### Objective Function Section",
        "### Metropolis-Hastings Section",
        "### Simplex Section",
    )
    payload = {}
    for heading in headings:
        payload.update(_yaml_after_heading(document, heading))

    LauncherConfig.model_validate(payload, context={"root_dir": ROOT})


def test_documented_temporal_yaml_sections_form_a_valid_configuration():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    temporal = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]
    headings = (
        "### Dataset Section",
        "### LPM Models Section",
        "### Workflow Section",
        "### Calibration Section",
        "### Figures Section",
        "### Results Section",
    )
    payload = {}
    for heading in headings:
        payload.update(_yaml_after_heading(temporal, heading))

    TemporalParams.model_validate(payload)


def test_documented_multichain_yaml_is_strictly_valid() -> None:
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    payload = _yaml_after_heading(document, "### Optional Multi-chain MH Configuration")

    MHMultichainCfg.model_validate(payload["multichain"])


def test_documented_lpm_table_matches_runtime_registry():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    table = document.split("**Available LPM models:**", maxsplit=1)[1].split(
        "The model-specific meaning", maxsplit=1
    )[0]
    documented = set(re.findall(r"^\| `([^`]+)` \|", table, flags=re.MULTILINE))

    assert documented == set(list_available_lpms())


@pytest.mark.parametrize(
    ("heading", "model", "temporal_only"),
    [
        ("### Reachable Concentrations Section", LauncherReachableCfg, False),
        ("### Objective Function Section", LauncherObjectiveCfg, False),
        ("### Metropolis-Hastings Section", LauncherMetropolisCfg, False),
        ("### Simplex Section", LauncherSimplexCfg, False),
        ("### Calibration Section", TemporalCalibrationCfg, True),
        ("### Figures Section", TemporalFiguresCfg, True),
        ("### Results Section", TemporalResultsCfg, True),
    ],
)
def test_documented_default_tables_match_pydantic_models(heading, model, temporal_only):
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    if temporal_only:
        document = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]

    assert _defaults_after_heading(document, heading) == _model_defaults(model)


@pytest.mark.parametrize(
    ("heading", "model", "temporal_only"),
    [
        ("### Dataset Section", LauncherDatasetCfg, False),
        ("### LPM Section", LauncherLpmCfg, False),
        ("### Dataset Section", TemporalDatasetCfg, True),
        ("### LPM Models Section", TemporalLpmModelsCfg, True),
    ],
)
def test_documented_required_fields_match_pydantic_models(
    heading, model, temporal_only
):
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    if temporal_only:
        document = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]

    assert _required_after_heading(document, heading) == _model_required(model)


def test_documented_single_date_run_defaults_remain_all_enabled():
    defaults = _model_defaults(LauncherRunCfg)

    assert defaults
    assert all(value is True for value in defaults.values())


def test_single_date_mh_requires_at_least_one_retained_state() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 11"):
        LauncherMetropolisCfg(nstep=10)

    assert LauncherMetropolisCfg(nstep=11).nstep == 11
    with pytest.raises(ValidationError, match="at least one MH draw"):
        LauncherMetropolisCfg(nstep=20, burn_in=0.9, nskip=100)
    with pytest.raises(ValidationError, match="at least one MH draw"):
        TemporalCalibrationCfg(mh_nsteps=101, burn_in=0.4, nskip=1000)


def test_temporal_fixed_seed_requires_a_non_negative_value() -> None:
    with pytest.raises(ValidationError, match="seed is required"):
        TemporalCalibrationCfg(seed_enabled=True)
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        TemporalCalibrationCfg(seed_enabled=True, seed=-1)

    assert TemporalCalibrationCfg(seed_enabled=True, seed=0).seed == 0
    assert (
        TemporalCalibrationCfg(
            seed_enabled=True,
            multichain={"enabled": True},
        ).seed
        is None
    )


def test_multichain_configuration_is_presence_activated_and_strict() -> None:
    assert LauncherMetropolisCfg().multichain is None
    single_date = LauncherMetropolisCfg(multichain={})
    temporal = TemporalCalibrationCfg(multichain={})
    assert single_date.multichain is not None
    assert single_date.multichain.enabled is True
    assert temporal.multichain is not None
    assert temporal.multichain.enabled is True
    assert MHMultichainCfg(enabled=False).enabled is False

    config = MHMultichainCfg.model_validate(
        {
            "enabled": True,
            "chains": 4,
            "master_seed": 42,
            "initialization": {"strategy": "bounds_stratified"},
            "pilot": {"nstep": 100, "proposal_multiplier": "auto"},
            "diagnostics": {
                "max_rhat": 1.01,
                "min_bulk_ess": 300,
                "min_tail_ess": 300,
            },
        }
    )

    assert config.enabled is True
    assert config.chains == 4
    assert config.master_seed == 42
    assert config.pilot.proposal_multiplier == "auto"


def test_multichain_configuration_rejects_boolean_master_seed() -> None:
    with pytest.raises(ValidationError, match="master_seed"):
        MHMultichainCfg(master_seed=True)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LauncherMetropolisCfg(seed=True),
        lambda: LauncherMetropolisCfg(nskip=True),
        lambda: MHMultichainCfg(chains=True),
        lambda: MHMultichainCfg(initialization={"max_attempts": True}),
        lambda: MHMultichainCfg(pilot={"nstep": True}),
        lambda: MHMultichainCfg(pilot={"burn_in": True}),
        lambda: MHMultichainCfg(pilot={"relative_ridge": True}),
        lambda: MHMultichainCfg(pilot={"proposal_multiplier": True}),
        lambda: MHMultichainCfg(diagnostics={"max_rhat": True}),
        lambda: MHMultichainCfg(diagnostics={"min_bulk_ess": True}),
        lambda: TemporalCalibrationCfg(mh_nsteps=True),
        lambda: TemporalCalibrationCfg(seed=True),
    ],
)
def test_multichain_numeric_controls_reject_yaml_booleans(factory) -> None:
    with pytest.raises(ValidationError, match="boolean"):
        factory()


def test_explicit_initialization_rejects_boolean_parameter_values() -> None:
    with pytest.raises(ValidationError, match="boolean parameter values"):
        MHMultichainCfg(
            chains=2,
            initialization={
                "strategy": "explicit",
                "explicit_starts": [{"mu": True}, {"mu": 2.0}],
            },
        )


def test_multichain_configuration_rejects_ambiguous_initialization() -> None:
    with pytest.raises(ValidationError, match="explicit_starts is required"):
        MHMultichainCfg(initialization={"strategy": "explicit"})
    with pytest.raises(ValidationError, match="accepted only"):
        MHMultichainCfg(
            initialization={
                "strategy": "bounds_stratified",
                "explicit_starts": [{"mu": 1.0}],
            }
        )
    with pytest.raises(ValidationError, match="greater than or equal to 2"):
        MHMultichainCfg(chains=1)
    with pytest.raises(ValidationError, match="one state per chain"):
        MHMultichainCfg(
            chains=3,
            initialization={
                "strategy": "explicit",
                "explicit_starts": [{"mu": 1.0}, {"mu": 2.0}],
            },
        )


def test_multichain_configuration_requires_enough_diagnostic_draws() -> None:
    with pytest.raises(ValidationError, match="at least eight draws"):
        LauncherMetropolisCfg(
            nstep=20,
            burn_in=0.2,
            nskip=10,
            multichain={"enabled": True},
        )
    with pytest.raises(ValidationError, match="at least eight draws"):
        TemporalCalibrationCfg(
            mh_nsteps=101,
            burn_in=0.2,
            nskip=100,
            multichain={"enabled": True},
        )
    with pytest.raises(ValidationError, match="maximum split-draw ESS"):
        LauncherMetropolisCfg(nstep=200, multichain={"enabled": True})
    exploratory = LauncherMetropolisCfg(
        nstep=200,
        multichain={
            "enabled": True,
            "diagnostics": {"require_convergence": False},
        },
    )
    assert exploratory.multichain is not None
    assert not exploratory.multichain.diagnostics.require_convergence
    with pytest.raises(ValidationError, match="one-chain options"):
        LauncherMetropolisCfg(
            display_traj=True,
            multichain={"enabled": True},
        )
    with pytest.raises(ValidationError, match="require prior_option=true"):
        LauncherMetropolisCfg(
            prior_option=False,
            multichain={
                "enabled": True,
                "initialization": {"strategy": "prior_sample"},
            },
        )


def test_pilot_configuration_requires_covariance_draws_and_finite_scale() -> None:
    with pytest.raises(ValidationError, match="two covariance draws"):
        MHPilotCfg(nstep=4, burn_in=0.5)
    with pytest.raises(ValidationError, match="positive or 'auto'"):
        MHPilotCfg(proposal_multiplier=float("nan"))
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MHPilotCfg(covariance_mode="pooled_within_chain")


def test_temporal_relative_error_must_be_strictly_positive() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        TemporalDatasetCfg(file="observations.txt", error_rel=0.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        TemporalDatasetCfg(file="observations.txt", missing_error_rel=0.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        LauncherDatasetCfg(missing_error_rel=0.0)


@pytest.mark.parametrize("models", [[], ["exp", ""], ["exp", "exp"]])
def test_temporal_explicit_model_list_must_be_unambiguous(models) -> None:
    with pytest.raises(ValidationError, match="lpm_models.list"):
        TemporalLpmModelsCfg(list=models)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (LauncherDatasetCfg, {"name": "../observations.txt"}),
        (LauncherDatasetCfg, {"name": "..\\observations.txt"}),
        (LauncherDatasetCfg, {"name": "D:observations.txt"}),
        (LauncherLpmCfg, {"model_name": "../exp"}),
        (TemporalLpmModelsCfg, {"list": ["../exp"]}),
        (LauncherResultsCfg, {"study_name": ".."}),
        (TemporalResultsCfg, {"study_name": ".."}),
    ],
)
def test_result_path_components_cannot_escape_their_parent(model, payload) -> None:
    with pytest.raises(ValidationError, match="single non-empty path component"):
        model.model_validate(payload)


@pytest.mark.parametrize("directory", [None, "", "   "])
def test_custom_temporal_results_require_a_directory(directory) -> None:
    with pytest.raises(ValidationError, match="results.directory must be set"):
        TemporalResultsCfg(use_default=False, directory=directory)


def test_single_date_results_defaults_and_relative_directory_are_propagated(
    tmp_path: Path,
) -> None:
    defaults = load_params_payload(tmp_path, {})

    assert defaults.results_use_default is True
    assert defaults.results_directory is None
    assert defaults.results_study_name == "test_cases"

    custom = load_params_payload(
        tmp_path,
        {
            "results": {
                "use_default": False,
                "directory": "relative-results",
                "study_name": "profile_a",
            }
        },
    )

    assert custom.results_use_default is False
    assert custom.results_directory == tmp_path / "relative-results"
    assert custom.results_study_name == "profile_a"


@pytest.mark.parametrize("directory", [None, "", "   "])
def test_custom_single_date_results_require_a_directory(directory) -> None:
    with pytest.raises(ValidationError, match="results.directory must be set"):
        LauncherResultsCfg(use_default=False, directory=directory)


def test_multichain_example_profiles_isolate_existing_datasets() -> None:
    profile_pairs = [
        (
            ROOT / "examples/synthetic/lpm_recovery_single_date/"
            "lpm_recovery_single_date.yaml",
            ROOT / "examples/synthetic/lpm_recovery_single_date/"
            "lpm_recovery_single_date_multichain.yaml",
        ),
        (
            ROOT / "examples/natural/ploemeur/exemple_ploemeur.yaml",
            ROOT / "examples/natural/ploemeur/exemple_ploemeur_multichain.yaml",
        ),
        (
            ROOT / "examples/natural/ploemeur/exemple_ploemeur.yaml",
            ROOT / "examples/natural/ploemeur/"
            "exemple_ploemeur_ig_shifted_prior_multichain.yaml",
        ),
        (
            ROOT / "examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml",
            ROOT / "examples/natural/albuquerque/"
            "exemple_albuquerque_shapefree_multichain.yaml",
        ),
    ]
    multichain_studies = set()
    for single_path, multichain_path in profile_pairs:
        single = LauncherConfig.model_validate(
            yaml.safe_load(single_path.read_text(encoding="utf-8")),
            context={"root_dir": ROOT},
        )
        multichain = LauncherConfig.model_validate(
            yaml.safe_load(multichain_path.read_text(encoding="utf-8")),
            context={"root_dir": ROOT},
        )
        assert single.dataset.name == multichain.dataset.name
        assert single.results.study_name == "test_cases"
        assert multichain.results.study_name != single.results.study_name
        multichain_studies.add(multichain.results.study_name)

    assert len(multichain_studies) == 4


def test_all_documented_yaml_blocks_are_parseable():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\s*\n(.*?)```", document, flags=re.DOTALL)

    assert blocks
    for block in blocks:
        yaml.safe_load(block)
