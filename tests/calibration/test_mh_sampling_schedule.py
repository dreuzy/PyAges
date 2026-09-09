# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Scientific contracts for shared MH retained-draw calculations."""

from __future__ import annotations

import math

import pytest

from pyages.config.sampling_schedule import (
    maximum_split_ess,
    strict_retained_sample_count,
)


@pytest.mark.parametrize(
    ("nsteps", "burn_in", "thinning"),
    [
        (1, 0.0, 1),
        (10, 0.2, 2),
        (11, 0.2, 10),
        (17, 0.2, 3),
        (101, 0.333, 7),
    ],
)
def test_strict_retained_count_matches_iteration_rule(
    nsteps: int,
    burn_in: float,
    thinning: int,
) -> None:
    expected = sum(
        iteration > burn_in * nsteps and iteration % thinning == 0
        for iteration in range(nsteps)
    )

    assert strict_retained_sample_count(nsteps, burn_in, thinning) == expected


def test_strict_retained_count_excludes_threshold_iteration() -> None:
    assert strict_retained_sample_count(10, 0.2, 2) == 3


def test_maximum_split_ess_discards_each_odd_chain_tail() -> None:
    split_draws = 4 * 2 * (9 // 2)

    assert maximum_split_ess(4, 9) == pytest.approx(
        split_draws * math.log10(split_draws)
    )
    assert maximum_split_ess(4, 1) == 0.0


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ((True, 0.2, 1), "nsteps"),
        ((10, 1.0, 1), "burn_in"),
        ((10, 0.2, 0), "thinning"),
    ],
)
def test_strict_retained_count_rejects_invalid_controls(arguments, message) -> None:
    with pytest.raises(ValueError, match=message):
        strict_retained_sample_count(*arguments)


@pytest.mark.parametrize(
    ("chains", "retained_count"),
    [(True, 8), (0, 8), (4, True), (4, -1)],
)
def test_maximum_split_ess_rejects_invalid_counts(chains, retained_count) -> None:
    with pytest.raises(ValueError):
        maximum_split_ess(chains, retained_count)
