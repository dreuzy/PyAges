# Running and qualifying multi-chain MH

```{note}
Multi-chain MH is an **Unreleased** feature on the development branch. It is
not included in the `pyages==1.0.1` package from PyPI. Until the next release,
install PyAges from the source checkout that contains the configuration and
implementation described here, and record its Git commit.
```

This guide covers the complete operational path: dispersed initialization,
pilot tuning, independent production streams, diagnostics, qualification,
pooling, and inspection. The exhaustive field reference is in
{ref}`optional-multi-chain-mh-configuration`; the statistical definitions are
in {doc}`../science/inference`.

## Start from a reproducible profile

Four qualification configurations and one exploratory profile exercise the
public YAML workflows:

```bash
pyages run examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml
pyages run examples/natural/ploemeur/exemple_ploemeur_multichain.yaml
pyages run examples/natural/ploemeur/exemple_ploemeur_ig_shifted_prior_multichain.yaml
pyages run examples/natural/ploemeur_temporal/ploemeur_temporal_multichain.yaml
pyages run examples/natural/albuquerque/exemple_albuquerque_shapefree_multichain.yaml
```

The synthetic case has known generating parameters and is the first profile to
run. The three Ploemeur profiles have no known field parameter truth; they
qualify convergence and the internal coherence of fitted latent concentrations
only. See {doc}`../examples/synthetic-recovery`,
{doc}`../examples/ploemeur-multichain`,
{doc}`../examples/ploemeur-ig-shifted-prior-multichain`, and
{doc}`../examples/ploemeur-temporal-multichain` for their exact qualification
protocols. The Albuquerque profile is documented separately in
{doc}`../examples/albuquerque`: it is exploratory and is not part of the
publishable four-case archive.

All profiles use deterministic result-directory names. A new run writes into
an isolated, run-ID-derived staging tree while the preceding published result
remains intact. Terminal promotion verifies the staged artifacts and replaces
the exact preceding publication, so the manifest hashes only artifacts from
that run and a stale concurrent run cannot overwrite it. Archive the preceding
result first when it must be retained as qualification evidence.

## Understand the stages

An enabled ensemble follows this sequence:

1. `bounds_stratified` draws one dispersed Latin-hypercube start per chain
   inside the LPM calibration ranges, or within the effective marginal prior mass
   when an informative prior is enabled.
2. A distinct pilot random stream advances each start and retains tuning draws.
3. PyAges centers each pilot chain separately and estimates one pooled
   within-chain covariance. A scale-aware ridge makes it positive definite.
4. The covariance and proposal multiplier are frozen before production.
5. Production uses a fresh mutable calibration problem and a distinct random
   stream for every chain.
6. PyAges calculates folded rank-normalized split-R-hat, bulk ESS, tail ESS,
   and the Monte Carlo standard error of the mean before pooling.
7. Root posterior tables are written only after the configured gate passes, or
   after the user explicitly requests exploratory pooling with
   `require_convergence: false`.

Pilot draws tune the random walk; they are never posterior draws. The proposal
covariance is not a prior covariance and is not learned from the first
production chain. The pooled-within-chain estimator is the only supported
method, so there is no covariance-method selector in the configuration.

Prior-based ensemble starts use the prior's bounded marginal interface. A
normal marginal is conditioned on the calibration interval before its
quantile is inverted; a uniform marginal uses the overlap between its own
support and that interval; and an empirical marginal integrates its
piecewise-linear density after clipping it precisely at the calibration range.
The initializer therefore does not reinterpret prior storage or distribution
metadata. Both `prior_sample` and prior-aware `bounds_stratified` use this one
tested scientific definition.

## Choose the controls deliberately

A typical qualification block is:

```yaml
multichain:
  enabled: true
  chains: 4
  master_seed: 12345
  initialization:
    strategy: bounds_stratified
  pilot:
    enabled: true
    nstep: 2000
    burn_in: 0.5
    relative_ridge: 1.0e-6
    proposal_multiplier: auto
  diagnostics:
    max_rhat: 1.01
    min_bulk_ess: 300
    min_tail_ess: 300
    require_convergence: true
```

