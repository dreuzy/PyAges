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
        "pyage_tracerlpm": {
            "paired_cases": 480,
            "pyage_successful": 480,
            "tracerlpm_successful": 480,
        },
        "forward_verification": {
            "case_count": 270,
            "status": "measured_not_yet_qualified",
        },
        "shifted_exponential": baseline,
        "holten_h4": baseline,
        "ploemeur_shifted_exponential": baseline,
        "ploemeur_physical_ig": {
            "posterior_sets": 1,
            "max_split_rhat": 1.0,
            "min_bulk_ess": 1000.0,
            "min_tail_ess": 1000.0,
            "all_converged": True,
            "stabilized_campaign_converged": True,
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


def test_publication_package_uses_current_table4_names():
    table_artifacts = {
        artifact.identifier: artifact
        for artifact in package.ARTIFACTS
        if artifact.identifier.startswith("table4_")
    }

    assert set(table_artifacts) == {"table4_csv", "table4_markdown"}
    assert table_artifacts["table4_csv"].source.name == "table4_final.csv"
    assert table_artifacts["table4_csv"].destination == Path("tables/table4.csv")
    assert table_artifacts["table4_markdown"].source.name == "table4_final.md"
    assert table_artifacts["table4_markdown"].destination == Path("tables/table4.md")
    assert all(
        "Table 4" in artifact.description for artifact in table_artifacts.values()
    )

    readme = package._readme(_summary())
    assert "| Table 4 | `tables/table4.md` | `tables/table4.csv` |" in readme
    assert "table3_final" not in readme


def test_shifted_exponential_production_text_uses_current_table_number():
    runner = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_final_shifted_exponential.py"
    ).read_text(encoding="utf-8")
    postprocessor = (
        Path(__file__).resolve().parents[2]
        / "article"
        / "common"
        / "postprocess_existing.py"
    ).read_text(encoding="utf-8")

    assert "Table 3" not in runner
    assert "# Table 4 — shifted exponential" in runner
    assert "runner._table4(" in postprocessor
