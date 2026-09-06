# Planned API migration for PyAges 2.0

This page is a migration plan, not a PyAges 2.0 release announcement. PyAges
1.x continues to provide the deprecated functions below so callers have a
normal deprecation period.

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
| `get_domains(schema)` | `schema.domains` |
| `get_init(schema)` | `schema.initial_values` |

Each property returns a fresh dictionary. Mutating that dictionary therefore
does not alter the validated schema.

## Maintainer removal checklist

Removal belongs to the major-version release change, not to a 1.x cleanup:

1. confirm repository consumers use the schema properties;
2. remove the three compatibility functions and their exports;
3. replace deprecation tests with tests of their absence from the 2.0 API;
4. update generated API pages, examples, and the changelog;
5. perform the explicit major-version release change;
6. run the full contributor profile and applicable scientific qualification.

Until those steps are performed for PyAges 2.0, the compatibility functions
must keep warning with `DeprecationWarning` and returning the same fresh values
as the schema properties.
