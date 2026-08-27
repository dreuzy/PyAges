# Convolution-grid tolerance sensitivity

> **Follow-up (27 August 2026).** This 133-comparison study remains the
> historical qualification of the default grid controls. The distinct
> 270-case forward matrix now has an explicit two-regime pass/fail contract and
> multi-resolution result in {doc}`forward_qualification_2026-08-27`.

**Qualification date:** 26 August 2026  
**Source commit:** ``17b38579a616f899944441f73d52f9780655648a``  
**Command:** ``python -m scripts.run_article_non_ploemeur s1``

## Question and method

This qualification tests whether the default adaptive tracer-grid tolerances
materially affect PyAges convolution values. The absolute response tolerance,
relative response tolerance, and linear-curvature criterion in
{class}`pyages.config.runtime.TracerGridSettings` were multiplied together by
0.5, 1, or 2. A factor of 0.5 is stricter and normally creates more bins; a
factor of 2 is looser.

Each configuration used the same matrix of 133 tracer/LPM/regime comparisons.
The independent reference uses 32 quantile-space segments with 48-point
Gauss--Legendre integration in each segment. Its probability laws are built
directly from physical parameters with SciPy; it does not call the PyAges
convolution engine. Relative error is

\[
  \epsilon_\mathrm{rel} =
  \frac{|C_\mathrm{PyAges}-C_\mathrm{reference}|}
       {\max(|C_\mathrm{reference}|, 10^{-14})}.
\]

The run used Python 3.12.4, NumPy 2.1.2, SciPy 1.14.1, pandas 2.2.3, and
Matplotlib 3.10.8 on Windows 11. The default settings were
``absolute_tolerance_factor=5e-4``, ``relative_tolerance=0.02``,
``linear_curvature_factor=0.1``, ``max_subdivisions=20``, and
``max_bins=20000``. Complete generated evidence remains under
``results/article_non_ploemeur_final/supplement_s1/``; the compact values are
versioned in {download}`data/convolution_grid_sensitivity_2026-08-26.csv`.

## Results

| factor | comparisons | median relative error | 95th percentile | maximum | median bins | maximum bins | worst case |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.5x | 133 | 1.30e-15 | 2.03e-5 | 1.00e-4 | 566 | 2335 | kr85 / shifted IG / low dispersion |
| 1x | 133 | 1.30e-15 | 3.60e-5 | 1.41e-4 | 308 | 1175 | kr85 / shifted exponential / long tail |
| 2x | 133 | 1.26e-15 | 1.16e-4 | 4.69e-4 | 184 | 595 | kr85 / shifted exponential / long tail |

Median discrepancies are at floating-point round-off level. At the default
settings, the largest observed relative discrepancy is 0.0141%; making all
three controls twice as loose raises it to 0.0469%, while halving them reduces
it to 0.0100%. The expected resolution response is present: the median grid
size changes from 566 bins at 0.5x to 308 at 1x and 184 at 2x.

Wall-clock timings from this execution are not used to compare configurations:
the shared host was heavily loaded and the anomalous 2x duration is not a
property of the numerical method. Bin counts and errors, not those timings,
support the qualification.

## Decision and scope

The default settings are qualified for the tested matrix. A source inventory
found no production or article path that overrides ``TracerGridSettings``;
explicit non-default settings occur only in validation and sensitivity
drivers. No current article result therefore needs a separate non-default
tolerance justification.

This is an empirical qualification, not a universal error bound. A future
calculation that changes a grid setting, adds a sharper tracer history, or
introduces another LPM regime must repeat and archive the sensitivity test.

## Evidence identity

- run manifest SHA-256:
  ``57cafdb8a2f366d2bcdcc520d08081c18e81f07ff9447b7b4ffd15ac4d2f78a5``;
- full tolerance table SHA-256:
  ``2799deceef5eb5d9134b003941962ee1198cc32a6252de9f278236b5bab415ba``;
- generated Supplement S1 SHA-256:
  ``51c24aa80ae3aba39b3d8660b6b837d6da2715b2a65d2334fa07aec1e2e68b5a``.

The equations and boundary conventions are in {doc}`../scientific-methods`;
implementation history is in {doc}`../convolution-method-evolution-report`.
