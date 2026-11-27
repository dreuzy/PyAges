# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Failure-injection contracts for CLI file and quickstart publication."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import pyages.cli._atomic as atomic_module
import pyages.cli.templates.config_template as config_template
from pyages.cli._atomic import atomic_write_text


def _staging_siblings(destination: Path) -> list[Path]:
    """Return hidden temporary siblings owned by one destination name."""
    return list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_atomic_create_publishes_complete_content_without_overwrite(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "config.yaml"

    assert atomic_write_text(destination, "complete\n") == destination
    assert destination.read_text(encoding="utf-8") == "complete\n"

    with pytest.raises(FileExistsError):
        atomic_write_text(destination, "replacement\n")

    assert destination.read_text(encoding="utf-8") == "complete\n"
    assert _staging_siblings(destination) == []


def test_atomic_create_cleans_staging_after_interrupted_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "config.yaml"

    def fail_flush(_descriptor: int) -> None:
        raise OSError("injected flush failure")

    monkeypatch.setattr(atomic_module.os, "fsync", fail_flush)

    with pytest.raises(OSError, match="injected flush failure"):
        atomic_write_text(destination, "never published\n")

    assert not destination.exists()
    assert _staging_siblings(destination) == []


def test_atomic_create_preserves_destination_won_by_competing_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "config.yaml"
    original_link = os.link

    def competing_link(source: str | Path, target: str | Path) -> None:
        Path(target).write_text("competitor\n", encoding="utf-8")
        original_link(source, target)

    monkeypatch.setattr(atomic_module.os, "link", competing_link)

    with pytest.raises(FileExistsError):
        atomic_write_text(destination, "our content\n")

    assert destination.read_text(encoding="utf-8") == "competitor\n"
    assert _staging_siblings(destination) == []


def test_atomic_replace_keeps_old_file_until_complete_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "config.yaml"
    destination.write_text("old\n", encoding="utf-8")
    original_replace = os.replace

    def observed_replace(source: str | Path, target: str | Path) -> None:
        assert destination.read_text(encoding="utf-8") == "old\n"
        assert Path(source).read_text(encoding="utf-8") == "new\n"
        original_replace(source, target)

    monkeypatch.setattr(atomic_module.os, "replace", observed_replace)

    atomic_write_text(destination, "new\n", overwrite=True)

    assert destination.read_text(encoding="utf-8") == "new\n"
    assert _staging_siblings(destination) == []


def test_quickstart_publishes_both_files_in_one_directory_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "quickstart"
    original_rename = os.rename

    def observed_rename(source: str | Path, target: str | Path) -> None:
        staged = Path(source)
        assert not destination.exists()
        assert (staged / "pyages.yaml").is_file()
        assert (staged / "data" / "observations.tsv").is_file()
        original_rename(source, target)

    monkeypatch.setattr(config_template.os, "rename", observed_rename)

    config_path, data_path = config_template.generate_config_quickstart(
        destination,
        "single_date",
    )

    assert config_path.is_file()
    assert data_path.is_file()
    assert _staging_siblings(destination) == []


def test_quickstart_failure_before_publication_leaves_no_public_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "quickstart"
    real_write = config_template.atomic_write_text
    calls = 0

    def fail_second_write(path: str | Path, content: str) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second-file failure")
        return real_write(path, content)

    monkeypatch.setattr(config_template, "atomic_write_text", fail_second_write)

    with pytest.raises(OSError, match="injected second-file failure"):
        config_template.generate_config_quickstart(destination, "single_date")

    assert not destination.exists()
    assert _staging_siblings(destination) == []


def test_quickstart_refuses_even_an_empty_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "quickstart"
    destination.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        config_template.generate_config_quickstart(destination, "single_date")

    assert list(destination.iterdir()) == []
