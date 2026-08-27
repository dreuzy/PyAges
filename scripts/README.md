# Scripts

Quick entrypoints for manual runs and sanity checks. These are **not** pytest
tests; they are intended for interactive use when validating workflows.

## Common usage

Activate the environment first:

```bash
conda activate pyages
```

Then run a script from the repository root, for example:

```bash
pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
pyages run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
pyages run examples/templates/quickstart_single.yaml
pyages run --transient examples/templates/quickstart_temporal.yaml
python -m scripts.run_system_check
python -m scripts.run_system_check --params configs/system_check.yaml
python -m scripts.run_calibration_benchmark
```

### Example parameters

Single-date workflows (YAML-driven):

```bash
pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
python -m examples.natural.holten.run_holten
```

Temporal workflows (multi-date concentrations):

```bash
pyages run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
```

## Output location

Results are written under the configured results root. By default:

```
<home>/results/PyAges
```

You can override this with `PYAGES_RESULTS_DIR` (see the root `README.md`).

## Script overview

### Complete article reproduction

Use an output directory outside the repository:

```powershell
python -m scripts.reproduce_article preflight --output C:\pyages-runs\article-v1
python -m scripts.reproduce_article resume --output C:\pyages-runs\article-v1 --workers 6
python -m scripts.reproduce_article validate --output C:\pyages-runs\article-v1
```

The workflow covers the independent forward cases, paired TracerLPM/Excel
robustness campaign, shifted-exponential, Holten and Ploemeur campaigns,
physical-IG conditioning, publication package, and hash-validated core archive.
The Holten--Dirichlet prior-sensitivity case is included as a distinct robustness
stage. `resume` reuses validated stages and individual chain/shard
outputs. `validate` checks the fresh campaign manifest, expected stage files,
package hashes, and archive hashes. Canonical runs require a clean Git worktree;
`--allow-dirty` is intended only for development checks.

`python article/run_case.py check <case>` has a different purpose: it audits
the optional historical `results/` inventory. Its result must not be used as
the verdict for a fresh campaign.

- `pyages run`
  Canonical single-date workflow (systematic sampling + calibration) driven by YAML.
- `pyages.workflows.temporal`
  Canonical multi-date Metropolis-Hastings workflow, exposed by the CLI.
- `run_system_check.py`
  Lightweight end-to-end sanity check (LPM generation, tracers, and plotting).
- `run_calibration_benchmark.py`
  Compare Metropolis-Hastings and forward-uncertainty quantification runs.

Windows-only wrappers are grouped under `scripts/windows/`. The core entry
point is `reproduce_article.bat OUTPUT_DIRECTORY`; per-campaign wrappers remain
available for focused diagnostics.

---

## Add a New Data File (choose LPM + tracers)

1) Put your data file under a folder you control (e.g. `examples/my_site/data/`).
   The file must contain columns: `element`, `concentration`, `error`, `unit`, `date`.

2) Choose an LPM model with parameters in `data_core/data_lpm/<model>/params.yaml`.

3) Create a YAML config and run the launcher:

```bash
pyages run examples/my_site/my_config.yaml
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
pyages run --transient examples/my_site/my_temporal.yaml
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
pyages new lpm <name> --base scipy
pyages new tracer <name> [--with-decay] [--no-chronicle]
```

Run `pyages new lpm --help` or `pyages new tracer --help` for the complete
options. Complete the scientific definitions in the generated templates, then
validate the installation with `pyages check`.

---

## Expected outputs

- Single-date workflow (`pyages run`)
  - Results under: `<results_root>/test_cases/<dataset_name>/`
  - Core calibration outputs:
    - `parameters_calibration.txt`
    - `results_calibration.txt`
    - `lpm_dist_calibrated.txt`
    - `lpm_histo_calibrated.txt`
    - `lpm_stats_calibrated.txt`
  - Plots/tables from concentration time displays, including:
    - `Metropolis_Hastings/concentration_times.png`
    - `Metropolis_Hastings/concentrations_all_models.txt`
    - equivalent files below `forward_uncertainty_quantification/` when that
      method is enabled
- `pyages run --transient`
  - Results under:
    `<results_root>/<study_name>/<dataset_stem>/<mode>/<span_full-or-date>/<lpm_type>/`
    (`study_name` defaults to `temporal`)
  - Core outputs:
    - `parameters_calibration.txt`
    - `results_calibration.txt`
    - `lpm_stats_calibrated.txt`
    - `Metropolis_Hastings/concentration_times.png`
    - `Metropolis_Hastings/concentrations_all_models.txt`
    - `Metropolis_Hastings/distributions.txt`
    - `Metropolis_Hastings/distributions_stats.txt`
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
  Check the `PYAGES_RESULTS_DIR` environment variable. If unset, results go to
  `<home>/results/PyAges`.

- **`ModuleNotFoundError: pyages`**
  Install the project once with `pip install -e .`, then use `pyages` or
  `python -m ...` entry points.

- **`FileNotFoundError` for data files**  
  Verify the YAML paths and that example datasets are present under
  `examples/<site>/data/`.
