# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Canonical internal quantity contract for multi-chain MH diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from pyages.lpm.samples import LpmSampleTable


@dataclass(frozen=True)
class DiagnosticQuantity:
    """One ordered diagnostic quantity and its unpooled chain matrix."""

    name: str
    values: np.ndarray
    included_in_qualification: bool


def _diagnostic_values(
    samples: tuple[LpmSampleTable, ...],
    name: str,
) -> np.ndarray:
    """Stack one numeric diagnostic column without pooling chain identity."""
    chain_values: list[np.ndarray] = []
    for chain_index, table in enumerate(samples, start=1):
        try:
            values = table.frame[name].to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"diagnostic {name!r} in chain {chain_index} must be numeric"
            ) from exc
        if values.ndim != 1:
            raise ValueError(
                f"diagnostic {name!r} in chain {chain_index} must be one column"
            )
        chain_values.append(values)
    return np.vstack(chain_values)


def build_diagnostic_quantities(
    samples: Sequence[LpmSampleTable],
) -> tuple[DiagnosticQuantity, ...]:
    """Build the single canonical schema used by diagnostics and run records.

    Quantities are ordered as the distinct union of native LPM parameters and
    the model's declared derived moments, with native parameters first and both
    groups retaining their declared order. Every expected column must exist in
    every chain and chains must retain equal draw counts; numeric values remain
    shaped as ``(n_chains, n_draws)`` rather than being prematurely pooled.
    Finiteness is deliberately checked by each caller because unavailable live
    diagnostics and invalid persisted records have different error contracts.

    Every native sampled parameter participates in convergence qualification,
    even when all of its chains are constant, because a stuck native parameter
    is evidence against convergence. A derived moment participates exactly when
    it is non-constant over all retained chains. Derived moments that are
    constant across all retained production draws are still reported, but their
    undefined R-hat and ESS cannot make an otherwise converged run fail
    qualification.
    """
    try:
        chain_samples = tuple(samples)
    except TypeError as exc:
        raise TypeError("samples must be a sequence of LpmSampleTable objects") from exc
    if not chain_samples:
        raise ValueError("samples must contain at least one production chain")
    if any(not isinstance(table, LpmSampleTable) for table in chain_samples):
        raise TypeError("samples must contain only LpmSampleTable objects")

    first = chain_samples[0]
    parameter_names = tuple(first.get_param_names())
    names = tuple(
        dict.fromkeys(parameter_names + tuple(first.lpm_template.moments_name()))
    )
    draw_counts = {len(table.frame) for table in chain_samples}
    if len(draw_counts) != 1:
        raise ValueError("production chains must retain the same number of draws")
    if next(iter(draw_counts)) == 0:
        raise ValueError("production chains must retain at least one draw per chain")

    quantities: list[DiagnosticQuantity] = []
    for name in names:
        if any(name not in table.frame for table in chain_samples):
            raise ValueError(f"production samples are missing diagnostic {name!r}")
        values = _diagnostic_values(chain_samples, name)
        included = name in parameter_names or bool(np.any(values != values.flat[0]))
        quantities.append(
            DiagnosticQuantity(
                name=name,
                values=values,
                included_in_qualification=included,
            )
        )
    return tuple(quantities)
