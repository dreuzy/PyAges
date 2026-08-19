import csv
from pathlib import Path

from validation.tracerlpm.benchmark.scripts.generate_observations import generate


def test_observations_are_reproducible_and_keep_unnoised_truth(tmp_path):
    root = Path(__file__).parents[1]
    first = generate(
        root / "configs" / "campaign.yaml",
        root / "references" / "forward_reference.csv",
        tmp_path / "one.csv",
        tmp_path / "one.yaml",
    )
    second = generate(
        root / "configs" / "campaign.yaml",
        root / "references" / "forward_reference.csv",
        tmp_path / "two.csv",
        tmp_path / "two.yaml",
    )
    assert (
        first["synthetic_observations_sha256"]
        == second["synthetic_observations_sha256"]
    )
    assert first["observation_row_count"] == 1350
    with (tmp_path / "one.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    unnoised = [row for row in rows if row["noise_regime"] == "none"]
    assert len(unnoised) == 270
    assert all(
        row["true_concentration"] == row["observed_concentration"] for row in unnoised
    )
