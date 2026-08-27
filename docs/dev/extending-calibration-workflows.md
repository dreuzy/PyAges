# Extending calibration methods and workflows

PyAges has registries for LPMs and tracer data, but it deliberately has no
automatic registry for calibration methods or workflows. A new method is a
contributor interface that must be selected explicitly by a workflow. A new
workflow must likewise be wired explicitly into the Python facade or CLI if it
is intended to become supported.

This page documents the current contributor contract. Presence in the selected
API reference does not make these objects part of the public compatibility
surface defined in {doc}`../reference/public-api`.

## Calibration method contract

Subclass {py:class}`pyages.calibration.methods.base.CalibrationMethod` and:

1. call `super().__init__()`;
2. set a stable `method` string suitable for an output-directory name;
3. implement `perform()` and return a valid
   {py:class}`pyages.lpm.samples.table.LpmSampleTable`;
4. implement `write_parameters(path)` for the resolved algorithm settings;
5. implement `write_results_spec(data)` by adding scalar diagnostics to the
   supplied mapping.

Callers use `method.run(problem)`, not `perform()` directly. `run()` verifies
that the {py:class}`pyages.calibration.problem.CalibrationProblem` is prepared
and binds it to the method. The inherited `problem`, `observations`, `lpm`,
`tracers`, and `display_options` properties are unavailable before that bind.

A returned sample table must preserve these semantics:

| Content | Required contract |
|---|---|
| parameter columns | Every model parameter in `lpm.get_param_names()` order |
| `obj_function` | $\sqrt{\chi^2/n}$, dimensionless; not raw $\chi^2$ |
| concentration columns | Values in `observations.observation_keys()` order and in each tracer's declared unit |
| rows | Joint states; rejected MCMC proposals remain repeated rows when retained |
| derived moments | `mean`, `std`, and quantiles should be added with `add_moments()` before serialization |

Use the prepared problem's `objective_function()` so the method cannot silently
replace the forward model or observation-error convention. Parameter bounds
and priors remain the method's responsibility.

The smallest useful structural example is:

```python
from pathlib import Path
from time import perf_counter

from pyages.calibration.methods.base import CalibrationMethod
from pyages.calibration.outputs import write_key_values
from pyages.calibration.utils.objective_functions import normalized_residual_norm
from pyages.lpm.samples import LpmSampleTable


class MyMethod(CalibrationMethod):
    method = "my_method"

    def __init__(self, tolerance: float = 1e-6) -> None:
        super().__init__()
        self.tolerance = tolerance
        self.evaluations = 0

    def perform(self) -> LpmSampleTable:
        started = perf_counter()
        observed, errors = self.observation_arrays()

        # Replace this initial point with the new search algorithm.
        parameters = self.lpm.param_init()
        chi_square, modeled = self.objective_function(
            parameters, observed, errors, conc=True
        )
        self.evaluations = 1

        results = LpmSampleTable(
            self.lpm,
            c_names=self.observations.observation_keys(),
        )
        results.append_sample(
            self.lpm.p.copy(),
            obj_function=normalized_residual_norm(chi_square, len(observed)),
            concentrations=modeled,
            param_in_bounds=self.lpm.param_within_bounds_array(parameters),
        )
        self.time_perform = perf_counter() - started
        return results.add_moments()

    def write_parameters(self, file_name: str | Path) -> None:
        write_key_values(
            file_name,
            {"method": self.method, "tolerance": self.tolerance},
        )

    def write_results_spec(self, data: dict) -> None:
        data["evaluations"] = self.evaluations
```

The example evaluates one point only; it demonstrates the interface rather
than a scientifically useful optimizer.

After `results = method.run(problem)`, call
`method.write_calibrated_lpm(results)` to write the standard tables documented
in {doc}`../reference/outputs`. Do not create a competing table schema inside
the method.

### Method qualification checklist

- reject invalid settings before starting the expensive calculation;
- record all settings, seeds, initialization sources, and proposal metadata;
- make failure explicit when the algorithm does not converge or returns
  non-finite/out-of-bounds parameters;
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
4. create an explicit, preferably immutable context containing resolved inputs
   and output paths;
5. construct and prepare `CalibrationProblem`;
6. call `method.run(problem)` and write standard calibration outputs;
7. write workflow-specific tables and optional figures;
8. write {py:func}`pyages.workflows.result_manifest.write_result_manifest`
   **last**;
9. return the result path.

The manifest must index the YAML configuration and every external scientific
input. Its `details` mapping should record the choices needed to understand the
directory tree, such as dataset, mode, LPMs, and case directories. Never write
a `complete` manifest from a `finally` block or after catching and suppressing
an incomplete calculation.

Use `pyages.config.paths.result_subdirectory()` for fixed child names, but
validate any user-derived directory component before passing it. A public
workflow must have a deterministic, documented layout and must not silently
delete an earlier result directory.

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
- verify the manifest is absent on failure and complete on success;
- verify every documented artifact name and table schema;
- keep plotting optional and non-interactive for automated runs;
- record random seeds and numerical settings that affect results;
- add a migration note and golden updates for changes that alter scientific
  results.
