# Multi-chain MH qualification record — 2026-08-31

**Status:** consolidated four-profile qualification record with a completed
local integrated campaign. The profile-level protocols and descriptive metrics
below are taken from the versioned executable qualifications and their
maintained case pages. The exact aggregate results observed on the final
development worktree are recorded in {ref}`multichain-final-campaign`; clean
commit and release-tag evidence remain separate CI and release gates.

## Qualification decision and scope

The multi-chain Metropolis--Hastings workflow has four registered scientific
qualification profiles:

1. single-date recovery from a synthetic shifted-exponential realization with
   known generating parameters;
2. single-date Ploemeur F09 2010 inference with the shifted-exponential LPM and
   no informative parameter prior;
3. single-date Ploemeur F09 2010 inference with a three-parameter shifted
   inverse-Gaussian LPM and its registered parametric prior active;
4. temporal Ploemeur F09 inference over 58 observations and 20 dates with the
   shifted-exponential LPM and registered parametric priors.

Together, these profiles exercise known-truth recovery, two- and
three-parameter targets, inactive and active parametric priors, single-date and
temporal workflows, pilot adaptation, independent production chains,
convergence rejection, serialization, and terminal manifests. Qualification is
limited to the fixed targets, seeds, schedules, and inequalities documented
below. It is not a claim of universal MCMC performance, model identifiability,
or hydrogeological validity.

## Reproduction inputs

| Profile | Canonical configuration | Executable qualification | Detailed record |
|---|---|---|---|
| Synthetic known truth | `examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml` | `tests/examples/test_synthetic_recovery_multichain_scientific.py` | {doc}`../examples/synthetic-recovery` |
| Ploemeur F09 `exp_shifted` | `examples/natural/ploemeur/exemple_ploemeur_multichain.yaml` | `tests/examples/test_ploemeur_multichain_scientific.py` | {doc}`../examples/ploemeur-multichain` |
| Ploemeur F09 `ig_shifted`, prior active | `examples/natural/ploemeur/exemple_ploemeur_ig_shifted_prior_multichain.yaml` | `tests/examples/test_ploemeur_ig_shifted_prior_multichain_scientific.py` | {doc}`../examples/ploemeur-ig-shifted-prior-multichain` |
| Ploemeur temporal `exp_shifted` | `examples/natural/ploemeur_temporal/ploemeur_temporal_multichain.yaml` | `tests/examples/test_ploemeur_temporal_multichain_scientific.py` | {doc}`../examples/ploemeur-temporal-multichain` |

Run the four qualifications from the source revision that contains these
Unreleased profiles:

```bash
python -m pytest -q --run-extensive tests/examples/test_synthetic_recovery_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_ig_shifted_prior_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_temporal_multichain_scientific.py
```

`python run_tests.py extensive` runs the complete standard-plus-extensive
profile. The extensive tests write their effective YAML beside the result
evidence; the terminal manifest records that executed configuration's SHA-256.

## Registered protocols and computational cost

All four profiles use master seed `20260831`, `nskip: 1`, pooled within-chain
pilot covariance with relative ridge `1e-6`, automatic
`2.38 / sqrt(d)` proposal scaling, and required maximum R-hat `< 1.01`, minimum
bulk ESS `>= 300`, and minimum tail ESS `>= 300`.

The Ploemeur `exp_shifted` single-date and temporal tests additionally require
each production acceptance fraction to remain in `[0.20, 0.50]`; the
`ig_shifted` test uses `[0.20, 0.40]`. These are profile-specific regression
bounds, not general convergence gates. The synthetic profile has no additional
acceptance-rate gate.

