# Ploemeur temporal example

Quick run:

```bash
python examples/natural/ploemeur_temporal/run_ploemeur_temporal.py
```

What it does:
- loads the multi-date `F09` concentration record,
- runs Metropolis-Hastings in one of two temporal modes:
  - `span`: one calibration over the full observation window,
  - `successive`: one calibration per observation date,
- writes a compact reading order first:
  - `00_observations_overview.png`,
  - one `Metropolis_Hastings/concentration_times.png` per LPM,
  - one `parameter_summary.png` per LPM,
- still writes calibrated parameter tables and posterior distributions,
- only generates `concentrations2D_*.png` when
  `figures.concentrations_2d: true`.

Notebook:

- `examples/natural/ploemeur_temporal/exemple_ploemeur_temporal.ipynb`
  follows the same guided structure as the single-date `ploemeur` example,
  but keeps the temporal reading order and the `span` / `successive` split.
- the notebook also rebuilds comparative views between the transient and
  single-date calibrations for `exp_shifted` and `ig_shifted`:
  temporal fit overlays and parameter distribution overlays.

Outputs:
- stored under the default results root (`PYAGE_RESULTS_DIR`) unless overridden
  in the YAML,
- `span` mode writes to
  `.../ploemeur_temporal/<dataset_stem>/span/span_full/`,
- `successive` mode writes to
  `.../ploemeur_temporal/<dataset_stem>/successive/date_<yyyy_xxxxxx>/`.

Tests:
- `tests/ploemeur/test_ploemeur_temporal_golden.py` checks the calibrated
  parameter statistics in `span` mode.
- `tests/concentrations/test_concentration_chronicles_smoke.py` reads
  `examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt` as its
  input dataset.
