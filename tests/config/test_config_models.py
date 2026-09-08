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
    MetropolisHastingsCfg,
    MHPilotCfg,
    SingleDateConfig,
    SingleDateDataCfg,
    SingleDateLpmCfg,
    SingleDateObjectiveCfg,
    SingleDateOutputCfg,
    SingleDateReachableCfg,
    SingleDateRunCfg,
    SingleDateSimplexCfg,
    TemporalCalibrationCfg,
    TemporalConfig,
    TemporalDataCfg,
    TemporalLpmCfg,
    TemporalOutputCfg,
    TemporalReportingCfg,
)
from pyages.lpm import list_available_lpms
from pyages.workflows.single_date.config import load_config_payload

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
    return {
        name: {} if field.default_factory is not None else field.default
        for name, field in model.model_fields.items()
    }


def _deep_update(target: dict, values: dict) -> None:
    """Merge nested documentation fragments without losing sibling sections."""
    for name, value in values.items():
        if isinstance(value, dict) and isinstance(target.get(name), dict):
            _deep_update(target[name], value)
        else:
            target[name] = value


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
        "examples/natural/ploemeur_temporal/_single_date_compare/"
        "exemple_ploemeur_ig_shifted.yaml",
        "examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date.yaml",
        "examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml",
    ],
)
def test_shipped_single_date_configs_are_strictly_valid(relative_path):
    path = ROOT / relative_path
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 3
    config = load_config_payload(path.parent, payload)

    assert (config.data.data_dir / config.data.name).is_file()
    assert (config.lpm.directory / config.lpm.models[0] / "params.yaml").is_file()


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

    assert payload["schema_version"] == 3
    config = TemporalConfig.model_validate(payload)

    dataset_path = Path(config.data.file)
    if not dataset_path.is_absolute():
        dataset_path = path.parent / dataset_path
    assert config.lpm.directory is not None
    lpm_directory = Path(config.lpm.directory)
    if not lpm_directory.is_absolute():
        lpm_directory = path.parent / lpm_directory
    assert dataset_path.is_file()
    assert config.lpm.models is not None
    assert all(
        (lpm_directory / model / "params.yaml").is_file() for model in config.lpm.models
    )


def test_workflow_discriminators_are_required_and_reject_crossed_modes():
    with pytest.raises(ValidationError, match="workflow"):
        SingleDateConfig.model_validate({})
    with pytest.raises(ValidationError, match="workflow"):
        TemporalConfig.model_validate({"data": {"file": "sample.txt"}})

    with pytest.raises(ValidationError, match="single_date"):
        SingleDateConfig.model_validate({"workflow": {"kind": "temporal"}})
    with pytest.raises(ValidationError, match="temporal"):
        TemporalConfig.model_validate(
            {
                "workflow": {"kind": "single_date"},
                "data": {"file": "sample.txt"},
            }
        )


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (SingleDateConfig, {"data": {}, "obsolete_option": True}),
        (
            SingleDateConfig,
            {"data": {"name": "sample.txt", "obsolete_option": True}},
        ),
        (SingleDateConfig, {"output": {"obsolete_option": True}}),
        (
            TemporalConfig,
            {"data": {"file": "sample.txt"}, "obsolete_option": True},
        ),
        (
            TemporalConfig,
            {"data": {"file": "sample.txt", "obsolete_option": True}},
        ),
    ],
)
def test_unknown_configuration_keys_are_rejected(model, payload):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(payload)


def test_documented_single_date_yaml_sections_form_a_valid_configuration():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    headings = (
        "### Workflow Section",
        "### Data Section",
        "### LPM Section",
        "### Tracer Data Override",
        "### Run Section",
        "### Reachable Concentrations Section",
        "### Objective Function Section",
        "### Metropolis-Hastings Section",
        "### Simplex Section",
        "### Output Section",
    )
    payload = {"schema_version": 3}
    for heading in headings:
        _deep_update(payload, _yaml_after_heading(document, heading))

    SingleDateConfig.model_validate(payload, context={"root_dir": ROOT})


def test_documented_temporal_yaml_sections_form_a_valid_configuration():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    temporal = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]
    headings = (
        "### Data Section",
        "### LPM Section",
        "### Workflow Section",
        "### Calibration Section",
        "### Reporting Section",
        "### Output Section",
    )
    payload = {"schema_version": 3}
    for heading in headings:
        _deep_update(payload, _yaml_after_heading(temporal, heading))

    TemporalConfig.model_validate(payload)