| Profile | Chains and initialization | Pilot per chain | Production per chain | Retained rows | Sequential MH transitions |
|---|---|---:|---:|---:|---:|
| Synthetic known truth | 4, `bounds_stratified` | 1,500; 50% burn-in | 4,000; 25% burn-in | 11,996 | 22,000 |
| Ploemeur F09 `exp_shifted` | 5, `bounds_stratified` | 2,000; 50% burn-in | 5,000; 20% burn-in | 19,995 | 35,000 |
| Ploemeur F09 `ig_shifted`, prior active | 5, independent `prior_sample` draws from bounded prior marginals | 5,000; 75% burn-in | 15,000; 20% burn-in | 59,995 | 100,000 |
| Ploemeur temporal `exp_shifted` | 4, `bounds_stratified` over effective bounded prior mass | 2,000; 50% burn-in | 5,000; 20% burn-in | 15,996 | 28,000 |

The current runner executes chains sequentially, so transition counts add
across chains. Wall time depends on the model, tracer histories, cache,
processor, dependency versions, and concurrent machine load. The only
maintained indicative timing is for the prior-active `ig_shifted` profile:
fixed-seed review runs took about 4 to 7 minutes under different concurrent
loads. That observation is descriptive, not a qualification threshold. These
four profiles therefore belong to the scheduled or manually dispatched
extensive campaign rather than the pull-request smoke suite.

## Documented numerical evidence

| Profile | Convergence diagnostics from the fixed-seed run | Additional executable evidence |
|---|---|---|
| Synthetic known truth | Maximum R-hat `1.003066`; minimum bulk ESS `1540.59`; minimum tail ESS `1647.96` | Registered marginal and joint checks recover `mu=28`, `shift=4`, and `mu+shift=32`; four fitted latent tracer responses satisfy their versioned recovery limits. |
| Ploemeur F09 `exp_shifted` | Maximum R-hat `1.001381`; minimum bulk ESS `2485.89`; minimum tail ESS `2950.23`; production-chain acceptance `0.3480`–`0.3738` | Positive-definite proposal covariance, bounded coherent joint rows, independent forward recomputation, relative MCSE at most 10% of posterior standard deviation, and fitted-latent median NRMSE `1.0687`. |
| Ploemeur F09 `ig_shifted`, prior active | Maximum R-hat `1.001912`; minimum bulk ESS `1915.23`; minimum tail ESS `3001.80`; production-chain acceptance `0.3219`–`0.3411` | Prior provenance, distinct starts and phase seeds, positive-definite 3-by-3 proposal covariance, coherent retained rows, forward recomputation, and fitted-latent concentration intervals. |
| Ploemeur temporal `exp_shifted` | Maximum R-hat `1.003728`; minimum bulk ESS `1766.99`; minimum tail ESS `2087.03`; production-chain acceptance `0.3212`–`0.3346` | Prior and effective-error provenance, relative MCSE at most `0.10`, coherent 58-observation rows, forward recomputation, fitted-latent NRMSE `0.9177`, and maximum absolute normalized residual `4.6015` for CFC-11 in 2021. |

These values are descriptive outputs of the registered fixed-seed runs. The
tests enforce the documented scientific inequalities and structural
invariants, not exact floating-point equality to these summaries.

The prior-active inverse-Gaussian profile also preserves an important boundary
diagnostic: the fixed run's 97.5% and 99.5% posterior quantiles for `sigma` are
about 29.48 and 29.90 years against an upper support of 30 years. This contact
must not be reported as an interior, data-identified estimate. Widening or
changing that prior defines a different scientific target and requires a
separate sensitivity analysis.

## Scientific interpretation limits

The synthetic profile uses one versioned noisy realization. It establishes
recovery for that realization, not repeated-noise coverage.

The two single-date field profiles use the same three Ploemeur F09 observations
for calibration and fitted-response checks and have no known field parameter
truth. Their source uncertainty fields are all zero placeholders. The
shifted-exponential profile replaces them with 1% of the mean tracer-history
response at the sampling date; the inverse-Gaussian profile uses 20% of that
same tracer-history mean. These are different likelihood scales, neither is a
relative error on the observed concentration, and the two profiles are not a
controlled comparison of LPM families. The shifted-exponential profile does not
cover F11, the complete monitoring record, or an independent validation sample.
The inverse-Gaussian profile documents one active prior and its support contact,
not robustness to alternative priors or bounds.

