# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for dependency-light multi-chain MCMC diagnostics."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pyages.calibration.methods.mh.diagnostics import (
    bulk_ess,
    ess,
    mcse_mean,
    rank_normalize,
    split_chains,
    split_rhat,
    tail_ess,
)


def test_split_chains_uses_equal_ends_and_discards_an_odd_middle_draw():
    values = np.array([[0, 1, 2, 3, 4], [10, 11, 12, 13, 14]], dtype=float)

    split = split_chains(values)

    assert np.array_equal(
        split,
        np.array([[0, 1], [10, 11], [3, 4], [13, 14]], dtype=float),
    )


def test_rank_normalize_preserves_shape_order_and_ties():
    values = np.array([[1, 2, 2, 4], [0, 3, 5, 6]], dtype=float)

    normalized = rank_normalize(values)

    assert normalized.shape == values.shape
    assert normalized[0, 1] == normalized[0, 2]
    ordered = normalized.reshape(-1)[np.argsort(values.reshape(-1))]
    assert np.all(np.diff(ordered) >= 0.0)
    assert np.all(np.isfinite(normalized))


def test_split_rhat_is_near_one_for_well_mixed_chains():
    values = np.random.default_rng(4129).normal(size=(4, 4_000))

    assert 0.99 < split_rhat(values) < 1.01


def test_split_rhat_detects_between_chain_location_difference():
    rng = np.random.default_rng(731)
    values = rng.normal(size=(4, 3_000))
    values[2:] += 2.0

    assert split_rhat(values) > 1.1


def test_folded_split_rhat_detects_between_chain_scale_difference():
    rng = np.random.default_rng(9381)
    values = np.vstack(
        [
            rng.normal(scale=1.0, size=3_000),
            rng.normal(scale=1.0, size=3_000),
            rng.normal(scale=4.0, size=3_000),
            rng.normal(scale=4.0, size=3_000),
        ]
    )

    assert split_rhat(values) > 1.1


def test_ess_is_high_for_independent_draws_and_low_for_autocorrelated_draws():
    rng = np.random.default_rng(2917)
    independent = rng.normal(size=(4, 4_000))
    noise = rng.normal(size=independent.shape)
    autocorrelated = np.empty_like(noise)
    autocorrelated[:, 0] = noise[:, 0]
    for draw in range(1, noise.shape[1]):
        autocorrelated[:, draw] = 0.95 * autocorrelated[:, draw - 1] + noise[:, draw]

    independent_ess = ess(independent)
    autocorrelated_ess = ess(autocorrelated)

    assert independent_ess > 0.8 * independent.size
    assert autocorrelated_ess < 0.1 * autocorrelated.size
    assert autocorrelated_ess < independent_ess


def test_bulk_and_tail_ess_are_finite_and_bounded_by_retained_draws():
    values = np.random.default_rng(183).standard_t(df=4, size=(4, 2_001))
    retained_count = 4 * 2 * (values.shape[1] // 2)
    stan_upper_bound = retained_count * math.log10(retained_count)

    for diagnostic in (bulk_ess(values), tail_ess(values)):
        assert 0.0 < diagnostic <= stan_upper_bound


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            np.array(
                [
                    [0, 1, 0.5, 1.5, 1, 2, 1.5, 2.5, 2, 3, 2.5],
                    [0.2, 1.2, 0.7, 1.7, 1.2, 2.2, 1.7, 2.7, 2.2, 3.2, 2.7],
                    [-0.1, 0.9, 0.4, 1.4, 0.9, 1.9, 1.4, 2.4, 1.9, 2.9, 2.4],
                    [0, 1, 0.5, 1.5, 1, 2, 1.5, 2.5, 2, 3, 2.5],
                ],
                dtype=float,
            ),
            (
                1.5754412854670237,
                14.683207288736075,
                50.38167938931298,
                0.23913016176230617,
            ),
        ),
        (
            np.array(
                [
                    [0.2, -1.1, 0.7, 0.4, -0.3, 1.8, -0.8, 0.1],
                    [0.5, -0.6, 1.2, -0.2, 0.9, -1.4, 0.3, 0.8],
                    [-0.4, 0.6, -0.9, 1.5, 0.2, -0.1, 1.1, -0.7],
                    [0.8, -0.2, 0.1, -1.3, 0.6, 1.4, -0.5, 0.4],
                ],
                dtype=float,
            ),
            (
                0.9116245436095582,
                48.16479930623699,
                48.16479930623699,
                0.11886843828720052,
            ),
        ),
        (
            np.array(
                [
                    [0, 1, 100, 2, 3],
                    [0.1, 1.1, 200, 2.1, 3.1],
                ],
                dtype=float,
            ),
            (
                1.6402186857086332,
                7.224719895935548,
                7.224719895935548,
                24.886184680618257,
            ),
        ),
    ],
)
def test_diagnostics_match_arviz_022_reference(values, expected):
    """Lock rank R-hat, bulk/tail ESS, and mean MCSE to ArviZ 0.22.0."""
    actual = (split_rhat(values), bulk_ess(values), tail_ess(values), mcse_mean(values))

    assert actual == pytest.approx(expected, rel=1.0e-12, abs=1.0e-12)