The presence of `multichain:` activates the ensemble because `enabled`
defaults to `true`. The explicit value above makes the intended scientific
profile visible; use `enabled: false` to keep a block in a file without running
it. Omitting the mapping or setting it to `null` selects the historical
one-chain path.

`chains` is the number of pilot and production chains. `master_seed` is the
root of separate initialization, pilot, and production streams. A fixed value
replays the ensemble; `null` realizes and records a fresh root seed. The
ordinary one-chain `seed` is ignored while the ensemble is enabled.

Use `nskip: 1` for diagnostic runs unless storage is a demonstrated constraint.
Thinning discards information and cannot improve mixing. Increase production
length when ESS is insufficient. Do not weaken a gate merely to obtain a
pooled file.

(multichain-mh-python-contributor-interface)=
## Embed the ensemble in contributor code

```{important}
The YAML workflow and `pyages run` are the supported user interfaces. The
objects below are selected contributor interfaces: they are documented for
extensions, but their presence in the generated API does not add them to the
public compatibility surface defined in {doc}`../reference/public-api`.
```

The following source-checkout example constructs synthetic observations, uses
only the canonical MH facade for ensemble objects, creates a fresh prepared
`CalibrationProblem` for every requested stage and chain, and pools only after
the configured qualification gate passes:

```python
from pyages.calibration.methods.mh import (
    MHConfig,
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
    MHRunRecord,
    MultiChainMetropolisHastings,
)
from pyages.calibration.problem import CalibrationProblem
from pyages.convolution import ConvolutionTracers
from pyages.lpm.factory import build_lpm

# Build a small one-parameter synthetic target and its observation table.
target = build_lpm("exp")
tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
observations = tracers.convolve(target, return_type="concentrations")
observations.set_relative_errors(0.20)

chain_config = MHConfig(
    nstep=4000,
    burn_in=0.25,
    nskip=1,
    prior_option=False,
    likelihood=True,
    monitor=False,
    display_traj=False,
    componentwise_source="model",
)
ensemble_config = MHEnsembleConfig(
    chains=4,
    master_seed=20260831,
    initialization=MHInitializationConfig(strategy="bounds_stratified"),
    pilot=MHPilotConfig(
        enabled=True,
        nstep=1500,
        burn_in=0.5,
        relative_ridge=1.0e-6,
        proposal_multiplier=None,  # None selects 2.38 / sqrt(dimension).
    ),
    diagnostics=MHDiagnosticsConfig(
        max_rhat=1.01,
        min_bulk_ess=300,
        min_tail_ess=300,
        require_convergence=True,
    ),
)


def problem_factory(_stage: str, _chain_id: int) -> CalibrationProblem:
    # Never cache or reuse this object: evaluation mutates its LPM state.
    return CalibrationProblem(
        observations,
        "exp",
        explore_objective=False,
        explore_reachable=False,
    ).prepare()


ensemble = MultiChainMetropolisHastings(chain_config, ensemble_config)
record: MHRunRecord = ensemble.run(problem_factory)
if record.qualification_status == "qualified":
    pooled = record.pooled_samples()
    print(record.qualification_status, len(pooled.frame))
else:
    print("Ensemble status:", record.qualification_status)
    if record.diagnostics:
        for diagnostic in record.diagnostics:
            print(
                diagnostic.parameter,
                diagnostic.rhat,
                diagnostic.bulk_ess,
                diagnostic.tail_ess,
                diagnostic.qualified,
            )
    else:
        print("Diagnostics unavailable:", record.diagnostics_message)
```

This direct engine returns an in-memory record; it does not reproduce workflow
staging, manifests, or the documented result-file layout. Use the YAML workflow
when those operational guarantees are required. Contributor workflow wiring is
discussed in {doc}`../dev/extending-calibration-workflows`.

