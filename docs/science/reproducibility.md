# Article Reproducibility Layer

The versioned `article/` directory maps manuscript sections to executable
cases without copying the scientific code or distributed inputs. Its
machine-readable registry is `article/cases.yaml`; each case has a manifest
recording its historical inputs, outputs, checksums, environment, and seeds.

## Safe interface

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

The TracerLPM/Excel case cannot be reproduced portably without the qualified
external installation. Its versioned case therefore remains explicitly
partial even though the manuscript records the completed paired campaign.

## Case map

| Case ID | Scientific role | Versioned status |
|---|---|---|
| `s3_forward_verification` | Independent forward verification | `final` |
| `s3_1_tracerlpm` | Cross-software PyAge/TracerLPM benchmark | `partial` |
| `s3_2_shifted_exponential` | Bayesian uncertainty and identifiability | `final` |
| `s4_1_holten` | Holten four-bin benchmark | `final` |
| `s4_2_ploemeur` | Ploemeur full-record/window comparison | `final` |
| `holten_prior_dirichlet1` | Prior-sensitivity experiment | `unvalidated` |

Results under `results/` are deliberately ignored by Git and may be absent
from a source checkout. A missing result directory is therefore different from
a missing manifest. Historical checksum differences after code evolution must
be reported, not hidden by rewriting an old manifest.

The manuscript archive is intended to freeze the complete inputs, machine-
readable results, figures, tables, environment, and provenance metadata for
the published release. Until that immutable archive and DOI exist, the Git tag
and case manifests are the authoritative versioned references.

“PyAge v1.0” is currently a manuscript target rather than the released package
version. The beta/software/DOI identity rules and the future archive sequence
are maintained in {doc}`../dev/versioning-citation`.
