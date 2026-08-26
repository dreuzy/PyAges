# Section 3 — forward verification

- **Objective:** validate the forward operator against an independent quadrature.
- **Manuscript output:** Supplement S1 and its numerical tables.
- **Inputs/config:** `validation/tracerlpm/benchmark/inputs/`, `references/`, and `configs/campaign.yaml`.
- **Check:** `python article/run_case.py check s3_forward_verification`
- **Post-process:** `python article/run_case.py postprocess s3_forward_verification` (rebuilds the summary from existing case rows; no forward calculation or MCMC).
- **Full run:** `python article/run_case.py run s3_forward_verification`.
- **Historical canonical result:** `results/article_non_ploemeur_final/supplement_s1/`.

The archived Supplement S1 itself is final, but its original consolidator did
not preserve every intermediate table separately; see the organization report.

Canonical resources are
`validation/tracerlpm/benchmark/configs/campaign.yaml`, the `inputs/` and
`references/` manifests beside it, and the runner
`validation/tracerlpm/benchmark/scripts/compare_pyage.py`. Existing-output
summaries are rebuilt by `article/common/verify_forward.py`.
