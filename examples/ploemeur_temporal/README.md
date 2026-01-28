# Ploemeur temporal example

Quick run:

```
python scripts/launcher_temporal.py --params examples/ploemeur_temporal/ploemeur_temporal.yaml
```

What it does:
- Runs Metropolis-Hastings on a multi-date concentration file (ori_*.txt).
- Supports two modes:
  - `span`: single calibration over the full time span
  - `successive`: one calibration per observation date
- Produces temporal figures and distribution figures, plus calibration files.

Outputs:
- Stored under the default results root (`PYAGE_RESULTS_DIR`) unless overridden
  in the YAML.

Tests:
- `tests/concentrations/test_concentration_chronicles_smoke.py` reads
  `examples/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt` as its
  input dataset.
