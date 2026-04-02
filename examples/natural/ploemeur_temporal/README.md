# Ploemeur temporal example

Quick run:

```
python scripts/launcher_temporal.py --params examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
```

What it does:
- Runs Metropolis-Hastings on a multi-date concentration file (ori_*.txt).
- Supports two modes:
  - `span`: single calibration over the full time span
  - `successive`: one calibration per observation date
- Produces a compact figure set first:
  - `00_observations_overview.png`
  - one `concentration_times.png` per LPM
  - one `parameter_summary.png` per LPM
- Still writes calibration tables and distribution files in the same folders.
- The optional 2D concentration pair plots are only generated when
  `figures.concentrations_2d: true`.

Outputs:
- Stored under the default results root (`PYAGE_RESULTS_DIR`) unless overridden
  in the YAML.

Tests:
- `tests/concentrations/test_concentration_chronicles_smoke.py` reads
  `examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt` as its
  input dataset.
