from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import build_article_package as package
from scripts.common.mcmc_diagnostics import ess, mcse_mean, split_rhat
from scripts.common.reporting import markdown_table


def _summary():
    baseline = {
        "groups": 1,
        "max_split_rhat": 1.0,
        "min_ess": 1000.0,
        "all_converged": True,
    }
    return {
        "thresholds": {"split_rhat_lt": 1.01, "ess_gte": 300.0},
        "shifted_exponential": baseline,
        "holten_h4": baseline,
        "ploemeur_shifted_exponential": baseline,
        "ploemeur_physical_ig": {
            "posterior_sets": 1,
            "max_split_rhat": 1.0,
            "min_bulk_ess": 1000.0,
            "min_tail_ess": 1000.0,
            "all_converged": True,
            "article_nonregression_reproduced": True,
        },
    }


def test_shared_mcmc_diagnostics_distinguish_mixed_and_shifted_chains():
    rng = np.random.default_rng(12345)
    mixed = rng.normal(size=(4, 2000))
    shifted = mixed.copy()
    shifted[0] += 3.0

    assert split_rhat(mixed) < 1.01
    assert ess(mixed) > 1000
    assert split_rhat(shifted) > 1.1


def test_mcse_mean_uses_ess_and_preserves_constant_limit():
    values = np.asarray([1.0, 2.0, 3.0, 4.0])

    assert mcse_mean(values, 4.0) == pytest.approx(np.std(values, ddof=1) / 2.0)
    assert mcse_mean(np.ones(10), 3.0) == 0.0
    with pytest.raises(ValueError, match="effective_sample_size"):
        mcse_mean(values, 0.0)


def test_markdown_table_rounds_and_escapes_without_tabulate():
    frame = pd.DataFrame({"label": ["a|b"], "value": [1.234567]})

    rendered = markdown_table(frame, numeric_round=3)

    assert "a\\|b" in rendered
    assert "1.235" in rendered


def test_article_package_is_atomic_and_hash_validated(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("article result\n", encoding="utf-8")
    artifact = package.Artifact(
        "result",
        "report",
        source,
        Path("reports/result.txt"),
        "test result",
    )
    monkeypatch.setattr(package, "scientific_summary", _summary)
    monkeypatch.setattr(package, "_git", lambda *unused: "test-git-state")
    monkeypatch.setattr(package, "_execution_source_snapshots", lambda unused: ([], {}))
    output = tmp_path / "package"

    package.build_package(output, (artifact,))
    payload = package.validate_package(output)

    assert len(payload["artifacts"]) == 1
    assert (output / "README.md").is_file()
    assert (output / "CHECKSUMS.sha256").is_file()
    source.write_text("updated article result\n", encoding="utf-8")
    package.replace_package(output, (artifact,))
    assert (output / "reports" / "result.txt").read_text(encoding="utf-8") == (
        "updated article result\n"
    )
    (output / "reports" / "result.txt").write_text("corrupted\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash"):
        package.validate_package(output)
