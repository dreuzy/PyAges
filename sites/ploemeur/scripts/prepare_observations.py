"""Convert raw Ploemeur tables to canonical observation files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pyage.concentrations.schema import (
    CONCENTRATION_COLUMN,
    DATE_COLUMN,
    ELEMENT_COLUMN,
    ERROR_COLUMN,
    UNIT_COLUMN,
)
from sites.ploemeur.observations.ploemeur import (
    ploemeur_brut_folder,
    ploemeur_ori_folder,
)


WELLS = (
    "F34",
    "MF4",
    "F38b",
    "F13",
    "F11",
    "F38",
    "F22",
    "PE",
    "MF1",
    "F28",
    "F09",
    "PZ2",
    "PSR1",
)


def _tracer_name(raw_name: object) -> str:
    """Normalize a supported raw CFC header to its canonical name."""
    name = str(raw_name).strip().lower().replace("-", "").replace(" ", "")
    if not name.startswith("cfc") or not name[3:].isdigit():
        raise ValueError(f"Unsupported tracer column: {raw_name!r}")
    return name


def _decimal_year(value: str) -> float:
    """Apply the historical Ploemeur day/month/year conversion."""
    day, month, year = (float(part) for part in value.split("/"))
    return year + (30.0 * (month - 1.0) + day) / 365.0


def prepare_well(
    well: str,
    raw_directory: str | Path,
    output_directory: str | Path,
) -> Path:
    """Normalize one ``{well}_brut.txt`` table and return its output path."""
    source = Path(raw_directory) / f"{well}_brut.txt"
    if not source.is_file():
        raise FileNotFoundError(source)
    raw = pd.read_table(source, header=None)
    if raw.shape[0] < 3 or raw.shape[1] < 2:
        raise ValueError(f"Raw observation table is incomplete: {source}")
    units = {str(raw.at[1, column]).strip().lower() for column in raw.columns[1:]}
    if units != {"pptv"}:
        raise ValueError(f"Expected only pptv tracer columns in {source}: {units}")
    tracer_names = {
        column: _tracer_name(raw.at[0, column]) for column in raw.columns[1:]
    }

    records: list[dict[str, object]] = []
    for row_index in raw.index[2:]:
        date = _decimal_year(str(raw.at[row_index, 0]))
        for column, tracer_name in tracer_names.items():
            value = pd.to_numeric(raw.at[row_index, column], errors="coerce")
            if pd.isna(value) or float(value) <= 0.0:
                continue
            records.append(
                {
                    ELEMENT_COLUMN: tracer_name,
                    CONCENTRATION_COLUMN: float(value),
                    ERROR_COLUMN: 0.0,
                    UNIT_COLUMN: "pptv",
                    DATE_COLUMN: date,
                }
            )
    if not records:
        raise ValueError(f"No positive tracer observations found in {source}")

    observations = pd.DataFrame.from_records(records)
    first_year = int(observations[DATE_COLUMN].min())
    last_year = int(observations[DATE_COLUMN].max())
    destination_directory = Path(output_directory)
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = (
        destination_directory / f"ori_ploemeur_{well}_{first_year}_{last_year}.txt"
    )
    observations.to_csv(destination, sep="\t", index=False)
    return destination


def main() -> None:
    raw_directory = Path(ploemeur_brut_folder())
    output_directory = Path(ploemeur_ori_folder())
    for well in WELLS:
        print(prepare_well(well, raw_directory, output_directory))


if __name__ == "__main__":
    main()
