# Robustness — Holten Dirichlet(1,1,1,1)

- **Objective:** test sensitivity of Holten H4 fractions to a uniform physical-simplex prior.
- **Manuscript output:** separate sensitivity figure and summary tables; not a canonical manuscript result.
- **Inputs/config:** the Holten H4 inputs and constants embedded in `scripts/run_holten_prior_robustness.py`.
- **Check:** `python article/run_case.py check holten_prior_dirichlet1`
- **Post-process:** `python article/run_case.py postprocess holten_prior_dirichlet1`.
- **Full run:** `python article/run_case.py run holten_prior_dirichlet1` (**costly and intentionally separate**).
- **Historical result:** `results/robustness/holten_prior_dirichlet1/`.

Status is `unvalidated`; do not merge these outputs into the final Holten H4
campaign until scientific review is complete.

This case reuses the canonical Holten H4 inputs without copying them. Its
sensitivity protocol is embedded in `scripts/run_holten_prior_robustness.py`
and recorded in the historical manifest; safe rendering uses
`article/common/postprocess_existing.py`.