(multichain-mh-in-memory-record)=
## Inspect the in-memory ensemble structure

The ensemble does not retain four long-lived `MetropolisHastings` objects. It
creates one temporary sampler for each pilot or production chain, runs it, and
keeps the resulting values and provenance. The durable in-memory result is the
`MHRunRecord` returned by `run()`:

```text
record
|-- seed_plan
|   |-- initialization_seeds       one seed per chain
|   |-- pilot_seeds                one distinct seed per chain
|   `-- production_seeds           one distinct seed per chain
|-- pilot                          MHPilotResult, or None
|   |-- initial_states             one pre-pilot state per chain
|   |-- final_states               production starts when pilot is enabled
|   |-- covariance                 one shared d-by-d production covariance
|   |-- acceptance_rates           one value per pilot chain
|   `-- samples                    tuple of pilot matrices, or None
|-- chains                         tuple of production MHChainResult objects
|   |-- chains[0]                  chain_id == 1
|   |   `-- samples.frame          retained production table for chain 1
|   |-- chains[1]                  chain_id == 2
|   |   `-- samples.frame          retained production table for chain 2
|   `-- ...
|-- diagnostics                    one row-like object per diagnostic quantity
`-- qualification_status           qualified, not_qualified, or diagnostics_unavailable
```

The prototype requested as `problem_factory("initialization", 0)` is not an
extra chain. It supplies the common parameter names, calibration ranges, prior, and target
signature used to construct the dispersed starts. Pilot and production then
receive fresh mutable problems numbered from 1 through `ensemble_config.chains`.
Those problems and their temporary samplers are not stored on `record`.

### Locate pilot and production chains

In the contributor example above, the following assertions describe the
result topology:

```python
assert len(record.seed_plan.initialization_seeds) == 4
assert len(record.seed_plan.pilot_seeds) == 4
assert len(record.seed_plan.production_seeds) == 4

assert record.pilot is not None
assert len(record.pilot.initial_states) == 4
assert len(record.pilot.final_states) == 4
assert len(record.pilot.acceptance_rates) == 4

assert len(record.chains) == 4
assert tuple(chain.chain_id for chain in record.chains) == (1, 2, 3, 4)
assert record.chains[0].chain_id == 1  # Python index 0, scientific chain ID 1.
```

Pilot matrices contain native parameters only and have shape
`(retained_pilot_draws, parameter_count)`. They are retained only when
`save_samples=True` is set on `MHPilotConfig`; the example above uses the
default `False`, so `record.pilot.samples is None`. Regardless of that storage
choice, final pilot states, covariance, acceptance rates, retained counts, and
runtimes remain in `record.pilot`. Pilot draws tune the proposal and never enter
the posterior.

Production chains are always kept separately in `record.chains`. Inspect them
without pooling:

```python
for chain in record.chains:
    print(f"chain {chain.chain_id}")
    print("seed:", chain.seed)
    print("initial parameters:", dict(chain.initial_params))
    print("acceptance rate:", chain.acceptance_rate)
    print("retained rows:", len(chain.samples.frame))
    print(chain.samples.frame.head())
```

Each `chain.samples.frame` is oriented like an ordinary table: retained draws
are rows and model outputs are columns. Its canonical columns include native
LPM parameters, `obj_function`, modeled concentrations, `param_in_bounds`, and
derived LPM moments. Rejected proposals appear as repeated parameter rows. They
must remain in the table because they are genuine states of the Markov chain.

For example, the first eight retained values of a parameter named `mu` might
look like this:

```text
retained draw       1      2      3      4      5      6      7      8
chain 1          9.10   9.30   9.30   9.60   9.40   9.80   9.70  10.00
chain 2         10.90  10.70  10.50  10.50  10.30  10.10  10.20  10.00
chain 3          8.80   9.10   9.40   9.20   9.50   9.70   9.80   9.90
chain 4         11.20  10.80  10.60  10.40  10.20  10.10  10.00   9.90
```

