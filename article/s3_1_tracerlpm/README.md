# Section 3.1 — PyAge / TracerLPM

- **Objective:** cross-software qualification on matched synthetic cases.
- **Manuscript output:** Table 3 and Supplement S2.
- **Inputs/config:** `validation/tracerlpm/benchmark/configs/` and `inputs/`.
- **Check:** `python article/run_case.py check s3_1_tracerlpm`
- **Post-process:** `python article/run_case.py postprocess s3_1_tracerlpm`.
- **Full stabilized run:** `python -m scripts.reproduce_article resume --output <external-directory>` (**costly and requires the hash-qualified TracerLPM/Excel installation**).
- **Stabilized campaign output:** `<campaign>/tracerlpm/`.

Table 3 evidence is exported explicitly as
`article_package/tables/table3_pyage_tracerlpm_cases.csv`; no historical folder
alias is needed by the stabilized campaign.

Canonical campaign configurations and inputs remain under
`validation/tracerlpm/benchmark/`; external workbook mappings remain under
`validation/tracerlpm/config/`. The report builders live in
`validation/tracerlpm/benchmark/scripts/`, while safe post-processing is routed
through `article/common/postprocess_existing.py`.
