# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Load and evaluate independent parameter priors used by MH calibration."""

from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from pyages.calibration.methods.mh._prior_empirical import (
    EMPIRICAL_GRID_POINTS,
    EMPIRICAL_RELATIVE_TAIL_DECAY,
    build_empirical_prior_grid,
)
from pyages.calibration.methods.mh._prior_marginals import (
    EmpiricalMarginal,
    PriorMarginal,
    parametric_marginal,
)
from pyages.data_io.lpm_distribution import read_histogram


class Prior:
    """Factorized prior used by one- and multi-chain MH."""

    def __init__(
        self,
        option: bool = True,
        typ: str = "parametric",
        prior_file: str = "",
    ) -> None:
        """Create an empty prior with the requested storage format."""
        if type(option) is not bool:
            raise TypeError("option must be a boolean")
        if typ not in {"parametric", "empirical"}:
            raise ValueError(f"Unsupported prior type: {typ}")
        if not isinstance(prior_file, str):
            raise TypeError("prior_file must be a string")
        self.option = option
        self.typ = typ
        self.prior_file = prior_file
        self._marginals: dict[str, PriorMarginal] = {}

    def require_marginals(self, names: Sequence[str]) -> None:
        """Require an enabled, loaded marginal for every requested parameter."""
        if not self.option:
            raise ValueError("prior initialization requires an enabled prior")
        missing = [name for name in names if name not in self._marginals]
        if missing:
            raise ValueError(f"prior must be loaded for parameters {missing}")

    def _marginal(self, name: str) -> PriorMarginal:
        """Return the loaded marginal for one parameter."""
        self.require_marginals((name,))
        return self._marginals[name]

    @staticmethod
    def _numeric_value(value: float) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    def bounded_quantile(
        self,
        name: str,
        minimum: float,
        maximum: float,
        probability: float,
    ) -> float:
        """Invert one marginal conditional on a calibration range."""
        return self._marginal(name).bounded_quantile(minimum, maximum, probability)

    def contains(self, name: str, value: float) -> bool:
        """Return whether a value has finite positive marginal density."""
        numeric = self._numeric_value(value)
        return numeric is not None and self._marginal(name).contains(numeric)

    def density_grid(self, name: str) -> np.ndarray:
        """Return a detached empirical density grid for diagnostic plotting."""
        marginal = self._marginal(name)
        if not isinstance(marginal, EmpiricalMarginal):
            raise TypeError(f"Prior marginal {name!r} is not empirical")
        return marginal.density_grid()

    def param_init(
        self,
        lpm: Any,
        strategy: str = "map",
        rng: np.random.Generator | None = None,
    ) -> None:
        """Initialize all model parameters without changing their seeded law."""
        if strategy not in {"map", "sample"}:
            raise ValueError("strategy must be 'map' or 'sample'")
        if rng is None:
            rng = np.random.default_rng()
        parameters = [
            self._marginal(name).initial_value(
                *lpm.get_calibration_range(name),
                rng,
                strategy,
            )
            for name in lpm.p
        ]
        lpm.set_param_from_array(parameters)

    def _load_parametric_priors(self, lpm: Any) -> None:
        """Load validated parametric definitions in native parameter order."""
        from pyages.data_io import lpm_params

        self._marginals = {}
        schema = lpm_params.load_parameter_schema(lpm.name, lpm.lpm_data_directory)
        for name, prior in lpm_params.get_priors(schema).items():
            prior_type = prior.get("type")
            if not prior_type:
                continue
            fields = ("min", "max") if prior_type == "uniform" else ("mean", "std")
            self._marginals[name] = parametric_marginal(
                name,
                prior_type,
                [prior.get(field) for field in fields],
            )
        expected = list(lpm.p)
        missing = [name for name in expected if name not in self._marginals]
        extra = [name for name in self._marginals if name not in lpm.p]
        if missing or extra:
            raise ValueError(
                "Configured parametric priors must match the LPM parameters "
                f"(missing={missing}, extra={extra})"
            )

    def _load_empirical_priors(self, lpm: Any) -> None:
        """Load and extend one empirical density grid per model parameter."""
        if not self.prior_file:
            raise ValueError("prior_file must be non-empty for an empirical prior")
        self._marginals = {}
        for parameter in lpm.get_param_names():
            source = Path(f"{self.prior_file}_{parameter}.txt")
            source_bytes = source.read_bytes()
            histogram = read_histogram(f"{self.prior_file}.txt", parameter).to_numpy()
            if source.read_bytes() != source_bytes:
                raise RuntimeError(
                    f"Empirical prior source changed while loading {parameter!r}"
                )
            source_sha256 = hashlib.sha256(source_bytes).hexdigest()
            minimum, maximum = lpm.get_calibration_range(parameter)
            parameter_range = maximum - minimum
            if parameter_range <= 0.0:
                raise ValueError(
                    f"Empirical prior calibration range collapses for {parameter}"
                )
            decay = EMPIRICAL_RELATIVE_TAIL_DECAY / parameter_range
            values, density = build_empirical_prior_grid(
                histogram[:, 0],
                histogram[:, 1],
                xmin=minimum,
                xmax=maximum,
                n_points=EMPIRICAL_GRID_POINTS,
                decay_left=decay,
                decay_right=decay,
            )
            self._marginals[parameter] = EmpiricalMarginal(
                parameter,
                np.column_stack((values, density)),
                source_sha256,
            )

    def load(self, lpm: Any) -> None:
        """Load prior definitions for a model when the prior is enabled."""
        if not self.option:
            return
        loader = (
            self._load_parametric_priors
            if self.typ == "parametric"
            else self._load_empirical_priors
        )
        loader(lpm)

    def resolved_metadata(self, lpm: Any) -> dict[str, str | int]:
        """Return stable scalar metadata for every loaded marginal."""
        metadata: dict[str, str | int] = {}
        if not self.option:
            return metadata
        for name in lpm.get_param_names():
            minimum, maximum = lpm.get_calibration_range(name)
            for field, value in self._marginal(name).metadata(minimum, maximum).items():
                metadata[f"prior_{field}_{name}"] = value
        return metadata

    def evaluate(self, lpm: Any, params: list[float]) -> float:
        """Evaluate the factorized prior density in probability space."""
        probability = 1.0
        for index, name in enumerate(lpm.p):
            value = params[index]
            probability *= self._marginal(name).density(value)
            if probability == 0.0:
                break
        return probability

    def log_evaluate(self, lpm: Any, params: list[float]) -> float:
        """Evaluate the factorized log-density with exact zero support."""
        log_probability = 0.0
        for index, name in enumerate(lpm.p):
            value = params[index]
            contribution = self._marginal(name).log_density(value)
            if contribution == -math.inf:
                return -math.inf
            log_probability += contribution
        return log_probability

    def validate_chain_moments(
        self,
        path: pd.DataFrame,
        lpm: Any,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Compare sampled prior moments with marginal expectations."""
        sampled = {
            name: [
                np.nanmean(path[name].to_numpy(), dtype="float"),
                np.nanvar(path[name].to_numpy(), dtype="float"),
            ]
            for name in lpm.p
        }
        theory = {
            name: list(self._marginal(name).moments(*lpm.get_calibration_range(name)))
            for name in lpm.p
        }
        differences = copy.deepcopy(sampled)
        for name in lpm.p:
            for index in (0, 1):
                reference = theory[name][index]
                differences[name][index] = (
                    math.nan
                    if reference == 0.0
                    else 100.0 * (sampled[name][index] - reference) / abs(reference)
                )
        return {
            "sampled": {
                name: {"mean": value[0], "var": value[1]}
                for name, value in sampled.items()
            },
            "theory": {
                name: {"mean": value[0], "var": value[1]}
                for name, value in theory.items()
            },
            "difference_percent": {
                name: {"mean": value[0], "var": value[1]}
                for name, value in differences.items()
            },
        }


__all__ = ["Prior"]