The repeated `9.30` in chain 1 and `10.50` in chain 2 illustrate retained
states after rejected proposals; they are not accidental duplicate rows.

### Follow chains into the diagnostic matrix

Diagnostics use native sampled parameters followed by the LPM's declared
derived moments. `obj_function`, modeled concentrations, and
`param_in_bounds` remain useful sample-table columns but are not part of this
canonical diagnostic list.

For each diagnostic quantity, PyAges extracts the named column from every
production table and stacks the vectors without pooling chain identity. The
orientation therefore changes from one table per chain to one matrix whose
first axis identifies the chain:

```python
import numpy as np

mu_by_chain = np.vstack(
    [chain.samples.frame["mu"].to_numpy(dtype=float) for chain in record.chains]
)

assert mu_by_chain.shape == (
    ensemble_config.chains,
    chain_config.retained_sample_count(),
)
```

For the illustrative values above, `mu_by_chain[:, :8]` is:

```python
np.array(
    [
        [9.10, 9.30, 9.30, 9.60, 9.40, 9.80, 9.70, 10.00],  # chain 1
        [10.90, 10.70, 10.50, 10.50, 10.30, 10.10, 10.20, 10.00],  # chain 2
        [8.80, 9.10, 9.40, 9.20, 9.50, 9.70, 9.80, 9.90],  # chain 3
        [11.20, 10.80, 10.60, 10.40, 10.20, 10.10, 10.00, 9.90],  # chain 4
    ]
)
```

The diagnostic contract is thus always:

```text
values[chain_index, retained_draw_index]
shape == (n_chains, n_draws_per_chain)
```

Split diagnostics then divide every row into equal first and last halves. A
`(4, 8)` matrix becomes an `(8, 4)` matrix ordered as follows:

```text
diagnostic row 0    first half of chain 1
diagnostic row 1    first half of chain 2
diagnostic row 2    first half of chain 3
diagnostic row 3    first half of chain 4
diagnostic row 4    last half of chain 1
diagnostic row 5    last half of chain 2
diagnostic row 6    last half of chain 3
diagnostic row 7    last half of chain 4
```

This preserved identity is what lets split-R-hat compare within-chain and
between-chain variation. Bulk ESS, tail ESS, and MCSE likewise receive the
unpooled production matrix. If the retained length is odd, the one middle draw
is omitted from the split calculation as described in
{doc}`../science/inference`.

### Pool only after inspecting qualification

`record.pooled_samples()` first revalidates the record and, by default, refuses
to pool unless `record.qualification_status == "qualified"`. A successful pool
returns a new independent `LpmSampleTable`; it does not mutate the separate
tables in `record.chains`:

```python
pooled = record.pooled_samples()

assert len(pooled.frame) == sum(len(chain.samples.frame) for chain in record.chains)
```

The pooled table appends chain 1, then chain 2, and so on, but it does not add a
`chain_id` column. Preserve that identity explicitly when preparing custom
trace or exploratory tables:

```python
import pandas as pd

identified_frames = []
for chain in record.chains:
    frame = chain.samples.frame.copy()
    frame.insert(0, "chain_id", chain.chain_id)
    identified_frames.append(frame)

samples_with_chain_id = pd.concat(identified_frames, ignore_index=True)
```

Use `record.chains` or `samples_with_chain_id` for trace inspection, not the
unlabeled pooled table. Passing `require_qualified=False` to
`pooled_samples()` is an explicit exploratory override; it does not change a
non-qualified run into a qualified one.

The YAML workflow serializes the same logical structure under
`chains/chain_<N>/`, with diagnostics in `mcmc_diagnostics.tsv` and optional
pilot matrices under `pilot/`. The complete persistent layout is documented in
{doc}`../reference/outputs`.

## Interpret qualification and failure

The workflow records one of three statuses:

