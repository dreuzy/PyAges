# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Operational CLI contracts for interrupted workflow stages."""

import json

from click.testing import CliRunner

from pyages.cli.main import cli
from pyages.workflows.runtime.manifest import begin_staged_result_run


def test_stages_inspect_json_is_read_only_and_machine_readable(tmp_path) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    journal = run.working_directory / ".pyages-run-state.json"
    journal_before = journal.read_bytes()

    result = CliRunner().invoke(cli, ["stages", "inspect", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["stage_directory"] == str(run.working_directory)
    assert payload[0]["run_id"] == run.run_id
    assert payload[0]["manifest_status"] == "absent"
    assert not payload[0]["promotable_now"]
    assert "promotable" not in payload[0]
    assert journal.read_bytes() == journal_before


def test_stages_quarantine_requires_confirmation_and_exact_uuid(tmp_path) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    runner = CliRunner()

    rejected = runner.invoke(
        cli,
        [
            "stages",
            "quarantine",
            str(run.working_directory),
            "--run-id",
            "00000000-0000-0000-0000-000000000000",
            "--yes",
        ],
    )

    assert rejected.exit_code == 1
    assert "Run identity mismatch" in rejected.output
    assert run.working_directory.is_dir()

    accepted = runner.invoke(
        cli,
        [
            "stages",
            "quarantine",
            str(run.working_directory),
            "--run-id",
            run.run_id,
            "--yes",
        ],
    )

    assert accepted.exit_code == 0, accepted.output
    assert "Quarantined staging tree" in accepted.output
    assert not run.working_directory.exists()
    assert (tmp_path / f".pyages-quarantine-{run.run_id[:12]}").is_dir()
