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
| `unit` | yes | explicit concentration unit, consistent for each tracer |
| `date` | yes | finite numeric sampling year |

Extra columns are discarded when the table enters the scientific core. Keep
site identifiers or provenance in the source dataset and select the relevant
rows before constructing `Concentrations`.

```python
import pandas as pd

from pyages.concentrations import ConcentrationChronicle, Concentrations

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

Invalid numeric values, negative errors, missing tracer names or units, empty
tables, inconsistent units for one tracer, missing required columns, and
duplicate column labels are rejected when the container is created. Zero error
is allowed at this boundary because a workflow may derive errors before
calibration; an objective that divides by uncertainty requires strictly
positive errors.

## Unit boundary

Units are checked only when data enter the API and when observations first meet
their modeled tracers. They are not carried through convolution arrays or
checked inside optimization and sampling loops.

Known units use one canonical spelling: for example `pptv`, `TU`, `pmC`,
`fraction_modern`, `mol/l`, `Bq/L`, and `dpm/ccKr`. A spelling such as `tu` or
the historical `pCm%` is rejected with the canonical spelling in the error
message. Custom unit labels such as `pmol/kg` are accepted, but a custom
observation and its custom tracer must declare exactly the same label.

PyAges compares labels but never converts concentration values implicitly. For
example, the standard CFC tracer produces atmospheric-equivalent `pptv`. An
observation expressed as dissolved `pmol/kg` is rejected before calibration:

```text
Unit mismatch for tracer 'cfc11': observations use 'pmol/kg',
model uses 'pptv'.
```

That conversion depends on physical preprocessing assumptions such as
temperature, pressure, salinity, and excess air. It must therefore be performed
and documented before constructing the calibration problem. This one-time
boundary policy prevents unit mistakes without adding work to each objective
evaluation.

The explicit container-level check is `require_matching_units()`. It compares
labels once and does not transform the data:

```python
observations.require_matching_units({"cfc11": "pptv", "cfc12": "pptv"})
```

Workflow entry points call the same contract after loading their modeled
tracers. Objective and sampling loops therefore receive already-validated
numeric arrays.

## Assigning and sampling errors

`set_relative_errors(fraction)` replaces every error with the requested
fraction of the absolute observed concentration. The fraction must be finite
and non-negative.

`fill_missing_errors_from_means(values, fraction=0.01)` fills only zero errors. Supply
exactly one finite, non-negative mean value per observation row. Existing
positive errors are preserved.

Both assignment methods append a structured event to
`observations.error_provenance`, including the method, fraction, affected row
indices, and row count. Public workflows expose the fallback as
`dataset.missing_error_rel` and copy these events into the result manifest.

Zero-truncated Gaussian perturbations require an explicit NumPy generator,
making the random stream visible and reproducible:

```python
import numpy as np

sampled = observations.sample_with_errors(np.random.default_rng(12345))
```

The sampled object is independent from `observations`. Each stochastic value
follows the Gaussian observation-error model conditioned on a non-negative
concentration. This is a true truncated distribution: negative draws are not
clipped to zero, so the result has no artificial accumulation of exact zeros.
A non-negative row with zero error remains unchanged. A negative concentration
with zero error cannot define this distribution and is rejected when sampling.

`observation_keys()` returns stable result-column names in the form
`tracer@date#index`, for example `cfc11@2010.0#0`. The index distinguishes
replicate observations. Reachable-model tables, which contain one value per
tracer and date, use `tracer@date` without rounding the date.

`observation_tracer_names()` returns one tracer name per observation row and is
therefore aligned with concentration, error, and date arrays.
`unique_tracer_names()` returns each tracer once, preserving first-observation
order; use it for displays and tracer-level metadata.

## Time series and wide exports

`ConcentrationChronicle(observations=observations)` groups the long table by tracer for
chronicle plots. Alternatively, construct it with exactly one pre-grouped
mapping through `ConcentrationChronicle(series=series)`.

Long observation tables may contain replicate measurements for the same tracer
and date. A wide table has no replicate identifier, however, so
`save()` rejects duplicate tracer/date pairs instead of performing a
many-to-many merge that would silently multiply rows. Aggregate replicates or
retain them in long form before requesting a wide export.

The `series`, `temporal`, and `plotting` modules are contributor interfaces.
High-level file and figure orchestration lives under
`pyages.reporting.chronicles`; concentration serialization lives in
`pyages.data_io.concentrations`. The supported user interface consists of the
`Concentrations` and `ConcentrationChronicle` classes exported by
`pyages.concentrations`.
