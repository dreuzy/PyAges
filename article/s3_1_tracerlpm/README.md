# Section 3.1 — PyAge / TracerLPM

- **Objective:** cross-software qualification on matched synthetic cases.
- **Manuscript output:** Table 3 and Supplement S2.
- **Inputs/config:** `validation/tracerlpm/benchmark/configs/` and `inputs/`.
- **Check:** `python article/run_case.py check s3_1_tracerlpm`
- **Post-process:** `python article/run_case.py postprocess s3_1_tracerlpm`.
- **Full run:** `python article/run_case.py run s3_1_tracerlpm` (**costly and only partial without the external TracerLPM/Excel execution**).
- **Historical canonical result:** `results/article_non_ploemeur_final/`.

The historical folder names `table3/` and `figure2/` predate the current
manuscript numbering. They are retained unchanged.

Canonical campaign configurations and inputs remain under
`validation/tracerlpm/benchmark/`; external workbook mappings remain under
`validation/tracerlpm/config/`. The report builders live in
`validation/tracerlpm/benchmark/scripts/`, while safe post-processing is routed
through `article/common/postprocess_existing.py`.
