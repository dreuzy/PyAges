"""Serialization helpers for lumped-parameter models."""

from __future__ import annotations

from contextlib import nullcontext
from os import PathLike
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from pyage.lpm.core.lpm_base import LpmBase


def write_lpm_name(lpm: "LpmBase", stream: TextIO) -> None:
    """Write the model identifier to an open text stream."""
    stream.write(f"lpm\t{lpm.name}\n")


def write_lpm(
    lpm: "LpmBase",
    target: str | PathLike[str] | TextIO,
    *,
    open_file: bool = False,
) -> None:
    """Write model parameters to a path or an already-open text stream."""
    context = open(target, "w", encoding="utf-8") if open_file else nullcontext(target)
    with context as stream:
        write_lpm_name(lpm, stream)
        for name, value in lpm.p.items():
            stream.write(f"{name}\t{value}\t{lpm.parameter_units[name]}\n")
