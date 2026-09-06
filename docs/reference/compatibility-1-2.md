# Compatibility roadmap for PyAges 1.2

PyAges 1.2 is a compatible minor release, not a PyAges 2.0 release. It retains
the deprecated interfaces published in PyAges 1.x while directing new code to
the canonical APIs below.

## LPM parameter metadata

Load the immutable schema once and read its aggregate properties:

```python
from pyages.data_io.lpm_params import load_parameter_schema

schema = load_parameter_schema("exp", "data_core/data_lpm")
ranges = schema.calibration_ranges
domains = schema.domains
initial_values = schema.initial_values
```

Replace the deprecated calls as follows:

| Deprecated 1.x call | Supported replacement |
| --- | --- |
| `get_calibration_ranges(schema)` | `schema.calibration_ranges` |
| `get_bounds(schema)` | `schema.calibration_ranges` |
| `get_domains(schema)` | `schema.domains` |
| `get_init(schema)` | `schema.initial_values` |
| `load_params(model, directory)` | `load_parameter_document(model, directory)` |

The 1.0.1 flattened configuration symbols (`LauncherParams`,
`load_params()`, and `load_params_payload()`), the temporal `lpm_models.list`
field, `params.yaml` `bounds`, and `pyages run --transient` also remain
available as deprecated aliases. Schema-2 files and new code use the canonical
names documented in the configuration and CLI references.

Each property returns a fresh dictionary. Mutating that dictionary therefore
does not alter the validated schema.

## Compatibility policy

The 1.2 release follows this checklist:

1. repository consumers use the schema properties;
2. the compatibility functions and exports remain available;
3. tests assert that every deprecated accessor still delegates correctly;
4. generated API pages, user documentation, and the changelog identify the
   replacements;
5. each call keeps warning with `DeprecationWarning` without announcing a
   removal in a 1.x release.
