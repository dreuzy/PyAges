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
