# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Serialization helpers for lumped-parameter models."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase


def write_lpm_name(lpm: "LpmBase", stream: TextIO) -> None:
    """Write the model identifier to an open text stream."""
    stream.write(f"lpm\t{lpm.name}\n")


def write_lpm(
    lpm: "LpmBase",
    target: str | PathLike[str] | TextIO,
) -> None:
    """Write model parameters to a path or an already-open text stream.

    Parameters
    ----------
    lpm : LpmBase
        Model whose identifier, parameter values, and units are serialized.
    target : path-like or text stream
        Destination path, for which parent directories are created, or an
        already-open writable text stream that remains owned by the caller.
    """

    def write_to_stream(stream: TextIO) -> None:
        write_lpm_name(lpm, stream)
        for name, value in lpm.p.items():
            stream.write(f"{name}\t{value}\t{lpm.parameter_units[name]}\n")

    if isinstance(target, (str, PathLike)):
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as stream:
            write_to_stream(stream)
        return
    if not hasattr(target, "write"):
        raise TypeError("target must be a path-like object or writable text stream")
    write_to_stream(target)
