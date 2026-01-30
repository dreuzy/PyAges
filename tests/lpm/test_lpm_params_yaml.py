"""
Validation tests for LPM params.yaml files.

Checks presence of required fields and basic consistency across all models.
"""

from pathlib import Path

import pytest
import yaml

from tests.utils import paths as test_paths


def _lpm_data_dir() -> Path:
    return test_paths.repo_root() / "data_core" / "data_lpm"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.mark.parametrize("model_dir", sorted(_lpm_data_dir().iterdir()))
def test_params_yaml_schema(model_dir: Path):
    if not model_dir.is_dir():
        pytest.skip("Not a directory")

    params_path = model_dir / "params.yaml"
    if not params_path.exists():
        pytest.fail(f"Missing params.yaml in {model_dir}")

    data = _load_yaml(params_path)
    assert data.get("model") == model_dir.name
    assert "parameters" in data
    params = data["parameters"]
    assert isinstance(params, list) and len(params) > 0

    for param in params:
        assert "name" in param
        assert "bounds" in param and len(param["bounds"]) == 2
        assert "init" in param
        assert "step" in param
        prior = param.get("prior")
        assert prior and "type" in prior
