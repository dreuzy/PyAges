# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import pandas as pd

from scripts import run_ploemeur_targeted_ig_reproduction as runner


def test_markdown_table_has_no_optional_tabulate_dependency():
    frame = pd.DataFrame({"label": ["a|b"], "value": [1.23456789]})

    table = runner._markdown_table(frame)

    assert "| label | value |" in table
    assert "a\\|b" in table
    assert "1.23457" in table
