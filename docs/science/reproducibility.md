# Article Reproducibility Layer

The versioned `article/` directory maps manuscript sections to executable
cases without copying the scientific code or distributed inputs. Its
machine-readable registry is `article/cases.yaml`; each case has a manifest
recording its historical inputs, outputs, checksums, environment, and seeds.

## Two evidence layers

The case manifests under `article/` describe the optional historical evidence
inventory. They must remain unchanged because their paths and checksums identify
the older calculations. `article/run_case.py check` reports whether that exact
inventory is locally available; it is not the release gate for a fresh run.

The complete campaign writes every generated file outside the Git
checkout and records resumable stage status. Its own validator is the canonical
technical gate for the fresh evidence:

```powershell
$env:PYTHONNOUSERSITE = "1"
python -m scripts.reproduce_article preflight --output C:\pyages-runs\article-1.0
python -m scripts.reproduce_article resume --output C:\pyages-runs\article-1.0 --workers 6
python -m scripts.reproduce_article status --output C:\pyages-runs\article-1.0
python -m scripts.reproduce_article validate --output C:\pyages-runs\article-1.0
```

The canonical launch is accepted only from the qualified direct environment,
a clean worktree, and a commit carrying the exact annotated tag `1.0`. The
preflight checks the direct versions in `install/environment.yml`, the source
and installed PyAges versions, the tag at `HEAD`, versioned inputs, and the
hash-qualified TracerLPM dependencies. It also refuses a Python process whose
per-user package directory is enabled, because that directory can shadow the
qualified environment. `--allow-dirty` and `--allow-untagged` exist for
development diagnostics only and invalidate the final-release route.

On Windows, the equivalent wrapper is
`scripts\windows\reproduce_article.bat C:\pyages-runs\article-1.0`. The wrapper
sets `PYTHONNOUSERSITE=1` automatically. The default
sequence recalculates the independent forward benchmark, the paired
PyAges/TracerLPM robustness campaign, the stabilized shifted-exponential,
Holten H4 and Ploemeur MCMC campaigns, the distinct Holten--Dirichlet
prior-sensitivity case, the editorial package, and the complete GMD archive.
A failed command can be resumed without accepting a
missing expected artifact as a completed stage. Canonical runs require a clean
Git worktree.

From the repository root:

```powershell
python article/run_case.py list
python article/run_case.py check s3_2_shifted_exponential
python article/run_case.py postprocess s3_2_shifted_exponential
python article/run_case.py run s3_2_shifted_exponential
```

- `check` verifies paths and recorded provenance for the optional historical
  inventory without running scientific calculations. A 0/6 result means that
  old evidence is unavailable locally; it says nothing about the status of a
  fresh external campaign.
- `postprocess` requires existing raw outputs and does not create or extend
  MCMC chains.
- `run` is the only action that launches the full calculation. It writes to a
  new timestamped reproduction directory and does not overwrite canonical
  historical results.

The TracerLPM/Excel case requires Windows, Excel, the qualified four-tracer
workbook and the TracerLPM XLL. The preflight verifies their paths and SHA-256
digests. The runner then uses a campaign-local configuration and output tree;
neither the workbook nor generated evidence is written into the repository.

## Case map

| Case ID | Scientific role | Historical registry status |
|---|---|---|
| `s3_forward_verification` | Independent forward verification | `final` |
| `s3_1_tracerlpm` | Cross-software PyAges/TracerLPM benchmark | `partial` |
| `s3_2_shifted_exponential` | Bayesian uncertainty and identifiability | `final` |
| `s4_1_holten` | Holten four-bin benchmark | `final` |
| `s4_2_ploemeur` | Ploemeur full-record/window comparison | `final` |
| `holten_prior_dirichlet1` | Distinct Holten prior-sensitivity experiment included in the fresh campaign | `complete-sensitivity` |

The stabilized core workflow no longer consumes historical result
directories. Its scientific inputs are versioned data/configuration files and
the locally hash-qualified TracerLPM components. Historical outputs may be
compared separately, but are not initial states, priors, gates, or required
files for the new campaign.

