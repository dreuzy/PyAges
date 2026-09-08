# Public API and compatibility

PyAges deliberately exposes a small supported surface. This keeps scientific
workflows understandable and leaves implementation details free to evolve.

## Supported interfaces

The following interfaces are intended for users:

- the `pyages` command and its documented subcommands;
- `pyages.__version__`;
- the symbols exported by `pyages.convolution.__all__`;
- `pyages.lpm.factory.build_lpm`, `build_random_lpm`, and
  `list_available_lpms`;
- `pyages.lpm.samples.LpmSampleTable`;
- `pyages.tracer.tracer_root.Tracer`;
- `pyages.concentrations.Concentrations`, constructed with `from_file()` or
  `from_dataframe()`, and `pyages.concentrations.ConcentrationChronicle`;
- the validated models exported by `pyages.config`;
- `pyages.workflows.run_single_date` and `pyages.workflows.run_temporal`;
- documented YAML configuration fields and the result files defined in
  {doc}`outputs`.

`SingleDateConfig` is the canonical single-date model and preserves the nested
YAML sections used by the workflow.

Modules below `core`, `utils`, private names beginning with `_`, site-specific
code, examples, and repository scripts are implementation or research
interfaces. They can evolve without a compatibility alias.

The generated API reference also documents selected contributor interfaces.
Being present there does not by itself make a symbol part of the supported
public surface above.

The Python helpers in `pyages.data_io` are contributor interfaces rather than
public user APIs. The documented result-file names and layouts they produce
remain covered by the compatibility policy because workflows expose those
files directly to users. Contributor code should read these formats with
`read_distribution()`, `read_statistics()`, and `read_histograms()` from
`pyages.data_io.lpm_distribution`, rather than duplicating pandas parser
options.

## Contributor imports

Import continuous-convolution controls from `pyages.convolution` as
`ConvolutionSettings` and `DEFAULT_CONVOLUTION_SETTINGS`. For tracer
extensions, import `ConvolutionTracerProtocol` from
`pyages.tracer.protocols` and analytical implementations from
`pyages.tracer.simple_tracers`. Pre-1.0 names and compatibility modules are not
part of the supported surface.

Import reusable result exports and figures from `pyages.reporting`, workflow
execution services from `pyages.workflows.runtime`, and synthetic recovery
experiments from `pyages.qualification`. The former flat workflow utility
modules and the internal `pyages.workflows.plots` and
`pyages.workflows.synthetic_recovery` paths are removed before 1.0; contributor
code must use the canonical imports above.

The contributor runtime facade exports the staged-result lifecycle
`begin_staged_result_run()`, `write_result_manifest()`,
`write_failure_manifest()`, and `promote_result_run()`. Its returned `ResultRun`
is an opaque handle created by the facade, not a caller-constructed data model.

Interrupted-stage maintenance is intentionally separate from that contributor
facade. Operators should normally use `pyages stages inspect` and
`pyages stages quarantine`. Administrative Python integrations can import
`StagedRunInspection`, `inspect_staged_result_run()`,
`inventory_staged_result_runs()`, and `quarantine_staged_result_run()` directly
from `pyages.workflows.runtime.manifest`. Quarantine requires the complete run
UUID and preserves the tree; this API exposes no automatic purge operation.
`StagedRunInspection.promotable_now` is explicitly diagnostic, and no shorter
`promotable` compatibility alias is defined.

Contributor code that compares independently prepared calibration targets
imports the signature records and
`build_calibration_target_signature()` from
`pyages.calibration.target_signature`. Signature records and their
schema-version constant have this single canonical module; the problem module
does not provide compatibility aliases.

The contributor facade `pyages.calibration.methods.mh` exposes the primitive
one-chain kernel, the common 1..N-chain runner and its configurations,
`MHConvergenceError`, and the immutable `MHRunRecord` produced by the managed
run. Leaf chain, pilot, diagnostic, and seed records stay in their defining
contributor modules instead of enlarging the facade. `MHRunRecord` owns the
exact chain and run configurations consumed by serialization; writers do
not accept a second configuration source. The experimental `MHEnsembleResult`,
`ProblemFactory`, and workflow builder aliases were removed before release of
the multi-chain feature. Internal callable protocols and path/configuration
builders now use private names.

