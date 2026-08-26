from scripts.check_project_metadata import (
    dependency_alignment_errors,
    release_identity_errors,
)


def test_qualified_runtime_dependencies_are_aligned():
    assert dependency_alignment_errors() == []


def test_release_identity_is_aligned():
    assert release_identity_errors("v0.1.0b1") == []
