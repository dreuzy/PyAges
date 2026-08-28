# Robustness — Holten Dirichlet(1,1,1,1)

- **Objective:** test sensitivity of Holten H4 fractions to a uniform physical-simplex prior.
- **Manuscript output:** separate sensitivity figure and summary tables; not a canonical manuscript result.
- **Inputs/config:** the Holten H4 inputs and constants embedded in `scripts/article/run_holten_prior_robustness.py`.
- **Historical evidence check:** `python -m scripts.article.run_case check holten_prior_dirichlet1`
- **Post-process:** `python -m scripts.article.run_case postprocess holten_prior_dirichlet1`.
- **Full run:** `python -m scripts.article.run_case run holten_prior_dirichlet1` (**costly and intentionally separate**).
- **Historical result:** `results/robustness/holten_prior_dirichlet1/`.

Status is `complete sensitivity evidence`. In the fresh article campaign, all
49 diagnostic groups pass split-Rhat < 1.01 and ESS >= 300. These outputs remain
a distinct robustness analysis and do not replace or modify the canonical
Holten H4 campaign.

This case reuses the canonical Holten H4 inputs without copying them. Its
sensitivity protocol is embedded in `scripts/article/run_holten_prior_robustness.py`
and recorded in the historical manifest; safe rendering uses
`scripts/article/postprocess_existing.py`.