def test_documented_one_to_many_chain_yaml_is_strictly_valid() -> None:
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    payload = _yaml_after_heading(document, "### One-to-many-chain MH controls")

    MetropolisHastingsCfg.model_validate(payload["metropolis_hastings"])


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
        ("### Reachable Concentrations Section", SingleDateReachableCfg, False),
        ("### Objective Function Section", SingleDateObjectiveCfg, False),
        ("### Metropolis-Hastings Section", MetropolisHastingsCfg, False),
        ("### Simplex Section", SingleDateSimplexCfg, False),
        ("### Output Section", SingleDateOutputCfg, False),
        ("### Calibration Section", TemporalCalibrationCfg, True),
        ("### Reporting Section", TemporalReportingCfg, True),
        ("### Output Section", TemporalOutputCfg, True),
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
        ("### Data Section", SingleDateDataCfg, False),
        ("### Data Section", TemporalDataCfg, True),
        ("### LPM Section", TemporalLpmCfg, True),
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
    defaults = _model_defaults(SingleDateRunCfg)

    assert defaults
    assert all(value is True for value in defaults.values())


def test_mh_requires_at_least_one_retained_state() -> None:
    assert MetropolisHastingsCfg(nsteps=11).nsteps == 11
    with pytest.raises(ValidationError, match="at least one MH draw"):
        MetropolisHastingsCfg(nsteps=20, burn_in=0.9, thinning=100)
    with pytest.raises(ValidationError, match="at least one MH draw"):
        MetropolisHastingsCfg(nsteps=101, burn_in=0.4, thinning=1000)


def test_mh_seed_is_single_and_nullable() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        MetropolisHastingsCfg(seed=-1)

    assert MetropolisHastingsCfg(seed=0).seed == 0
    assert MetropolisHastingsCfg(seed=None).seed is None


def test_mh_configuration_uses_one_common_strict_surface() -> None:
    defaults = MetropolisHastingsCfg()
    assert defaults.chains == 1
    assert defaults.seed == 12345
    assert defaults.initialization.strategy == "bounds_stratified"
    assert defaults.pilot.enabled is False

    config = MetropolisHastingsCfg.model_validate(
        {
            "nsteps": 1000,
            "thinning": 1,
            "chains": 4,
            "seed": 42,
            "initialization": {"strategy": "bounds_stratified"},
            "pilot": {
                "enabled": True,
                "nsteps": 100,
                "proposal_multiplier": "auto",
            },
            "diagnostics": {
                "max_rhat": 1.01,
                "min_bulk_ess": 30,
                "min_tail_ess": 30,
            },
        }
    )

    assert config.chains == 4
    assert config.seed == 42
    assert config.pilot.proposal_multiplier == "auto"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MetropolisHastingsCfg(monitor=True)
    with pytest.raises(ValidationError, match="bounds_stratified"):
        MetropolisHastingsCfg(initialization={"strategy": "auto"})


def test_mh_configuration_rejects_boolean_seed() -> None:
    with pytest.raises(ValidationError, match="boolean"):
        MetropolisHastingsCfg(seed=True)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: MetropolisHastingsCfg(seed=True),
        lambda: MetropolisHastingsCfg(thinning=True),
        lambda: MetropolisHastingsCfg(chains=True),
        lambda: MetropolisHastingsCfg(initialization={"max_attempts": True}),
        lambda: MetropolisHastingsCfg(pilot={"nsteps": True}),
        lambda: MetropolisHastingsCfg(pilot={"burn_in": True}),
        lambda: MetropolisHastingsCfg(pilot={"relative_ridge": True}),
        lambda: MetropolisHastingsCfg(pilot={"proposal_multiplier": True}),
        lambda: MetropolisHastingsCfg(diagnostics={"max_rhat": True}),
        lambda: MetropolisHastingsCfg(diagnostics={"min_bulk_ess": True}),
        lambda: MetropolisHastingsCfg(nsteps=True),
    ],
)
def test_multichain_numeric_controls_reject_yaml_booleans(factory) -> None:
    with pytest.raises(ValidationError, match="boolean"):
        factory()


def test_explicit_initialization_rejects_boolean_parameter_values() -> None:
    with pytest.raises(ValidationError, match="boolean parameter values"):
        MetropolisHastingsCfg(
            nsteps=100,
            thinning=1,
            chains=2,
            diagnostics={"require_convergence": False},
            initialization={
                "strategy": "explicit",
                "explicit_starts": [{"mu": True}, {"mu": 2.0}],
            },
        )


def test_multichain_configuration_rejects_ambiguous_initialization() -> None:
    with pytest.raises(ValidationError, match="explicit_starts is required"):
        MetropolisHastingsCfg(initialization={"strategy": "explicit"})
    with pytest.raises(ValidationError, match="accepted only"):
        MetropolisHastingsCfg(
            initialization={
                "strategy": "bounds_stratified",
                "explicit_starts": [{"mu": 1.0}],
            }
        )
    assert MetropolisHastingsCfg(chains=1).chains == 1
    with pytest.raises(ValidationError, match="one state per chain"):
        MetropolisHastingsCfg(
            nsteps=100,
            thinning=1,
            chains=3,
            diagnostics={"require_convergence": False},
            initialization={
                "strategy": "explicit",
                "explicit_starts": [{"mu": 1.0}, {"mu": 2.0}],
            },
        )


