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

Contributor code that compares independently prepared calibration targets
imports the signature records and
`build_calibration_target_signature()` from
`pyages.calibration.target_signature`. Signature records and their
schema-version constant have this single canonical module; the problem module
does not provide compatibility aliases.

The contributor facade `pyages.calibration.methods.mh` exposes the immutable
`MHRunRecord` produced by the ensemble engine. That record owns the exact chain
and ensemble configurations consumed by serialization; writers do not accept a
second configuration source. The experimental `MHEnsembleResult`,
`ProblemFactory`, and workflow builder aliases were removed before release of
the multi-chain feature. Internal callable protocols and path/configuration
builders now use private names.

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
