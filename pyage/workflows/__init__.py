"""Reusable high-level PyAge workflows with lazy imports."""


def run_single_date(*args, **kwargs):
    """Run the single-date workflow without importing it at package import time."""
    from pyage.workflows.single_date import run_single_date as implementation

    return implementation(*args, **kwargs)


def run_temporal(*args, **kwargs):
    """Run the temporal workflow without importing it at package import time."""
    from pyage.workflows.temporal import run_temporal as implementation

    return implementation(*args, **kwargs)


__all__ = ["run_single_date", "run_temporal"]