def test_multichain_configuration_requires_enough_diagnostic_draws() -> None:
    one_chain = MetropolisHastingsCfg(
        nsteps=11,
        burn_in=0.2,
        thinning=10,
        chains=1,
    )
    assert one_chain.chains == 1

    with pytest.raises(ValidationError, match="at least eight draws"):
        MetropolisHastingsCfg(
            nsteps=20,
            burn_in=0.2,
            thinning=5,
            chains=4,
        )
    with pytest.raises(ValidationError, match="at least eight draws"):
        MetropolisHastingsCfg(
            nsteps=101,
            burn_in=0.2,
            thinning=20,
            chains=4,
        )
    with pytest.raises(ValidationError, match="maximum split-draw ESS"):
        MetropolisHastingsCfg(nsteps=200, chains=4)
    exploratory = MetropolisHastingsCfg(
        nsteps=200,
        chains=4,
        diagnostics={"require_convergence": False},
    )
    assert not exploratory.diagnostics.require_convergence
    monitored = MetropolisHastingsCfg(
        display_traj=True,
        chains=4,
        diagnostics={"require_convergence": False},
    )
    assert monitored.display_traj is True
    with pytest.raises(ValidationError, match="requires prior_option=true"):
        MetropolisHastingsCfg(
            prior_option=False,
            chains=4,
            initialization={"strategy": "prior_sample"},
        )


def test_pilot_configuration_requires_covariance_draws_and_finite_scale() -> None:
    with pytest.raises(ValidationError, match="two covariance draws"):
        MHPilotCfg(enabled=True, nsteps=4, burn_in=0.5)
    with pytest.raises(ValidationError, match="positive or 'auto'"):
        MHPilotCfg(proposal_multiplier=float("nan"))
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MHPilotCfg(covariance_mode="pooled_within_chain")


def test_temporal_relative_error_must_be_strictly_positive() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        TemporalDataCfg(file="observations.txt", error_rel=0.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        TemporalDataCfg(file="observations.txt", missing_error_rel=0.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        SingleDateDataCfg(missing_error_rel=0.0)


@pytest.mark.parametrize("models", [[], ["exp", ""], ["exp", "exp"]])
def test_temporal_explicit_model_list_must_be_unambiguous(models) -> None:
    with pytest.raises(ValidationError, match="lpm.models"):
        TemporalLpmCfg(models=models)


def test_temporal_lpm_models_rejects_the_removed_list_field() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TemporalLpmCfg.model_validate({"list": ["exp"]})


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (SingleDateDataCfg, {"name": "../observations.txt"}),
        (SingleDateDataCfg, {"name": "..\\observations.txt"}),
        (SingleDateDataCfg, {"name": "D:observations.txt"}),
        (SingleDateLpmCfg, {"models": ["../exp"]}),
        (TemporalLpmCfg, {"models": ["../exp"]}),
        (SingleDateOutputCfg, {"study_name": ".."}),
        (TemporalOutputCfg, {"study_name": ".."}),
    ],
)
def test_result_path_components_cannot_escape_their_parent(model, payload) -> None:
    with pytest.raises(ValidationError, match="single non-empty path component"):
        model.model_validate(payload)


@pytest.mark.parametrize("directory", [None, "", "   "])
def test_custom_temporal_results_require_a_directory(directory) -> None:
    with pytest.raises(ValidationError, match="output.directory must be set"):
        TemporalOutputCfg(use_default=False, directory=directory)


def test_single_date_results_defaults_and_relative_directory_are_resolved(
    tmp_path: Path,
) -> None:
    defaults = load_config_payload(
        tmp_path,
        {"schema_version": 3, "workflow": {"kind": "single_date"}},
    )

    assert defaults.output.use_default is True
    assert defaults.output.directory is None
    assert defaults.output.study_name == "test_cases"

    custom = load_config_payload(
        tmp_path,
        {
            "schema_version": 3,
            "workflow": {"kind": "single_date"},
            "output": {
                "use_default": False,
                "directory": "relative-results",
                "study_name": "profile_a",
            },
        },
    )

    assert custom.output.use_default is False
    assert custom.output.directory == tmp_path / "relative-results"
    assert custom.output.study_name == "profile_a"


@pytest.mark.parametrize("directory", [None, "", "   "])
def test_custom_single_date_results_require_a_directory(directory) -> None:
    with pytest.raises(ValidationError, match="output.directory must be set"):
        SingleDateOutputCfg(use_default=False, directory=directory)


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
        single = load_config_payload(
            single_path.parent,
            yaml.safe_load(single_path.read_text(encoding="utf-8")),
        )
        multichain = load_config_payload(
            multichain_path.parent,
            yaml.safe_load(multichain_path.read_text(encoding="utf-8")),
        )
        assert single.data.name == multichain.data.name
        assert single.output.study_name == "test_cases"
        assert multichain.output.study_name != single.output.study_name
        multichain_studies.add(multichain.output.study_name)

    assert len(multichain_studies) == 4


def test_all_documented_yaml_blocks_are_parseable():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\s*\n(.*?)```", document, flags=re.DOTALL)

    assert blocks
    for block in blocks:
        yaml.safe_load(block)
