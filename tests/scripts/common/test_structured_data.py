# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for shared structured-data validation boundaries."""

import pytest

from scripts.common.structured_data import (
    integer_field,
    list_field,
    mapping_field,
    require_mapping,
    string_field,
)


def test_structured_fields_preserve_valid_values() -> None:
    payload: dict[str, object] = {
        "metadata": {"version": 1},
        "files": ["one", "two"],
        "name": "archive",
    }

    assert mapping_field(payload, "metadata") == {"version": 1}
    assert list_field(payload, "files") == ["one", "two"]
    assert string_field(payload, "name") == "archive"
    assert integer_field({"count": 2}, "count") == 2


@pytest.mark.parametrize("value", [None, [], "mapping", {1: "invalid key"}])
def test_require_mapping_rejects_ambiguous_shapes(value: object) -> None:
    with pytest.raises(ValueError, match="manifest"):
        require_mapping(value, "manifest")


def test_missing_or_wrong_field_types_are_contextual() -> None:
    with pytest.raises(ValueError, match="Missing required field: files"):
        list_field({}, "files")
    with pytest.raises(ValueError, match="name must be a string"):
        string_field({"name": 42}, "name")
    with pytest.raises(ValueError, match="count must be an integer"):
        integer_field({"count": True}, "count")