The temporal profile uses 58 observations of three tracers over 20 dates. Its
zero uncertainty placeholders are replaced by 20% of the absolute observed
concentration; the recorded 1% tracer-history-mean fallback is unused for this
dataset. It qualifies only `span` mode, the shifted-exponential LPM, this error
policy, the registered priors, seed, and schedule. The temporal workflow
currently forces registered parametric priors; it does not expose the
single-date `prior_option` choice.

Across all field profiles, serialized concentration draws are fitted latent
model responses over retained parameter states. They do not draw new
observation noise and therefore are not posterior predictive distributions.
The checks are in-sample and do not establish out-of-sample skill, tracer
history correctness, LPM uniqueness, structural identifiability, model
adequacy, or transferability to another aquifer.

## Installed-wheel smoke boundary

`examples/templates/smoke_multichain.yaml` is the short installation smoke
profile used after installing the freshly built wheel. It runs the public
`pyages` CLI with two chains, a 40-transition pilot, a 120-transition
production phase, and `require_convergence: false`, then checks chain tables,
proposal covariance, diagnostics, the terminal manifest, and recorded
multi-chain provenance.

This smoke establishes packaging and installed-entry-point reachability for the
CLI/YAML, pilot, diagnostics, serialization, and manifest path. Its deliberately
short exploratory chains are not a fifth scientific qualification and must not
be cited as convergence evidence. Final execution status for the wheel smoke
belongs in {ref}`multichain-final-campaign` rather than being inferred from the
workflow definition.

## Failed evidence and interrupted stages

A required convergence rejection raises `MHConvergenceError`, with an exception
note naming the public directory that contains the promoted evidence. Its
failure manifest records hashes for the preserved chain and diagnostic
artifacts, omits qualified pooled output, and does not claim completion. A
reviewed rerun is a fresh calculation, not continuation from partial chain
state. The failure-to-inspection-to-archive-to-rerun drill is documented in
{doc}`../user-guide/multichain-mh`.

Interrupted internal staging trees have a separate operator path:

```console
pyages stages inspect /path/to/results
pyages stages quarantine /path/to/results/.pyages-<stage-id> \
  --run-id <complete-run-uuid> --yes
```

`stages inspect` recursively inventories managed candidates without writing and
reports journal, terminal-manifest seal, artifact hashes, and publication-token
state. It cannot determine whether another process is still writing an
unsealed stage. After the owning workflow has been stopped, `stages quarantine`
requires the exact inspected run UUID and confirmation, then atomically renames
the complete stage to a sibling quarantine directory. It does not delete,
rewrite, resume, or automatically promote evidence. Corrupt candidates remain
manual-review cases; there is no forced purge command. See
{doc}`../user-guide/cli-flags` and {doc}`../reference/outputs` for the complete
operator contract.

## Qualification archive and CI retention

The scheduled or manually dispatched extensive job fixes pytest's temporary
root, then the strict CI wrapper discovers exactly these four qualified result
manifests. For each profile it finds the YAML actually executed by the test and
matches its SHA-256 to the terminal manifest. It rejects missing, duplicate,
invalid, additional, or mismatched qualified results. After pytest succeeds,
the job builds one wheel and one sdist and passes the four result trees,
executed YAML files, canonical extensive tests, and four maintained case pages
to the generic archive builder in `draft` mode.

CI uploads all four executed YAML files and all four raw result trees together
with `multichain-qualification-draft.zip` and its adjacent `.zip.sha256`
sidecar.
The artifact is retained for **30 days**. Upload uses `if: always()`, so partial
raw trees can remain available after a pytest failure; distribution and archive
construction run only after pytest succeeds. Consequently, an absent ZIP must
not be interpreted as complete qualification evidence. The 30-day artifact is
temporary review storage, not a durable scientific deposit.

