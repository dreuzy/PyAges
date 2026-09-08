# Extending calibration methods and workflows

PyAges has registries for LPMs and tracer data, but it deliberately has no
automatic registry for calibration methods or workflows. A new method is a
contributor interface that must be selected explicitly by a workflow. A new
workflow must likewise be wired explicitly into the Python facade or CLI if it
is intended to become supported.

This page documents the current contributor contract. Presence in the selected
API reference does not make these objects part of the public compatibility
surface defined in {doc}`../reference/public-api`.

All calibration algorithms are composition-based. For a complete MH example
using fresh problem factories, `MHRunRecord`, and guarded pooling, see
{ref}`multichain-mh-python-contributor-interface`.

## Calibration method contract

Do not subclass another calibration algorithm. Implement the structural
{py:class}`pyages.calibration.methods.protocols.CalibrationAlgorithm` contract:

1. set a stable `method` string suitable for an output-directory name;
2. implement `run(problem)` and return a valid
   {py:class}`pyages.lpm.samples.table.LpmSampleTable`;
3. implement `write_parameters(path)` for the resolved settings;
4. implement `write_results(path)` for elapsed time and scalar diagnostics.

This is a typing contract, not a parent class: Python accepts any object with
these operations. Each implementation explicitly receives and validates its
{py:class}`pyages.calibration.problem.CalibrationProblem`. It neither copies
the problem nor acquires hidden state through inheritance.

A returned sample table must preserve these semantics:

| Content | Required contract |
|---|---|
| parameter columns | Every model parameter in `lpm.get_param_names()` order |
| `obj_function` | $\sqrt{\chi^2/n}$, dimensionless; not raw $\chi^2$ |
| concentration columns | Values in `observations.observation_keys()` order and in each tracer's declared unit |
| rows | Joint states; rejected MCMC proposals remain repeated rows when retained |
| derived moments | `mean`, `std`, and quantiles should be added with `add_moments()` before serialization |

Use the prepared problem's `objective_function()` so the method cannot silently
replace the forward model or observation-error convention. Calibration ranges
and priors remain the method's responsibility; formula validity stays with the
LPM domain contract.

The smallest useful structural example is:

```python
from pathlib import Path
from time import perf_counter

from pyages.calibration.outputs import write_calibrated_result, write_key_values
from pyages.calibration.objective import normalized_residual_norm
from pyages.lpm.samples import LpmSampleTable


class MyMethod:
    method = "my_method"

    def __init__(self, tolerance: float = 1e-6) -> None:
        self.tolerance = tolerance
        self.evaluations = 0
        self.runtime_seconds = 0.0
        self.problem = None

    def run(self, problem) -> LpmSampleTable:
        problem.ensure_prepared()
        self.problem = problem
        started = perf_counter()
        observed, errors = problem.prepared_observation_arrays()
        lpm = problem.lpm
        assert lpm is not None

        # Replace this initial point with the new search algorithm.
        parameters = lpm.param_init()
        chi_square, modeled = problem.objective_function(
            parameters, observed, errors, return_concentrations=True
        )
        self.evaluations = 1

        results = LpmSampleTable(
            lpm,
            c_names=problem.observations.observation_keys(),
        )
        results.append_sample(
            lpm.p.copy(),
            obj_function=normalized_residual_norm(chi_square, len(observed)),
            concentrations=modeled,
            param_in_bounds=lpm.param_within_calibration_range_array(parameters),
        )
        self.runtime_seconds = perf_counter() - started
        return results.add_moments()

    def write_parameters(self, file_name: str | Path) -> None:
        write_key_values(
            file_name,
            {"method": self.method, "tolerance": self.tolerance},
        )

    def write_results(self, file_name: str | Path) -> None:
        write_key_values(
            file_name,
            {"runtime_seconds": self.runtime_seconds, "evaluations": self.evaluations},
        )
```

The example evaluates one point only; it demonstrates the interface rather
than a scientifically useful optimizer.

After `results = method.run(problem)`, call
`write_calibrated_result(method, problem, results)` to write the standard tables
documented in {doc}`../reference/outputs`. Output is a separate service, not an
inherited method of the numerical algorithm.

### Method qualification checklist

- reject invalid settings before starting the expensive calculation;
- record all settings, seeds, initialization sources, and proposal metadata;
- make failure explicit when the algorithm does not converge or returns
  non-finite or out-of-calibration-range parameters;
- test the returned joint-sample schema and objective convention;
- test deterministic behavior for fixed seeds;
- add numerical or golden qualification appropriate to the algorithm;
- wire the method explicitly into each workflow that supports it;
- update the configuration, output, scientific-method, and compatibility pages
  if the method becomes user-facing.

## Workflow contract

A reusable workflow orchestrates existing scientific objects; it does not
inherit from them. Follow the sequence below:

1. validate YAML with a strict Pydantic model (`extra="forbid"`);
2. resolve paths relative to the configuration using the shared loading rules;
3. load observations through `Concentrations.from_file()` or
   `Concentrations.from_dataframe()`;
4. create an isolated run with
   {py:func}`pyages.workflows.runtime.begin_staged_result_run`, then
   place its identity and resolved working/output paths in an explicit,
   preferably immutable context;
5. construct and prepare `CalibrationProblem`;
6. call `method.run(problem)` and write standard calibration outputs;
7. write workflow-specific tables and optional figures;
8. write {py:func}`pyages.workflows.runtime.write_result_manifest`
   **last**, passing the run identity;
9. call {py:func}`pyages.workflows.runtime.promote_result_run` and
   return the public result path.

The returned `ResultRun` is an opaque lifecycle handle: inspect its identity and
resolved directories as needed, but do not construct or alter it. Pass that same
handle to `promote_result_run()` so the stored compare-and-swap identity remains
bound to the staged tree.

The manifest must index the YAML configuration and every external scientific
input. Its `details` mapping should record the choices needed to understand the
directory tree, such as dataset, mode, LPMs, and case directories. Never write
a `complete` manifest from a `finally` block or after catching and suppressing
an incomplete calculation. Do not bypass staging for a supported public
workflow: direct in-place writers cannot provide the same whole-tree isolation.

Use `pyages.config.paths.result_subdirectory()` for fixed child names, but
validate any user-derived directory component with
`pyages.config.paths.validate_path_component()` before passing it. A public
workflow must have a deterministic, documented layout. Terminal promotion
replaces the preceding tree deliberately; document that lifecycle and require
callers to archive an earlier result when it must be retained.

### Exposure levels

| Intended use | Required integration |
|---|---|
| Repository-only study | Local entry point and README; no import from the installed core |
| Reusable contributor workflow | Module under `pyages.workflows` plus tests; no compatibility promise by default |
| Supported Python workflow | Export through `pyages.workflows.__all__`, add selected API documentation, and update the compatibility policy |
| Installed CLI workflow | Add explicit Click routing, flags, exit behavior, user guide, output contract, and end-to-end tests |

### Workflow qualification checklist

- cover minimal successful execution and every mode with tests;
- verify path resolution inside and outside a source checkout;
- verify the manifest is complete on success, failed for a documented
  scientific gate rejection, and absent for other pre-terminal failures;
- verify every documented artifact name and table schema;
- keep plotting optional and non-interactive for automated runs;
- record random seeds and numerical settings that affect results;
- add a migration note and golden updates for changes that alter scientific
  results.
