import pytest

from scripts.generate_test_inventory import Collection, render_inventory


def test_inventory_summary_distinguishes_scopes():
    rendered = render_inventory(
        Collection(
            core=(
                "tests/lpm/test_models.py::test_model[a]",
                "tests/lpm/test_models.py::test_model[b]",
                "tests/workflows/test_run.py::test_slow",
            ),
            extensive=("tests/workflows/test_run.py::test_slow",),
            tracerlpm=(
                "validation/tracerlpm/benchmark/tests/test_mapping.py::test_mapping",
            ),
        )
    )

    assert "| Standard selection | 2 | 2 |" in rendered
    assert "| Extensive opt-in | 1 | 1 |" in rendered
    assert "| TracerLPM validation | 1 | 1 |" in rendered
    assert "`tests/lpm/test_models.py`" in rendered
    assert "`validation/tracerlpm/benchmark/tests/test_mapping.py`" in rendered
    assert "Golden regression" not in rendered
    assert "Extensive scientific" in rendered
    assert "Models within lumped-parameter models." in rendered
    assert "mapping within tracerlpm cross-software validation." in rendered.lower()

    with pytest.raises(ValueError, match="No test-area description"):
        render_inventory(
            Collection(
                core=("tests/new_area/test_new.py::test_new",),
                extensive=(),
                tracerlpm=(),
            )
        )
