# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Internal immutable value containers shared by MH records and configs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, TypeVar

import numpy as np

_Value = TypeVar("_Value")


class FrozenMapping(Mapping[str, _Value]):
    """Small immutable mapping safe for pickle and dataclass copying.

    MH mappings contain validated scalar values, so tuple storage provides
    genuinely immutable backing without ``MappingProxyType``'s pickle and
    ``deepcopy`` limitations.
    """

    __slots__ = ("_items",)

    def __init__(self, values: Mapping[str, _Value]) -> None:
        """Store the mapping as an ordered immutable tuple of items."""
        self._items = tuple(values.items())

    def __getitem__(self, key: str) -> _Value:
        for name, value in self._items:
            if name == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (name for name, _value in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._items)!r})"

    def __reduce__(self) -> tuple[Any, tuple[dict[str, _Value]]]:
        return type(self), (dict(self._items),)

    def __deepcopy__(self, _memo: dict[int, object]) -> FrozenMapping[_Value]:
        return self


def immutable_float_array(values: object) -> np.ndarray:
    """Return a float array whose immutable backing cannot be re-enabled.

    Round-tripping through ``bytes`` makes the buffer itself immutable. This is
    stronger than clearing NumPy's ``writeable`` flag on caller-owned memory,
    because that flag can otherwise be set back to true by a downstream view.
    """
    copied = np.ascontiguousarray(np.asarray(values, dtype=float))
    return np.frombuffer(copied.tobytes(order="C"), dtype=copied.dtype).reshape(
        copied.shape
    )


__all__ = ["FrozenMapping", "immutable_float_array"]
