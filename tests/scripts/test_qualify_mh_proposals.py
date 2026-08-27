# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for the standalone shifted-exponential MH qualification diagnostics."""

from __future__ import annotations

import numpy as np

from scripts.qualify_mh_proposals import _acf, _iact_ess, split_rhat


def test_split_rhat_is_near_one_for_independent_identical_chains():
    rng = np.random.default_rng(1402)
    chains = [rng.normal(size=5_000) for _ in range(4)]
    assert 0.99 < split_rhat(chains) < 1.01


def test_split_rhat_detects_between_chain_location_difference():
    rng = np.random.default_rng(889)
    chains = [rng.normal(size=3_000) for _ in range(3)]
    chains.append(rng.normal(loc=1.5, size=3_000))
    assert split_rhat(chains) > 1.1


def test_fft_acf_and_iact_for_independent_draws_are_well_formed():
    values = np.random.default_rng(711).normal(size=20_000)
    acf, iact, ess = _iact_ess(values)
    assert acf[0] == 1.0
    assert len(acf) == 1_001
    assert iact >= 1.0
    assert 0.8 * len(values) <= ess <= len(values)
    assert np.array_equal(acf, _acf(values))