The dated {doc}`../reports/reproduction_campaign_status_2026-08-27` report
records the current observed state. The historical inventory is available for
0/6 cases in this checkout, while the fresh external campaign validates all
9/9 recorded stages, 87 package artifacts, and 3,046 archived files. This is a
structure-and-checksum result; scientific qualification remains explicit in
each stage output. The archived 270-case forward summary retains its original
`measured_not_yet_qualified` status. The subsequently versioned two-regime
contract qualifies 270/270 cases at the default grid and at the 0.5× and 0.25×
grids; see {doc}`../reports/forward_qualification_2026-08-27`. A clean future
campaign must integrate that verdict instead of rewriting the archived summary.

## What is versioned where

The evidence behind the manuscript must be frozen and version-identifiable,
but large numerical results do not have to be committed to Git. The two layers
have different roles:

- Git tracks source code, configurations, distributed inputs permitted by their
  licences, case manifests, small reference reports, and the exact pointer to
  the scientific archive.
- The immutable scientific archive stores every result needed to recalculate a
  published figure, table, residual, interval, or convergence claim. For MCMC
  cases this includes lossless per-chain retained states (including repeated
  states after rejection), chain identifiers, seeds, initial states, proposal
  settings, acceptance rates, diagnostics, and derived quantities.
- The archive manifest records the archive version or DOI, permanent URL,
  filenames, byte sizes, SHA-256 digests, source commit and tag, environment,
  licences, and the relationship between raw evidence and publication files.

Caches, temporary exports, superseded exploratory runs, and duplicate rendered
files that support no published claim are not required. If raw chains and the
smaller editorial package are deposited separately, the editorial manifest
must identify every archive part by immutable URL, size, and SHA-256. A mutable
cloud folder or an unversioned local `results/` directory is not an archive.

For `holten_prior_dirichlet1`, the historical `check` currently reports missing
chains, pilots, and historical manifest plus a runner checksum mismatch. Unit
tests can qualify the Jacobian implementation, but they cannot validate the
manuscript's reported posterior-sensitivity result. The campaign has reportedly
been run elsewhere, so the next action is evidence integration and independent review,
not an automatic duplicate calculation.

The local core archive is hash-valid, but it is not yet an immutable external
deposit. The publication archive is intended to freeze the in-scope inputs,
machine-readable results, figures, tables, environment, per-stage source
revisions, and provenance metadata for the published release. Until that
external archive and DOI exist, the local archive, Git revisions, and case
manifests provide traceability but not a permanent deposit.

## Final Zenodo bundle

The complete campaign ends with the core archive
`C:\pyages-runs\article-v1-gmd-archive`. After reserving the Zenodo DOI, build
the uploadable reader bundle without rerunning simulations:

```powershell
python -m scripts.build_zenodo_bundle `
  --archive C:\pyages-runs\article-v1-gmd-archive `
  --output C:\pyages-runs\pyages-1.0-zenodo `
  --zip-output C:\pyages-runs\pyages-1.0-zenodo.zip `
  --tracerlpm-workbook C:\TracerLPM-Test\working\TracerLPM_V_1_0_FourTracers_v17.xlsm `
  --tracerlpm-xll C:\Users\dreuzy\AppData\Roaming\Microsoft\AddIns\TracerLPMfunctions_64_v_1.xll `
  --doi 10.5281/zenodo.REPLACE_WITH_RESERVED_ID
```

Add `--article-doi` when the GMD article or preprint DOI is known. For a local
metadata review before DOI reservation, use `--draft`; the final command
refuses a missing DOI. Validate the directory and ZIP together with:

```powershell
python -m scripts.build_zenodo_bundle `
  --validate-only C:\pyages-runs\pyages-1.0-zenodo `
  --zip-output C:\pyages-runs\pyages-1.0-zenodo.zip
```

The source tree carries the prepared `1.0` identity. It becomes the released
version only when tag `1.0`, its commit, the validated archive, and the Zenodo
record agree. The full identity and DOI rules are maintained in
{doc}`../dev/versioning-citation`.
