import math

import pytest

from validation.tracerlpm.benchmark.scripts.mappings import (
    dm_to_inverse_gaussian,
    epm_to_shifted_exponential,
    inverse_gaussian_to_dm,
    shifted_exponential_to_epm,
)


@pytest.mark.parametrize("tau", [1.0, 20.0, 80.0])
@pytest.mark.parametrize("eta", [1.0, 1.5, 3.0, 10.0])
def test_epm_mapping_is_reversible(tau, eta):
    pyage = epm_to_shifted_exponential(tau, eta)
    restored = shifted_exponential_to_epm(pyage.mu, pyage.shift)
    assert restored.tau == pytest.approx(tau)
    assert restored.eta == pytest.approx(eta)
    assert pyage.mu + pyage.shift == pytest.approx(tau)


@pytest.mark.parametrize("tau", [10.0, 40.0])
@pytest.mark.parametrize("dp", [0.02, 0.2, 1.0])
def test_dm_mapping_is_reversible_and_preserves_moments(tau, dp):
    pyage = dm_to_inverse_gaussian(tau, dp)
    restored = inverse_gaussian_to_dm(pyage.mu, pyage.sigma)
    assert restored.tau == pytest.approx(tau)
    assert restored.dispersion_parameter == pytest.approx(dp)
    assert pyage.sigma == pytest.approx(tau * math.sqrt(2 * dp))
    assert pyage.sigma**2 == pytest.approx(2 * dp * tau**2)


@pytest.mark.parametrize("tau,eta", [(0, 2), (1, 0), (1, 0.9)])
def test_epm_mapping_rejects_invalid_parameters(tau, eta):
    with pytest.raises(ValueError):
        epm_to_shifted_exponential(tau, eta)


@pytest.mark.parametrize("tau,dp", [(0, 1), (1, 0), (-1, 1)])
def test_dm_mapping_rejects_invalid_parameters(tau, dp):
    with pytest.raises(ValueError):
        dm_to_inverse_gaussian(tau, dp)