| Status | Meaning |
|---|---|
| `qualified` | Every applicable quantity has finite diagnostics, R-hat below the configured strict limit, and bulk/tail ESS at or above their limits. |
| `not_qualified` | Diagnostics were calculated, but at least one applicable quantity failed a gate. |
| `diagnostics_unavailable` | Diagnostics could not be calculated; the recorded message gives the cause. |

With `require_convergence: true`, either non-qualified status preserves chain,
seed, pilot, and diagnostic evidence, then fails the workflow. No pooled root
posterior is produced. The workflow writes `result_manifest.json` with
`status: failed`, the exception message, and hashes of the preserved evidence;
this is not a completion marker. With
`require_convergence: false`, pooling is explicitly exploratory and the
non-qualified status remains recorded.

Qualification does not include a scientific acceptance-rate interval, a
relative-MCSE threshold, residual adequacy, uniqueness of the LPM, or external
field truth. Those checks belong to a case-specific protocol.

(multichain-mh-failure-recovery-drill)=
## Exercise rejection, inspection, and a clean rerun

The following source-checkout drill derives two local configurations from the
qualified synthetic profile. The first changes only the R-hat gate to the
deliberately impractical floating-point value immediately above one. The second
restores the reviewed `1.01` gate. Both publish to the same deterministic
directory so that the rerun exercises the normal terminal replacement path.
This strict threshold is a test of failure handling, not a recommended
scientific setting.

Create the local configurations under the ignored `.artifacts/` directory:

```python
from copy import deepcopy
from pathlib import Path

import yaml

source = Path(
    "examples/synthetic/lpm_recovery_single_date/"
    "lpm_recovery_single_date_multichain.yaml"
).resolve()
work = Path(".artifacts/mh-recovery-drill").resolve()
work.mkdir(parents=True, exist_ok=True)

reviewed = yaml.safe_load(source.read_text(encoding="utf-8"))
diagnostic_key = "calibration_metropolis_hastings"
reviewed_gate = reviewed[diagnostic_key]["multichain"]["diagnostics"]
assert reviewed_gate["require_convergence"] is True
assert reviewed_gate["max_rhat"] == 1.01

common_results = {
    "use_default": False,
    "directory": str(work / "results"),
    "study_name": "synthetic_multichain_recovery_drill",
}
strict_rhat = 1.0000000000000002

rejected = deepcopy(reviewed)
rejected["results"] = common_results
rejected[diagnostic_key]["multichain"]["diagnostics"]["max_rhat"] = strict_rhat

retry = deepcopy(reviewed)
retry["results"] = common_results

for name, payload in (("reject.yaml", rejected), ("retry.yaml", retry)):
    (work / name).write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
```

Run the deliberately rejected configuration from the repository root:

```bash
pyages run .artifacts/mh-recovery-drill/reject.yaml
```

The expected exit status is `1`. In non-verbose mode the CLI prints the failure
and exactly one `Preserved result evidence: ...` note. Inspect that terminal
failure and archive it before retrying; the live directory will otherwise be
replaced by the next terminal promotion:

```python
import csv
import json
from pathlib import Path
from shutil import copytree

evidence = Path(
    ".artifacts/mh-recovery-drill/results/"
    "synthetic_multichain_recovery_drill/"
    "synthetic_exp_shifted_2010.txt"
)
manifest = json.loads((evidence / "result_manifest.json").read_text(encoding="utf-8"))
assert manifest["status"] == "failed"
assert manifest["failure"]["type"] == "MHConvergenceError"

mh_directory = evidence / "Metropolis_Hastings"
chains = sorted((mh_directory / "chains").glob("chain_*"))
assert len(chains) == 4
assert not (mh_directory / "lpm_dist_calibrated.txt").exists()

with (mh_directory / "mcmc_diagnostics.tsv").open(
    encoding="utf-8", newline=""
) as stream:
    diagnostics = list(csv.DictReader(stream, delimiter="\t"))
print(manifest["failure"])
for row in diagnostics:
    if row["included_in_qualification"] == "True" and row["qualified"] == "False":
        print(row["parameter"], row["rhat"], row["bulk_ess"], row["tail_ess"])

archive = evidence.with_name(f"{evidence.name}-rejected-evidence")
copytree(evidence, archive)
print(f"Archived rejected evidence: {archive}")
```

