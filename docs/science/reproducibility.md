# Article Reproducibility Layer

The versioned `article/` directory maps manuscript sections to executable
cases without copying the scientific code or distributed inputs. Its
machine-readable registry is `article/cases.yaml`; each case has a manifest
recording its historical inputs, outputs, checksums, environment, and seeds.

## Safe interface

The canonical whole-article interface writes every generated file outside the
Git checkout and records resumable stage status:

```powershell
python -m scripts.reproduce_article preflight --output C:\pyage-runs\article-v1
python -m scripts.reproduce_article resume --output C:\pyage-runs\article-v1 --workers 6
python -m scripts.reproduce_article status --output C:\pyage-runs\article-v1
```

On Windows, the equivalent wrapper is
`scripts\windows\reproduce_article.bat C:\pyage-runs\article-v1`. The default
sequence recalculates the independent forward benchmark, the paired
PyAge/TracerLPM robustness campaign, all MCMC campaigns, the editorial package,
and the complete GMD archive. A failed command can be resumed without accepting
a missing expected artifact as a completed stage. Canonical runs require a
clean Git worktree.

From the repository root:

```powershell
python article/run_case.py list
python article/run_case.py check s3_2_shifted_exponential
python article/run_case.py postprocess s3_2_shifted_exponential
python article/run_case.py run s3_2_shifted_exponential
```

- `check` verifies paths and recorded provenance without running scientific
  calculations.
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

| Case ID | Scientific role | Versioned status |
|---|---|---|
| `s3_forward_verification` | Independent forward verification | `final` |
| `s3_1_tracerlpm` | Cross-software PyAge/TracerLPM benchmark | `partial` |
| `s3_2_shifted_exponential` | Bayesian uncertainty and identifiability | `final` |
| `s4_1_holten` | Holten four-bin benchmark | `final` |
| `s4_2_ploemeur` | Ploemeur full-record/window comparison | `final` |
| `holten_prior_dirichlet1` | Prior-sensitivity experiment completed in a separate workstream but not yet imported or checked here | `unvalidated` |

The stabilized whole-article workflow no longer consumes historical result
directories. Its scientific inputs are versioned data/configuration files and
the locally hash-qualified TracerLPM components. Historical outputs may be
compared separately, but are not initial states, priors, gates, or required
files for the new campaign.

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

For `holten_prior_dirichlet1`, `check` currently reports missing chains,
pilots, and historical manifest plus a runner checksum mismatch. Unit tests can
qualify the Jacobian implementation, but they cannot validate the manuscript's
reported posterior-sensitivity result. The campaign has reportedly been run
elsewhere, so the next action is evidence integration and independent review,
not an automatic duplicate calculation.

The manuscript archive is intended to freeze the complete inputs, machine-
readable results, figures, tables, environment, and provenance metadata for
the published release. Until that immutable archive and DOI exist, the Git tag
and case manifests identify the code and expected evidence, but they do not by
themselves make absent numerical results auditable.

“PyAge v1.0” is currently a manuscript target rather than the released package
version. The beta/software/DOI identity rules and the future archive sequence
are maintained in {doc}`../dev/versioning-citation`.
