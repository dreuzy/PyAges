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
  `from_dataframe()`; the former
  `pyages.concentrations.concentrations.Concentrations` import remains the same
  class;
- the validated models exported by `pyages.config`;
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

## Compatibility policy

- A public Python symbol or configuration field is deprecated before removal.
- Deprecations are recorded in `CHANGELOG.md` with their planned removal.
- Scientific changes that can alter numerical results require updated golden
  references and a migration note.
- Public workflow directories contain `result_manifest.json`. Its
  `schema_version` field identifies the result layout; incompatible layout
  changes increment that value and are recorded in `CHANGELOG.md`.
  Schema 2 is written only after a successful workflow and fingerprints the
  configuration, scientific inputs, generated artifacts, runtime platform and
  selected direct-dependency versions, Git diff, and complete tracked
  workspace. Reproduce a qualified environment from the versioned constraint
  or environment files; the result manifest is not a complete package lock.
- Before version 1.0, incompatible changes may occur in a minor release. From
  version 1.0 onward, incompatible public changes require a major release.

This policy covers the reusable library. Article-reproduction and site
workflows may impose stricter, study-specific reproducibility contracts.
