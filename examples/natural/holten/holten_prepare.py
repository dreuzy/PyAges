# -*- coding: utf-8 -*-
"""
Preparation utilities for the Holten benchmark workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import numpy as np
import pandas as pd
import yaml

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

from holten_case import HoltenContext, PreparedHoltenCase, build_context, decimal_year_from_sampling_date


VALID_TRACERS = ("3H", "kr85", "39Ar")
TRACER_REQUIRED_SECTIONS = {
    "3H": ("premodern_input",),
    "kr85": ("old_endmember",),
    "39Ar": ("old_endmember",),
}
TRACER_OUTPUT_UNITS = {"3H": "TU", "kr85": "dpm/ccKr", "39Ar": "%modern"}


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML structure in {path}")
    return payload


def read_sampling_table(context: HoltenContext) -> pd.DataFrame:
    frame = pd.read_csv(context.paths.sampling_raw_path, sep="\t")
    frame["Date_decimal_exact"] = frame["Date"].apply(decimal_year_from_sampling_date)
    frame["Date_decimal"] = frame["Date_decimal_exact"].round(context.date_round_decimals)
    return frame


def select_v1_wells(frame: pd.DataFrame, selected_wells: list[str]) -> pd.DataFrame:
    filtered = frame.loc[frame["ID"].isin(selected_wells)].copy()
    missing = sorted(set(selected_wells).difference(set(filtered["ID"])))
    if missing:
        raise ValueError(f"Missing selected wells in sampling_data.txt: {missing}")
    return filtered


def _is_missing(value: Any) -> bool:
    if pd.isna(value):
        return True
    if isinstance(value, str) and value.strip().upper() == "NA":
        return True
    return False


def _resolve_repo_relative(path_text: str, context: HoltenContext) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return context.paths.repo_root / path


def validate_local_tracer_yaml(tracer_name: str, context: HoltenContext) -> dict[str, Any]:
    yaml_path = context.paths.tracer_source_dir / tracer_name / f"{tracer_name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Missing local Holten tracer YAML: {yaml_path}")
    payload = _read_yaml(yaml_path)

    for key in ("unit", "decay_time"):
        if key not in payload:
            raise ValueError(f"{yaml_path}: missing top-level key '{key}'")

    has_recharge = "recharge" in payload
    has_constant = "recharge_constant" in payload
    if has_recharge == has_constant:
        raise ValueError(
            f"{yaml_path}: exactly one of 'recharge' or 'recharge_constant' must be defined"
        )

    if float(payload["decay_time"]) <= 0:
        raise ValueError(f"{yaml_path}: decay_time must be > 0")

    if has_constant:
        for key in ("datemin", "datemax"):
            if key not in payload:
                raise ValueError(f"{yaml_path}: missing '{key}' for constant recharge")
        if float(payload["datemin"]) >= float(payload["datemax"]):
            raise ValueError(f"{yaml_path}: datemin must be < datemax")

    holten = payload.get("holten")
    if not isinstance(holten, dict):
        raise ValueError(f"{yaml_path}: missing 'holten' section")
    source = holten.get("source")
    preparation = holten.get("preparation")
    if not isinstance(source, dict):
        raise ValueError(f"{yaml_path}: missing 'holten.source'")
    if not isinstance(preparation, dict):
        raise ValueError(f"{yaml_path}: missing 'holten.preparation'")

    for key in ("reference",):
        if key not in holten:
            raise ValueError(f"{yaml_path}: missing 'holten.{key}'")
    for key in ("observation_table", "observation_field", "observation_unit"):
        if key not in source:
            raise ValueError(f"{yaml_path}: missing 'holten.source.{key}'")
    for key in ("input_normalization", "output_unit"):
        if key not in preparation:
            raise ValueError(f"{yaml_path}: missing 'holten.preparation.{key}'")

    if str(preparation["output_unit"]) != str(payload["unit"]):
        raise ValueError(f"{yaml_path}: holten.preparation.output_unit must match unit")

    observation_table = _resolve_repo_relative(str(source["observation_table"]), context)
    if not observation_table.exists():
        raise FileNotFoundError(f"{yaml_path}: observation table not found: {observation_table}")

    if bool(payload.get("recharge", False)):
        for key in ("recharge_file", "recharge_unit"):
            if key not in source:
                raise ValueError(f"{yaml_path}: missing 'holten.source.{key}'")
        recharge_path = _resolve_repo_relative(str(source["recharge_file"]), context)
        if not recharge_path.exists():
            raise FileNotFoundError(f"{yaml_path}: recharge file not found: {recharge_path}")

    for section_name in TRACER_REQUIRED_SECTIONS.get(tracer_name, ()):
        if section_name not in holten:
            raise ValueError(f"{yaml_path}: missing 'holten.{section_name}'")

    if tracer_name == "kr85":
        if "krypton_air_fraction" not in preparation or "conversion_factor" not in preparation:
            raise ValueError(f"{yaml_path}: kr85 requires krypton_air_fraction and conversion_factor")
        if float(preparation["krypton_air_fraction"]) <= 0 or float(preparation["conversion_factor"]) <= 0:
            raise ValueError(f"{yaml_path}: kr85 conversion constants must be > 0")
    if tracer_name == "39Ar":
        if str(preparation.get("value_scale")) != "fraction_of_modern":
            raise ValueError(f"{yaml_path}: 39Ar requires value_scale=fraction_of_modern")

    return payload


def _parse_history_file(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t")


def _coerce_numeric_series(series: pd.Series, label: str) -> pd.Series:
    cleaned = series.astype(str).str.replace("..", ".", regex=False).str.strip()
    values = pd.to_numeric(cleaned, errors="coerce")
    if values.isna().any():
        bad = cleaned.loc[values.isna()].head(5).tolist()
        raise ValueError(f"Could not parse numeric values in {label}: {bad}")
    return values


def _prepare_3h_history(tracer_cfg: dict[str, Any], context: HoltenContext) -> pd.DataFrame:
    source = tracer_cfg["holten"]["source"]
    path = _resolve_repo_relative(str(source["recharge_file"]), context)
    raw = _parse_history_file(path)
    value_col = next(col for col in raw.columns if col != "Date")
    history = pd.DataFrame(
        {
            "date": raw["Date"].astype(str).map(decimal_year_from_sampling_date),
            "concentration": raw[value_col].astype(float),
            "unit": tracer_cfg["unit"],
        }
    )
    return history.sort_values("date").reset_index(drop=True)


def _prepare_kr85_history(tracer_cfg: dict[str, Any], context: HoltenContext) -> pd.DataFrame:
    source = tracer_cfg["holten"]["source"]
    prep = tracer_cfg["holten"]["preparation"]
    path = _resolve_repo_relative(str(source["recharge_file"]), context)
    raw = _parse_history_file(path)
    value_col = next(col for col in raw.columns if "[Bq/cbm air]" in col)
    factor = float(prep["conversion_factor"])
    values = _coerce_numeric_series(raw[value_col], f"{path}:{value_col}")
    history = pd.DataFrame(
        {
            "date": raw["Date"].astype(str).map(decimal_year_from_sampling_date),
            "concentration": values * factor,
            "unit": tracer_cfg["unit"],
        }
    )
    if "Kr85_error [Bq/cbm air]" in raw.columns:
        errors = _coerce_numeric_series(raw["Kr85_error [Bq/cbm air]"], f"{path}:Kr85_error [Bq/cbm air]")
        history["error"] = errors * factor
    return history.sort_values("date").reset_index(drop=True)


def _prepare_39ar_history(tracer_cfg: dict[str, Any], reference_year: float) -> pd.DataFrame:
    decay_time = float(tracer_cfg["decay_time"])
    recharge_constant = float(tracer_cfg["recharge_constant"])
    old_endmember = float(tracer_cfg["holten"]["old_endmember"]["value"])
    min_age_to_show = max(350.0, -1.25 * decay_time * np.log(max(old_endmember, 1e-6)))
    start_year = max(float(tracer_cfg["datemin"]), reference_year - min_age_to_show)
    dates = np.linspace(start_year, reference_year, 360)
    concentrations = recharge_constant * np.exp(-(reference_year - dates) / decay_time)
    history = pd.DataFrame(
        {
            "date": dates,
            "concentration": concentrations,
            "unit": [tracer_cfg["unit"]] * len(dates),
        }
    )
    history.attrs["display_kind"] = "reference_decay"
    history.attrs["reference_year"] = reference_year
    return history


def build_prepared_tracer_directory(context: HoltenContext, reference_year: float | None = None) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    context.paths.prepared_tracer_dir.mkdir(parents=True, exist_ok=True)
    for tracer_name in context.calibration_tracers:
        tracer_cfg = validate_local_tracer_yaml(tracer_name, context)
        out_dir = context.paths.prepared_tracer_dir / tracer_name
        out_dir.mkdir(parents=True, exist_ok=True)

        if tracer_name == "3H":
            history = _prepare_3h_history(tracer_cfg, context)
        elif tracer_name == "kr85":
            history = _prepare_kr85_history(tracer_cfg, context)
        elif tracer_name == "39Ar":
            if reference_year is None:
                raise ValueError("39Ar preparation requires a sampling reference year")
            history = _prepare_39ar_history(tracer_cfg, reference_year)
        else:
            raise ValueError(f"Unsupported Holten tracer: {tracer_name}")

        flattened = {
            key: tracer_cfg[key]
            for key in ("unit", "recharge", "recharge_constant", "decay_time", "production_rate", "datemin", "datemax")
            if key in tracer_cfg
        }
        with (out_dir / f"{tracer_name}.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(flattened, handle, sort_keys=False)
        if bool(flattened.get("recharge", False)):
            history[["date", "concentration"]].to_csv(out_dir / "recharge.csv", index=False)
        histories[tracer_name] = history
    return histories


def convert_3h_record(row: pd.Series) -> dict[str, Any]:
    return {
        "element": "3H",
        "concentration": float(row["3H_TU"]),
        "error": float(row["3H_err"]),
        "unit": "TU",
        "date": float(row["Date_decimal"]),
    }


def convert_kr85_record(row: pd.Series) -> dict[str, Any]:
    return {
        "element": "kr85",
        "concentration": float(row["Kr85_dpm_ccKr"]),
        "error": float(row["Kr85_err"]),
        "unit": "dpm/ccKr",
        "date": float(row["Date_decimal"]),
    }


def convert_39ar_record(row: pd.Series) -> dict[str, Any]:
    return {
        "element": "39Ar",
        "concentration": float(row["Ar39_pMC"]) / 100.0,
        "error": float(row["Ar39_err"]) / 100.0,
        "unit": "%modern",
        "date": float(row["Date_decimal"]),
    }


def convert_sampling_observations(frame: pd.DataFrame, context: HoltenContext) -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[dict[str, Any]] = []
    prep_log: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        well_id = str(row["ID"])
        conversions = [
            ("3H", "3H_TU", "TU", "3H_err", convert_3h_record(row), "none"),
            ("kr85", "Kr85_dpm_ccKr", "dpm/ccKr", "Kr85_err", convert_kr85_record(row), "none"),
            ("39Ar", "Ar39_pMC", "pMC", "Ar39_err", convert_39ar_record(row), "pMC / 100"),
        ]
        for element, source_field, raw_unit, err_field, converted, rule in conversions:
            raw_value = row[source_field]
            raw_error = row[err_field]
            if _is_missing(raw_value) or _is_missing(raw_error):
                raise ValueError(f"Missing required value for well {well_id}, tracer {element}")
            record = {"well_id": well_id, **converted}
            records.append(record)
            prep_log.append(
                {
                    "well_id": well_id,
                    "element": element,
                    "raw_value": float(raw_value),
                    "raw_unit": raw_unit,
                    "converted_value": float(converted["concentration"]),
                    "converted_unit": converted["unit"],
                    "conversion_rule": rule,
                    "source_field": source_field,
                }
            )
    aggregated = pd.DataFrame.from_records(records)
    preparation_log = pd.DataFrame.from_records(prep_log)
    validate_converted_dataset(aggregated, context.selected_wells, aggregated_file=True)
    return aggregated, preparation_log


def validate_converted_dataset(frame: pd.DataFrame, selected_wells: list[str], aggregated_file: bool) -> None:
    required = ["element", "concentration", "error", "unit", "date"]
    if aggregated_file:
        required = ["well_id", *required]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Converted dataset missing columns: {missing}")

    expected_elements = set(VALID_TRACERS)
    if set(frame["element"]) != expected_elements:
        raise ValueError(f"Unexpected tracer set: {sorted(set(frame['element']))}")
    if frame["concentration"].isna().any() or frame["error"].isna().any():
        raise ValueError("Converted dataset contains missing numeric values")
    if (frame["error"].astype(float) <= 0).any():
        raise ValueError("Converted dataset contains non-positive errors")
    if (frame["concentration"].astype(float) < 0).any():
        raise ValueError("Converted dataset contains negative concentrations")
    if frame.loc[frame["element"] == "39Ar", "concentration"].astype(float).max() > 10:
        raise ValueError("39Ar values appear to still be in pMC, not fraction of modern")

    for element, expected_unit in TRACER_OUTPUT_UNITS.items():
        got = frame.loc[frame["element"] == element, "unit"].iloc[0]
        if got != expected_unit:
            raise ValueError(f"Unexpected unit for {element}: {got} != {expected_unit}")

    dates = frame["date"].astype(float)
    if not ((dates >= 2010.0) & (dates < 2011.0)).all():
        raise ValueError("Converted dataset contains dates outside the 2010 campaign")

    if aggregated_file:
        allowed_wells = set(selected_wells)
        unexpected_wells = sorted(set(frame["well_id"]).difference(allowed_wells))
        if unexpected_wells:
            raise ValueError(f"Unexpected wells in aggregated dataset: {unexpected_wells}")
        if frame.duplicated(["well_id", "element", "date"]).any():
            raise ValueError("Duplicate well_id/element/date rows in aggregated dataset")
        if len(frame) != len(selected_wells) * len(VALID_TRACERS):
            raise ValueError("Aggregated dataset does not contain exactly 9 V1 rows")
    else:
        if frame.duplicated(["element", "date"]).any():
            raise ValueError("Duplicate element/date rows in per-well dataset")
        if len(frame) != len(VALID_TRACERS):
            raise ValueError("Per-well dataset must contain exactly 3 V1 rows")


def write_aggregated_dataset(frame: pd.DataFrame, context: HoltenContext) -> Path:
    context.paths.data_dir.mkdir(parents=True, exist_ok=True)
    ordered = frame[["well_id", "element", "concentration", "error", "unit", "date"]].copy()
    order_map = {"3H": 0, "kr85": 1, "39Ar": 2}
    ordered["_element_order"] = ordered["element"].map(order_map)
    ordered = ordered.sort_values(["well_id", "date", "_element_order"]).reset_index(drop=True)
    ordered = ordered.drop(columns="_element_order")
    ordered.to_csv(context.paths.aggregated_dataset_path, sep="\t", index=False)
    return context.paths.aggregated_dataset_path


def write_per_well_files(frame: pd.DataFrame, context: HoltenContext) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for well_id, group in frame.groupby("well_id"):
        payload = group[["element", "concentration", "error", "unit", "date"]].copy()
        validate_converted_dataset(payload, [well_id], aggregated_file=False)
        out_path = context.paths.data_dir / f"holten_2010_{well_id}.txt"
        payload.to_csv(out_path, sep="\t", index=False)
        paths[well_id] = out_path
    return paths


def prepare_holten_inputs(config_path: Path | None = None) -> PreparedHoltenCase:
    context = build_context(config_path)
    context.paths.data_dir.mkdir(parents=True, exist_ok=True)
    context.paths.generated_dir.mkdir(parents=True, exist_ok=True)

    sampling_raw = read_sampling_table(context)
    selected = select_v1_wells(sampling_raw, context.selected_wells)
    reference_year = float(selected["Date_decimal_exact"].median())
    tracer_histories = build_prepared_tracer_directory(context, reference_year=reference_year)
    observed_aggregated, preparation_log = convert_sampling_observations(selected, context)
    write_aggregated_dataset(observed_aggregated, context)
    write_per_well_files(observed_aggregated, context)

    observed_by_well: dict[str, pd.DataFrame] = {}
    for well_id, group in observed_aggregated.groupby("well_id"):
        observed_by_well[well_id] = group[["element", "concentration", "error", "unit", "date"]].copy().reset_index(drop=True)

    return PreparedHoltenCase(
        context=context,
        sampling_raw=sampling_raw,
        observed_aggregated=observed_aggregated,
        observed_by_well=observed_by_well,
        tracer_histories=tracer_histories,
        preparation_log=preparation_log,
    )
