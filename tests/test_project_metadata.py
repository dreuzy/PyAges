# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from scripts.check_project_metadata import (
    dependency_alignment_errors,
    release_identity_errors,
)


def test_qualified_runtime_dependencies_are_compatible():
    assert dependency_alignment_errors() == []


def test_release_identity_is_aligned():
    assert release_identity_errors("v0.1.0b1") == []