LPM parameter metadata uses three distinct canonical concepts: `domain` for
mathematical formula validity, `calibration_range` for the finite operational
search interval, and `prior` for probability mass. Contributor code should use
the prepared-LPM methods `get_calibration_ranges()`, `get_calibration_range()`,
`get_calibration_range_width()`,
`param_within_calibration_range()`, and
`param_within_calibration_range_array()`. Parameter files, runtime objects, and
Python helpers all use `calibration_range`; the former ambiguous name `bounds`
is no longer accepted.

When contributor code needs parameter metadata, it should normally call
`load_parameter_schema()`: the returned typed, immutable object exposes the
shared per-parameter fields (`domain`, `calibration_range`, `init`, `step`, and
`prior`) and the aggregate `calibration_ranges`, `domains`, and
`initial_values` properties. The next major-version source no longer exposes
the former module-level `get_calibration_ranges()`, `get_domains()`,
`get_init()`, or `load_params()` aliases. Use `load_parameter_document()` only
for model-specific YAML fields that are not part of the shared schema; it
returns a defensive, mutable copy of the raw document.

### One unambiguous parameter-definition API

`LPMParameterDefinition` now has one vocabulary at every entry point:

| Concept | Canonical name | Meaning |
| --- | --- | --- |
| Formula validity | `domain` | Every value for which the LPM formula is mathematically defined. It may be open-ended or exclude an endpoint. |
| Calibration search | `calibration_range` | The finite closed interval explored by calibration. It must lie inside `domain`. |

The former word `bounds` was ambiguous because it did not say which of those
two intervals it described. It is therefore rejected in parameter YAML, absent
from `LPMParameterDefinition`, and absent from the module-level helpers. A
misspelling or an old file now fails with a message directing the contributor
to `calibration_range`, instead of being interpreted differently depending on
the route used.

Most code should let `load_parameter_schema()` construct validated definitions
from YAML. Direct construction remains available when a contributor genuinely
needs an in-memory definition, but both concepts must be stated explicitly:

```python
from pyages.data_io.lpm_params import (
    LPMParameterDefinition,
    LPMParameterDomain,
)

parameter = LPMParameterDefinition(
    name="mu",
    domain=LPMParameterDomain(
        minimum=0.0,
        maximum=None,
        minimum_inclusive=False,
    ),
    calibration_range=(0.1, 100.0),
    init=10.0,
    step=1.0,
    prior=None,
)
```

In YAML only, omitting `domain` has one documented shorthand: the closed
`calibration_range` is also used as the mathematical domain. Direct Python
construction deliberately has no such implicit default, because it is the
lower-level API and should make the scientific contract visible at the call
site.

`SingleDateConfig`, `TemporalConfig`, `load_config()`, and
`load_config_payload()` use exactly the schema-3 section names: `data`, `lpm`,
`calibration`, `reporting` when applicable, and `output`. There is no separate
runtime vocabulary. The flattened `LauncherParams`, `LauncherConfig`,
`TemporalParams`, `load_params()`, and `load_params_payload()` views are
removed in 2.0. Older field spellings are rejected; runtime and tooling expose
only the schema-3 vocabulary.

## Compatibility policy

- A public Python symbol or configuration field is deprecated before removal.
- Deprecations are recorded in `CHANGELOG.md` with their planned removal.
- Scientific changes that can alter numerical results require updated golden
  references and a migration note.
- Public workflow directories contain `result_manifest.json`. Its
  `schema_version` field identifies the result layout; incompatible layout
  changes increment that value and are recorded in `CHANGELOG.md`.
  Schema 2 is written after a successful workflow or a required multi-chain
  convergence rejection and fingerprints the configuration, scientific inputs,
  generated artifacts, runtime platform and selected direct-dependency
  versions, Git diff, and complete tracked workspace. Only `status: complete`
  marks success; `status: failed` preserves rejected-run evidence. Reproduce a
  qualified environment from the versioned constraint or environment files;
  the result manifest is not a complete package lock.
- Before version 1.0, incompatible changes may occur in a minor release. From
  version 1.0 onward, incompatible public changes require a major release.

This policy covers the reusable library. Article-reproduction and site
workflows may impose stricter, study-specific reproducibility contracts.
