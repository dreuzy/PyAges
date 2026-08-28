# Direct convolution

This page covers programmatic forward calculations with the supported
`pyages.convolution` API. The normative equations and numerical conventions
remain in {doc}`../scientific-methods`; this page focuses on using the API.

## One tracer and one date

```python
from pyages.config.paths import DIRECTORY_TRACER_DATA
from pyages.convolution import Convolution
from pyages.lpm import build_lpm
from pyages.tracer.tracer_root import Tracer

tracer = Tracer(DIRECTORY_TRACER_DATA, name="cfc11")
lpm = build_lpm("exp")
convolution = Convolution(tracer, date=2010.0)

concentration = convolution.convolve(lpm)
represented_mass = convolution.window_mass(lpm)
diagnostics = convolution.diagnostics
```

The observation date is a finite decimal year and cannot precede
`tracer.datemin`. Dates newer than `tracer.datemax` are allowed: a chronicle
tracer contributes zero recharge outside its declared range, while configured
production still follows the tracer response law.

The integration window is `[0, date - tracer.datemin]`. Probability mass older
than that window contributes zero and is not renormalized. Consequently,
`represented_mass < 1` can explain a reduced modeled concentration for a short
input history.

## Diagnostics and prepared grids

After a continuous or mixed convolution, `convolution.diagnostics` contains:

| Field | Meaning |
| --- | --- |
| `window_mass` | LPM probability mass represented by the tracer history |
| `n_bins` | Number of cached tracer-response bins used |
| `min_weight` | Smallest raw CDF bin difference before roundoff clipping |
| `clipped_weight_count` | Number of roundoff-sized negative weights clipped |

Pure Dirac and double-Dirac paths return `None` for `diagnostics` because they
do not use an integration grid. `window_mass(lpm)` remains available for every
strategy.

`convolution.prepare()` eagerly constructs the tracer-only grid. Repeated LPM
evaluations at the same observation date reuse it, which is useful in
calibration loops. The returned `PreparedTracerGrid` and its NumPy arrays are
read-only snapshots. Assigning a new `convolution.date` invalidates the cached
grid and diagnostics.

## A date range

```python
frame = convolution.convolve_date_range(
    lpm,
    2000.0,
    2005.0,
    resolution=5,
)
```

`resolution` is the number of equal intervals, so this example returns six
rows including both endpoints. It must be an integer greater than or equal to
one. The method restores the original `convolution.date` before returning,
including when an evaluation raises an exception.

## Several tracers

```python
from pyages.convolution import ConvolutionTracers

tracers = ConvolutionTracers(
    names=["cfc11", "cfc12", "sf6"],
    date=[2010.0, 2010.0, 2012.0],
)

values = tracers.convolve(lpm, return_type="array")
table = tracers.convolve(lpm, return_type="dataframe")
observations = tracers.convolve(lpm, return_type="concentrations")
```

The `array` return type is a list ordered like `names`. Use `concentrations`
when units and sampling dates must remain attached to the values. An unknown
return type is rejected before numerical work begins.

## Numerical controls

```python
from pyages.convolution import ConvolutionSettings

settings = ConvolutionSettings(
    absolute_tolerance_factor=2.5e-4,
    relative_tolerance=1.0e-2,
)
convolution = Convolution(tracer, date=2010.0, grid_settings=settings)
```

These controls cover both tracer-grid preparation and continuous integration;
they do not sample the LPM density and are not a formal total-error bound. Keep
the defaults unless a documented sensitivity study supports another choice.
Publication calculations using non-default settings should record every value
and archive a convergence comparison.

## Errors that stop a calculation

PyAges rejects non-finite dates, tracer responses, Dirac ages, CDF or moment
values; invalid mixture weights; non-monotonic or out-of-bounds CDFs; and
inconsistent partial first moments. These are model-contract failures rather
than missing-history truncation. A legitimate old tail is represented by a
finite `window_mass` below one, not by an exception.
