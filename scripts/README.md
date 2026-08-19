# Scripts

Quick entrypoints for manual runs and sanity checks. These are **not** pytest
tests; they are intended for interactive use when validating workflows.

## Common usage

Activate the environment first:

```bash
conda activate pyage
```

Then run a script from the repository root, for example:

```bash
pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
pyage run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
pyage run examples/templates/quickstart_single.yaml
pyage run --transient examples/templates/quickstart_temporal.yaml
python -m scripts.run_system_check
python -m scripts.run_system_check --params configs/system_check.yaml
python -m scripts.run_calibration_benchmark
```

### Example parameters

Single-date workflows (YAML-driven):

```bash
pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
pyage run examples/natural/fontainebleau/exemple_fontainebleau.yaml
python -m examples.natural.fontainebleau.run_fontainebleau
python -m examples.natural.holten.run_holten
```

Temporal workflows (multi-date concentrations):

```bash
pyage run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
```

## Output location

Results are written under the configured results root. By default:

```
<home>/results/PyAge
```

You can override this with `PYAGE_RESULTS_DIR` (see the root `README.md`).

## Script overview

- `pyage run`
  Canonical single-date workflow (systematic sampling + calibration) driven by YAML.
- `pyage.workflows.temporal`
  Canonical multi-date Metropolis-Hastings workflow, exposed by the CLI.
- `run_system_check.py`
  Lightweight end-to-end sanity check (LPM generation, tracers, and plotting).
- `run_calibration_benchmark.py`
  Compare Metropolis-Hastings and forward-uncertainty quantification runs.

---

## Add a New Data File (choose LPM + tracers)

1) Put your data file under a folder you control (e.g. `examples/my_site/data/`).
   The file must contain columns: `element`, `concentration`, `error`, `unit`, `date`.

2) Choose an LPM model with parameters in `data_core/data_lpm/<model>/params.yaml`.

3) Create a YAML config and run the launcher:

```bash
pyage run examples/my_site/my_config.yaml
```

Minimal YAML:
```yaml
dataset:
  name: my_site_2010.txt
  year: 2010
  data_dir: examples/my_site/data

lpm:
  model_name: exp_shifted
  data_directory: data_core/data_lpm
```

4) If the data contains multiple dates, use the temporal workflow:

```bash
pyage run --transient examples/my_site/my_temporal.yaml
```

```yaml
dataset:
  file: examples/my_site/data/ori_my_site_2005_2024.txt
  error_rel: 0.2

lpm_models:
  list: ["exp_shifted", "ig"]
  directory: data_core/data_lpm

workflow:
  mode: span
```

5) Tracer names come from the `element` column. If you need new tracers,
   add them under `data_core/data_tracer/<tracer>/` (see `docs/user-guide/adding-tracer.md`).

---

## Creating New Components

Use the canonical CLI generators:

```bash
pyage new lpm <name> --base scipy
pyage new tracer <name> [--with-decay] [--no-chronicle]
```

Run `pyage new lpm --help` or `pyage new tracer --help` for the complete
options. Complete the scientific definitions in the generated templates, then
validate the installation with `pyage check`.

---

## Expected outputs

- Single-date workflow (`pyage run`)
  - Results under: `<results_root>/test_cases/<dataset_name>/`
  - Core calibration outputs:
    - `parameters_calibration.txt`
    - `results_calibration.txt`
    - `lpm_dist_calibrated.txt`
    - `lpm_histo_calibrated.txt`
    - `lpm_stats_calibrated.txt`
  - Plots/tables from concentration time displays, including:
    - `concentration_times.png`
    - `concentrations_all_models.txt`
- `pyage run --transient`
  - Results under:
    `<results_root>/ploemeur_temporal/<dataset_stem>/<mode>/<date>/<lpm_type>/`
  - Core outputs:
    - `parameters_calibration.txt`
    - `results_calibration.txt`
    - `lpm_stats_calibrated.txt`
    - `concentration_times.png`
    - `concentrations_all_models.txt`
    - `distributions.txt`
    - `distributions_stats.txt`
- `run_system_check.py`
  - Results under: `<results_root>/test/<check_name>/<timestamp>/`
  - Diagnostic plots + console summaries of generated models/tracers.
  - Optional config override: `python -m scripts.run_system_check --params <file.yaml>`
- `run_calibration_benchmark.py`
  - Results under:
    `<results_root>/test_calib_comp/<timestamp>/prec_<error>/<tracers>/<lpm>/<case>/`
  - Benchmark results comparing MH and FUQ runs (plots + tables).

## Troubleshooting

- **No figures appear**  
  Ensure the script enables plotting in the params and that your backend is
  available (e.g., run from a local session, not a headless environment).

- **Results are not written where expected**  
  Check the `PYAGE_RESULTS_DIR` environment variable. If unset, results go to
  `<home>/results/PyAge`.

- **`ModuleNotFoundError: pyage`**
  Install the project once with `pip install -e .`, then use `pyage` or
  `python -m ...` entry points.

- **`FileNotFoundError` for data files**  
  Verify the YAML paths and that example datasets are present under
  `examples/<site>/data/`.