def test_tail_ess_matches_the_smaller_quantile_indicator_ess():
    values = np.random.default_rng(622).normal(size=(4, 2_000))
    lower, upper = np.quantile(values, (0.1, 0.9))
    expected = min(
        ess(np.asarray(values <= lower, dtype=float)),
        ess(np.asarray(values <= upper, dtype=float)),
    )

    assert tail_ess(values, probability=0.1) == pytest.approx(expected)


def test_mcse_mean_uses_supplied_ess_and_can_estimate_it():
    values = np.arange(32.0).reshape(4, 8)
    supplied_ess = 16.0

    assert mcse_mean(values, supplied_ess) == pytest.approx(
        np.std(values, ddof=1) / math.sqrt(supplied_ess)
    )
    assert mcse_mean(values) == pytest.approx(
        np.std(values, ddof=1) / math.sqrt(ess(values))
    )


def test_constant_chains_are_flagged_as_degenerate():
    values = np.ones((4, 20))

    assert math.isinf(split_rhat(values))
    assert ess(values) == 0.0
    assert bulk_ess(values) == 0.0
    assert tail_ess(values) == 0.0
    assert mcse_mean(values) == 0.0


def test_all_diagnostics_accept_the_documented_four_draw_minimum():
    values = np.array(
        [[0.0, 1.0, 2.0, 3.0], [0.2, 1.2, 2.2, 3.2]],
        dtype=float,
    )

    assert split_chains(values).shape == (4, 2)
    assert rank_normalize(values).shape == values.shape
    assert math.isfinite(split_rhat(values))
    assert ess(values) > 0.0
    assert bulk_ess(values) > 0.0
    assert tail_ess(values) >= 0.0
    assert math.isfinite(mcse_mean(values))


@pytest.mark.parametrize(
    "values",
    [
        np.ones(10),
        np.ones((1, 10)),
        np.ones((2, 3)),
        np.array([[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, np.nan, 4.0]]),
        np.array([[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, np.inf, 4.0]]),
    ],
)
@pytest.mark.parametrize(
    "diagnostic",
    [split_chains, rank_normalize, split_rhat, ess, bulk_ess, tail_ess, mcse_mean],
)
def test_diagnostics_reject_invalid_chain_arrays(values, diagnostic):
    with pytest.raises(ValueError):
        diagnostic(values)


@pytest.mark.parametrize("probability", [0.0, 0.5, -0.1, 0.6, np.nan, np.inf])
def test_tail_ess_rejects_invalid_probability(probability):
    with pytest.raises(ValueError, match="probability"):
        tail_ess(np.arange(40.0).reshape(4, 10), probability=probability)


@pytest.mark.parametrize("effective", [0.0, -1.0, np.nan, np.inf])
def test_mcse_rejects_invalid_supplied_ess(effective):
    with pytest.raises(ValueError, match="effective_sample_size"):
        mcse_mean(np.arange(40.0).reshape(4, 10), effective)
