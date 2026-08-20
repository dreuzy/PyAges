# LPM distribution families

This independent script generates the illustrative Supporting Information
comparison without running a calibration or a Bayesian simulation.

Run from the repository root:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.postprocessing.supporting_information.plot_lpm_distribution_families
```

The matched-median/matched-IQR variant is generated without overwriting the
original outputs:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.postprocessing.supporting_information.plot_lpm_distribution_families_matched_quantiles
```

Matched-quantile caption: Representative transit-time distributions for the
shifted exponential (a) and shifted inverse Gaussian (b) Lumped Parameter
Models. Curves carrying the same number have identical minimum transit-time
shifts, medians, and interquartile ranges. The remaining differences therefore
illustrate the effect of the assumed distribution shape. Parameter values and
distribution statistics are reported in Table Sx. The curves are illustrative
and do not represent site-specific calibrations.

Matched-quantile Supporting Information text: Figure Sx compares shifted
exponential and shifted inverse Gaussian distributions with matched minimum
transit-time shifts, medians, and interquartile ranges. This matching provides
distributions with comparable central transit times and overall central spreads
while preserving their different shapes. The shifted exponential distribution
reaches its maximum immediately after the minimum transit time and then
decreases monotonically. The shifted inverse Gaussian distribution may instead
rise progressively, reach an interior mode, and display a differently shaped
right tail. These differences illustrate the structural uncertainty associated
with the assumed transit-time distribution.

Caption: Representative transit-time distributions for the shifted exponential
(a) and shifted inverse Gaussian (b) Lumped Parameter Models. Numbered curves
represent illustrative combinations of minimum transit-time shift, mean of the
unshifted component (mu), and inverse Gaussian shape parameter (lambda), as
reported in the accompanying parameter table. These combinations span a range
of means, spreads, and distribution shapes and are not site calibrations.

Supporting text: The shifted exponential and shifted inverse Gaussian
distributions were compared over a deliberately diverse set of illustrative
parameter combinations. The shifted exponential distribution has its maximum density
immediately after the minimum transit time and then decreases monotonically. In
contrast, the shifted inverse Gaussian distribution rises progressively after
the shift, reaches an interior maximum, and exhibits a right-skewed tail. These
differences illustrate the structural uncertainty introduced by the assumed
shape of the transit-time distribution. These curves are purely illustrative
and are not calibrations of the Ploemeur site.

The direct four-panel comparison for parameter sets 1, 2, 4, and 6 is generated
from the matched-quantile CSV files with:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.postprocessing.supporting_information.plot_lpm_pairwise_comparison
```

The pairwise figure is also exported as a flattened, LZW-compressed TIFF at
600 dpi for journal submission.

Pairwise caption: Figure Sx. Pairwise comparison of representative shifted
exponential and shifted inverse Gaussian transit-time distributions. Each panel
compares two distributions with identical minimum transit-time shifts, medians,
and interquartile-range widths. Solid red curves represent the shifted
exponential model and dashed green curves the shifted inverse Gaussian model.
Vertical grey lines indicate the common median, and shaded regions represent
the model-specific intervals between the first and third quartiles. The
remaining differences illustrate the effect of the assumed distribution shape.
Parameter values and distribution statistics are reported in Table Sx. The
curves are illustrative and do not correspond to site-specific calibrations.

Pairwise Supporting Information text: Figure Sx directly compares shifted
exponential and shifted inverse Gaussian distributions with matched minimum
transit-time shifts, medians, and interquartile-range widths. The shifted
exponential distribution reaches its maximum immediately after the minimum
transit time and then decreases monotonically. The shifted inverse Gaussian
distribution rises after the minimum transit time, reaches an interior mode,
and exhibits a differently shaped right tail. The pairwise presentation
isolates differences associated with the assumed distribution form while
maintaining comparable central transit times and central spreads.
