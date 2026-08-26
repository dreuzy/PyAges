"""Small reporting helpers shared by standalone article runners."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def markdown_table(
    frame: pd.DataFrame,
    *,
    float_format: str | None = None,
    numeric_round: int | None = None,
) -> str:
    """Render a DataFrame without pandas' optional ``tabulate`` dependency."""
    display = frame.copy()
    if numeric_round is not None:
        numeric = display.select_dtypes(include=[np.number]).columns
        display[numeric] = display[numeric].round(numeric_round)

    def render(value: Any) -> str:
        if pd.isna(value):
            return ""
        if float_format is not None and isinstance(value, (float, np.floating)):
            return format(float(value), float_format)
        return str(value).replace("|", "\\|")

    columns = list(map(str, display.columns))
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| " + " | ".join(render(value) for value in row) + " |"
        for row in display.itertuples(index=False, name=None)
    ]
    return "\n".join((header, separator, *rows))
