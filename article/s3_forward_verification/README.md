# Section 3 — forward verification

- **Objective:** validate the forward operator against an independent quadrature.
- **Manuscript output:** Supplement S1 and its numerical tables.
- **Inputs/config:** `validation/tracerlpm/benchmark/inputs/`, `references/`, and `configs/campaign.yaml`.
- **Historical evidence check:** `python article/run_case.py check s3_forward_verification`
- **Post-process:** `python article/run_case.py postprocess s3_forward_verification` (rebuilds the summary from existing case rows; no forward calculation or MCMC).
- **Full run:** `python article/run_case.py run s3_forward_verification`.
- **Stabilized campaign output:** `<campaign>/forward/`.

The archived Supplement S1 itself is final, but its original consolidator did
not preserve every intermediate table separately; see the organization report.

Canonical resources are
`validation/tracerlpm/benchmark/configs/campaign.yaml`, the `inputs/` and
`references/` manifests beside it, and the runner
`validation/tracerlpm/benchmark/scripts/compare_pyages.py`. Existing-output
summaries are rebuilt by `article/common/verify_forward.py`.

## Historical discrepancy metric

The historical 133-comparison campaign calculated
`abs(PyAges - reference) / abs(reference)` when the reference was non-zero and
stored `NaN` when it was zero. It did not apply a `1e-14` denominator floor.
The checksum-protected historical report and its manifests are retained
unchanged; this correction governs current documentation and future PyAges 1.0
campaigns without rewriting the archived evidence.
