"""Small, lazily loaded public API for calibration."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CalibrationProblem": ("pyage.calibration.problem", "CalibrationProblem"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public calibration symbol only when it is requested."""
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return module globals together with lazily exported names."""
    return sorted({*globals(), *__all__})
