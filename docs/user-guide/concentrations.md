# Concentration observations

PyAges represents observation data with `pyages.concentrations.Concentrations`.
The object owns a normalized copy of the input table in its `frame` attribute, so
later edits to the source DataFrame do not alter a calibration.

## Canonical table

Concentration files are UTF-8, tab-separated tables with one observation per
row. Their canonical columns are:

| Column | Required in input | Contract |
| --- | --- | --- |
| `element` | yes | non-empty tracer name |
| `concentration` | yes | finite numeric observation |
| `error` | no | finite, non-negative one-sigma uncertainty; defaults to `0.0` |
| `unit` | no | concentration unit; defaults to `mol/l` |
| `date` | yes | finite numeric sampling year |

Extra columns are discarded when the table enters the scientific core. Keep
site identifiers or provenance in the source dataset and select the relevant
rows before constructing `Concentrations`.

```python
import pandas as pd

from pyages.concentrations import Concentrations
from pyages.concentrations.chronicles import ConcentrationChronicle

observations = Concentrations.from_dataframe(
    pd.DataFrame(
        {
            "element": ["cfc11", "cfc12"],
            "concentration": [150.0, 300.0],
            "error": [7.5, 15.0],
            "unit": ["pptv", "pptv"],
            "date": [2010.0, 2010.0],
        }
    )
)
```

Load the same schema from disk with:

```python
observations = Concentrations.from_file("observations.tsv")
```

Invalid numeric values, negative errors, missing tracer names, empty tables,
missing required columns, and duplicate column labels are rejected when the
container is created. Zero error is allowed at this boundary because a
workflow may derive errors before calibration; an objective that divides by
uncertainty requires strictly positive errors.

## Assigning and sampling errors

`set_relative_errors(fraction)` replaces every error with the requested
fraction of the absolute observed concentration. The fraction must be finite
and non-negative.

`fill_missing_errors_from_means(values, fraction=0.01)` fills only zero errors. Supply
exactly one finite, non-negative mean value per observation row. Existing
positive errors are preserved.

Gaussian perturbations require an explicit NumPy generator, making the random
stream visible and reproducible:

```python
import numpy as np

sampled = observations.sample_with_errors(np.random.default_rng(12345))
```

The sampled object is independent from `observations`. Gaussian draws are not
truncated, so a large uncertainty can produce a negative sampled value; that is
a property of the selected observation-error model, not a concentration-table
validation failure.

`observation_keys()` returns stable result-column names in the form
`tracer@date#index`, for example `cfc11@2010.0#0`. The index distinguishes
replicate observations. Reachable-model tables, which contain one value per
tracer and date, use `tracer@date` without rounding the date.

## Time series and wide exports

`ConcentrationChronicle(observations=observations)` groups the long table by tracer for
chronicle plots. Alternatively, construct it with exactly one pre-grouped
mapping through `ConcentrationChronicle(series=series)`.

Long observation tables may contain replicate measurements for the same tracer
and date. A wide table has no replicate identifier, however, so
`save()` rejects duplicate tracer/date pairs instead of performing a
many-to-many merge that would silently multiply rows. Aggregate replicates or
retain them in long form before requesting a wide export.

The modules below `pyages.concentrations.utils` and the high-level chronicle
display functions are contributor interfaces. The supported user interface is
the `Concentrations` class exported by `pyages.concentrations`.