Now rerun the same fixed-seed scientific protocol with its reviewed gate:

```bash
pyages run .artifacts/mh-recovery-drill/retry.yaml
```

The published directory is replaced only after the staged retry passes all
gates. Confirm that it is a complete run with qualified pooling while the local
archive still contains the rejected terminal state:

```python
import json
from pathlib import Path

evidence = Path(
    ".artifacts/mh-recovery-drill/results/"
    "synthetic_multichain_recovery_drill/"
    "synthetic_exp_shifted_2010.txt"
)
manifest = json.loads((evidence / "result_manifest.json").read_text(encoding="utf-8"))
assert manifest["status"] == "complete"
assert "failure" not in manifest
assert (evidence / "Metropolis_Hastings/lpm_dist_calibrated.txt").is_file()
assert evidence.with_name(f"{evidence.name}-rejected-evidence").is_dir()
```

This is a full rerun, not continuation from partial chain state. Do not replace
the reviewed gate with `require_convergence: false`: that option deliberately
permits exploratory pooling and would not repair the failed qualification.

## Inspect chains and traces

The stable input for trace inspection is the set of per-chain tables, not the
one-chain `monitor` or `display_traj` options. For a single-date run:

```python
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

mh_dir = Path("/path/to/results/Metropolis_Hastings")
chain_files = sorted(mh_dir.glob("chains/chain_*/lpm_dist_calibrated.txt"))

fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
for chain_file in chain_files:
    chain = pd.read_csv(chain_file, sep="\t", index_col=0)
    label = chain_file.parent.name
    for axis, parameter in zip(axes, ("mu", "shift"), strict=True):
        axis.plot(chain[parameter].to_numpy(), linewidth=0.7, alpha=0.8, label=label)
        axis.set_ylabel(parameter)

axes[-1].set_xlabel("retained draw")
for axis in axes:
    axis.legend()
fig.tight_layout()
plt.show()
```

Read the numerical diagnostics separately:

```python
diagnostics = pd.read_csv(mh_dir / "mcmc_diagnostics.tsv", sep="\t")
print(diagnostics.to_string(index=False))
```

Inspect all traces for stationarity, slow excursions, different chain modes,
and persistent contact with calibration-range endpoints. Numerical gates complement this
inspection; they do not replace it.

## Budget the calculation

The current ensemble runner executes chains sequentially. Approximate cost is
therefore the sum of all pilot and production transitions:

| Profile | Pilot transitions | Production transitions | Retained production rows |
|---|---:|---:|---:|
| Synthetic | 4 × 1,500 | 4 × 4,000 | 11,996 |
| Ploemeur F09 | 5 × 2,000 | 5 × 5,000 | 19,995 |
| Ploemeur F09 IG with prior | 5 × 5,000 | 5 × 15,000 | 59,995 |
| Ploemeur temporal | 4 × 2,000 | 4 × 5,000 | 15,996 |
| Albuquerque exploratory | 5 × 1,000 | 5 × 2,500 | 9,995 |

Wall time depends strongly on tracer histories, LPM, convolution cache,
processor, and dependency versions. These profiles are extensive scientific
checks, not fast smoke tests.

## Reproduce the executable qualifications

Run each case directly with pytest:

```bash
python -m pytest -q --run-extensive tests/examples/test_synthetic_recovery_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_ig_shifted_prior_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_temporal_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_albuquerque_shapefree_multichain_scientific.py
```

Or run the complete standard-plus-extensive profile:

```bash
python run_tests.py extensive
```

For a scientific record, preserve the YAML, normalized observations, exact
source commit, environment, all chain tables, diagnostics, proposal covariance,
seed provenance, and complete result manifest. The observed qualification is
summarized in
{doc}`../reports/multichain-mh-qualification-2026-08-31`.