`scripts.qualification.build_multichain_archive` is independent of the
historical article/tag-1.0 archive tooling. It validates terminal manifests,
nested artifact SHA-256 values, qualification metadata, executed YAML digests,
wheel and sdist metadata, source state, environment, inventory, and
`CHECKSUMS.sha256`; it writes a reproducible ZIP and a whole-container SHA-256
integrity sidecar, which is not an origin signature.

- `draft` mode clearly records dirty or untagged source state and always marks
  the bundle non-publishable.
- `publishable` mode requires an output outside the repository, checks Git state
  before assembly and before sealing, and binds every result to the exact clean
  annotated HEAD whose tag equals the runtime version. The canonical wrapper
  still requires all four qualified cases.

Verify the ZIP and every nested evidence layer before transfer:

```bash
python -m scripts.qualification.build_multichain_archive verify \
  /path/to/pyages-<version>-multichain-qualification.zip
```

Keep the ZIP and sidecar together. Rebuild publishable evidence from the exact
reviewed release tag rather than relabelling the scheduled branch draft. The
commands and release boundary are documented in {doc}`../dev/releasing`; CI
discovery and failure behavior are documented in {doc}`../dev/ci`.

(multichain-final-campaign)=
## Final integrated local campaign

The campaign below was executed on the complete development worktree before
commit. Result manifests therefore truthfully record parent revision
`03888f9cec25e7387e7bb78348fa14b5313c9250` and `repository.dirty: true`; this
is review evidence, not clean-tag publication evidence. The extensive pytest
root was the short external path `C:\pt-pyages-mh-final`, avoiding both Windows
path-length effects and repository-provenance contamination.

| Validation | Exact observed result |
|---|---|
| Source and environment | PyAges `1.0.1`; Windows 11 `10.0.26200`; CPython `3.12.4`; NumPy `2.1.2`; SciPy `1.14.1`; pandas `2.2.3`; Matplotlib `3.10.8`; Pydantic `2.12.5`; parent Git HEAD `03888f9cec25e7387e7bb78348fa14b5313c9250`, modified worktree |
| Standard pytest profile | `1431 passed, 15 skipped` in `250.83 s`; the 15 skips comprise the 9 opt-in extensive cases and 6 unavailable Windows link/junction cases; 0 failed |
| Extensive pytest profile | `1439 passed, 6 skipped` in `1120.15 s`; all 9 opt-in extensive cases ran, including the four registered scientific profiles; 0 failed |
| Focused archive, stage/runtime/API, and scientific/documentation groups | Three explicit invocations: `25 passed`; `61 passed, 6 skipped`; `112 passed, 4 skipped`; these overlap the integrated suites and are not additive coverage counts |
| Static and generated contracts | Ruff lint and formatting, qualified-surface docstrings, CeCILL licensing metadata/notices, generated test inventory, and `git diff --check` passed |
| Strict Sphinx HTML | Passed with `-W --keep-going`; all internal references resolved |
| Sphinx external link check | Passed. The USGS TracerLPM endpoint was explicitly excluded because its automated endpoint returned a TLS-chain failure or CloudFront `403`; the visible provenance URL is retained, consistently with the other documented publisher endpoints that block link robots. |
| Distribution and installed-wheel smoke | Wheel and sdist built; both passed `twine check`; a fresh external virtual environment imported PyAges from `site-packages`, passed all 12 installation checks, ran the historical quickstart and the two-chain smoke, found no managed residual stage, and verified `installed_distribution` provenance plus all 20 manifest artifacts |
| Canonical qualification archive | A four-profile `draft` ZIP and adjacent SHA-256 integrity sidecar were built and independently verified from the extensive result trees, executed YAML files, protocols, reports, wheel, and sdist; publishable mode was deliberately not claimed on the modified untagged worktree |

The local result is sufficient to hand the branch to clean-commit CI. Release
still requires the exact pushed revision to pass its required jobs. A durable
scientific deposit additionally requires a new clean annotated version tag,
fresh results whose manifests name that exact HEAD, a publishable archive built
outside the repository, transfer verification, and repository/DOI metadata
review. A green campaign does not broaden the scientific scope of the four
registered profiles.
