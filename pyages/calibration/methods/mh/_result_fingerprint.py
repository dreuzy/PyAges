# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file fingerprints the scientific state and stored results of MH runs.

"""Detect changes to MH pilot data, model interpretation, and chain tables.

Metadata is converted to a recursively ordered JSON representation, while
floating-point arrays are normalized to a fixed byte order before hashing. A
sample template fingerprint covers the LPM class, calibration ranges, domains, units,
moments, fixed scientific state, and concentration columns independently of the
sampled rows.

Table fingerprints add column types, index, and row contents; pilot fingerprints
include every field and array reused by production. These digests establish
integrity and reproducibility but are not intended as authentication signatures.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

import numpy as np
import pandas as pd

from pyages.lpm.samples.table import LpmSampleTable


def snapshot_json_value(value: Any) -> Any:
    """Return a deterministic JSON-compatible value for integrity snapshots."""
    if isinstance(value, Mapping):
        return {
            str(name): snapshot_json_value(item)
            for name, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, np.ndarray):
        return snapshot_json_value(value.tolist())
    if isinstance(value, (tuple, list)):
        return [snapshot_json_value(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def pilot_result_sha256(pilot: Any) -> str:
    """Fingerprint every pilot field used for production provenance."""
    payload = {
        "final_states": pilot.final_states,
        "proposal_multiplier": pilot.proposal_multiplier,
        "acceptance_rates": pilot.acceptance_rates,
        "retained_counts": pilot.retained_counts,
        "initial_states": pilot.initial_states,
        "runtime_seconds": pilot.runtime_seconds,
    }
    digest = sha256(
        json.dumps(
            snapshot_json_value(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    arrays = (pilot.covariance,) + (() if pilot.samples is None else pilot.samples)
    for values in arrays:
        canonical = np.ascontiguousarray(values, dtype="<f8")
        digest.update(repr(canonical.shape).encode("ascii"))
        digest.update(b"\0")
        digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def _template_payload(samples: LpmSampleTable) -> dict[str, Any]:
    template = samples.lpm_template
    parameter_names = tuple(samples.get_param_names())
    return {
        "class": f"{type(template).__module__}.{type(template).__qualname__}",
        "name": str(template.name),
        "parameters": [
            {
                "name": name,
                "minimum": float(template.get_calibration_range(name)[0]),
                "maximum": float(template.get_calibration_range(name)[1]),
                "domain": repr(template.get_parameter_domain(name)),
                "unit": str(template.parameter_units[name]),
            }
            for name in parameter_names
        ],
        "moments": template.moments_name(),
        "fixed_scientific_state": template.fixed_scientific_state(),
        "concentrations": samples.get_concentration_names(),
    }


def sample_template_sha256(samples: LpmSampleTable) -> str:
    """Fingerprint the scientific model contract independently of sample rows."""
    return sha256(
        json.dumps(
            snapshot_json_value(_template_payload(samples)),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def sample_table_sha256(samples: LpmSampleTable) -> str:
    """Fingerprint one chain table and its complete interpretation schema."""
    samples.validate()
    frame = samples.frame
    model_payload = {
        **_template_payload(samples),
        "columns": [str(column) for column in frame.columns],
        "dtypes": [str(dtype) for dtype in frame.dtypes],
    }
    digest = sha256(
        json.dumps(
            snapshot_json_value(model_payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    hashed_rows = pd.util.hash_pandas_object(frame, index=True, categorize=False)
    digest.update(hashed_rows.to_numpy(dtype=np.uint64, copy=False).tobytes())
    return digest.hexdigest()


__all__ = ["pilot_result_sha256", "sample_table_sha256", "sample_template_sha256"]
