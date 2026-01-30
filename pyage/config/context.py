# -*- coding: utf-8 -*-
"""
PyAge execution context for dependency injection.

Purpose
-------
Provides a centralized, injectable configuration context that replaces
direct access to global_parameters. This enables:
- Testing with different configurations
- Running multiple independent analyses in parallel
- Clearer dependencies in function signatures

Usage
-----
    from pyage.config.context import PyAgeContext

    # Use default configuration
    ctx = PyAgeContext.default()

    # Use custom configuration for testing
    test_ctx = PyAgeContext(
        lpm_data_dir=Path("test_data/lpm"),
        tracer_data_dir=Path("test_data/tracer")
    )

    # Pass context to functions
    lpm = create_lpm("ig", ctx=test_ctx)

Author
------
Jean-Raynald de Dreuzy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


@dataclass(frozen=True)
class PyAgeContext:
    """
    Immutable execution context containing all configuration parameters.

    This replaces scattered access to global_parameters throughout the codebase,
    making dependencies explicit and enabling isolated testing.

    Attributes
    ----------
    lpm_data_dir : Path
        Directory containing LPM parameter files (params.yaml for each model).
    tracer_data_dir : Path
        Directory containing tracer configuration and recharge data.
    resolution_convolution : int
        Number of sampling points for numerical convolution.
    resolution_mh_trajectory : int
        Default resolution for Metropolis-Hastings trajectory sampling.

    Examples
    --------
        # Default context from global_parameters
        ctx = PyAgeContext.default()

        # Custom context for testing
        ctx = PyAgeContext(
            lpm_data_dir=Path("tests/fixtures/lpm"),
            tracer_data_dir=Path("tests/fixtures/tracer"),
            resolution_convolution=100  # Lower for faster tests
        )
    """

    lpm_data_dir: Path
    tracer_data_dir: Path
    resolution_convolution: int = 200
    resolution_mh_trajectory: int = 1000

    @classmethod
    def default(cls) -> PyAgeContext:
        """
        Create a context with default values from global_parameters.

        Returns
        -------
        PyAgeContext
            Context initialized with global configuration.
        """
        import pyage.global_parameters as gp

        return cls(
            lpm_data_dir=Path(gp.DIRECTORY_LPM_DATA),
            tracer_data_dir=Path(gp.DIRECTORY_TRACER_DATA),
            resolution_convolution=getattr(gp, 'RESOLUTION_CONVOLUTION', 200),
        )

    @classmethod
    def for_testing(
        cls,
        base_dir: Optional[Union[str, Path]] = None,
        resolution_convolution: int = 50,
    ) -> PyAgeContext:
        """
        Create a context optimized for testing.

        Parameters
        ----------
        base_dir : Path, optional
            Base directory for test data. If not provided, uses
            a temporary directory structure.
        resolution_convolution : int
            Lower resolution for faster test execution.

        Returns
        -------
        PyAgeContext
            Context configured for testing.
        """
        if base_dir is None:
            # Use default data directories but with lower resolution
            import pyage.global_parameters as gp
            return cls(
                lpm_data_dir=Path(gp.DIRECTORY_LPM_DATA),
                tracer_data_dir=Path(gp.DIRECTORY_TRACER_DATA),
                resolution_convolution=resolution_convolution,
            )

        base = Path(base_dir)
        return cls(
            lpm_data_dir=base / "data_lpm",
            tracer_data_dir=base / "data_tracer",
            resolution_convolution=resolution_convolution,
        )

    def with_lpm_dir(self, lpm_data_dir: Union[str, Path]) -> PyAgeContext:
        """
        Create a new context with a different LPM data directory.

        Parameters
        ----------
        lpm_data_dir : Path
            New LPM data directory.

        Returns
        -------
        PyAgeContext
            New context with updated LPM directory.
        """
        return PyAgeContext(
            lpm_data_dir=Path(lpm_data_dir),
            tracer_data_dir=self.tracer_data_dir,
            resolution_convolution=self.resolution_convolution,
            resolution_mh_trajectory=self.resolution_mh_trajectory,
        )

    def with_tracer_dir(self, tracer_data_dir: Union[str, Path]) -> PyAgeContext:
        """
        Create a new context with a different tracer data directory.

        Parameters
        ----------
        tracer_data_dir : Path
            New tracer data directory.

        Returns
        -------
        PyAgeContext
            New context with updated tracer directory.
        """
        return PyAgeContext(
            lpm_data_dir=self.lpm_data_dir,
            tracer_data_dir=Path(tracer_data_dir),
            resolution_convolution=self.resolution_convolution,
            resolution_mh_trajectory=self.resolution_mh_trajectory,
        )


# Module-level default context (lazily initialized)
_default_context: Optional[PyAgeContext] = None


def get_default_context() -> PyAgeContext:
    """
    Get the default execution context.

    Lazily initializes the default context on first access.

    Returns
    -------
    PyAgeContext
        The default execution context.
    """
    global _default_context
    if _default_context is None:
        _default_context = PyAgeContext.default()
    return _default_context


def set_default_context(ctx: PyAgeContext) -> None:
    """
    Set the default execution context.

    Useful for testing or when running with non-standard configuration.

    Parameters
    ----------
    ctx : PyAgeContext
        New default context.
    """
    global _default_context
    _default_context = ctx


def reset_default_context() -> None:
    """
    Reset the default context to be re-initialized on next access.

    Useful in tests to ensure clean state.
    """
    global _default_context
    _default_context = None
