# Public API and compatibility

PyAge deliberately exposes a small supported surface. This keeps scientific
workflows understandable and leaves implementation details free to evolve.

## Supported interfaces

The following interfaces are intended for users:

- the `pyage` command and its documented subcommands;
- `pyage.__version__`;
- the symbols exported by `pyage.convolution.__all__`;
- `pyage.lpm.lpm_build.lpm_build` and `list_available_lpms`;
- `pyage.tracer.tracer_root.Tracer`;
- `pyage.concentrations.concentrations.Concentrations`, constructed with
  `from_file()` or `from_dataframe()`;
- the validated models exported by `pyage.config`;
- documented YAML configuration fields and documented result files.

Modules below `core`, `utils`, private names beginning with `_`, site-specific
code, examples, and repository scripts are implementation or research
interfaces. They can evolve without a compatibility alias.

The generated API reference also documents selected contributor interfaces.
Being present there does not by itself make a symbol part of the supported
public surface above.

## Compatibility policy

- A public Python symbol or configuration field is deprecated before removal.
- Deprecations are recorded in `CHANGELOG.md` with their planned removal.
- Scientific changes that can alter numerical results require updated golden
  references and a migration note.
- Public workflow directories contain `result_manifest.json`. Its
  `schema_version` field identifies the result layout; incompatible layout
  changes increment that value and are recorded in `CHANGELOG.md`.
- Before version 1.0, incompatible changes may occur in a minor release. From
  version 1.0 onward, incompatible public changes require a major release.

This policy covers the reusable library. Article-reproduction and site
workflows may impose stricter, study-specific reproducibility contracts.
