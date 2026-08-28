# Section 3.1 — PyAges / TracerLPM

- **Objective:** cross-software qualification on matched synthetic cases.
- **Manuscript output:** Table 3 and Supplement S2.
- **Inputs/config:** `validation/tracerlpm/benchmark/configs/` and `inputs/`.
- **Historical evidence check:** `python -m scripts.article.run_case check s3_1_tracerlpm`
- **Post-process:** `python -m scripts.article.run_case postprocess s3_1_tracerlpm`.
- **Full stabilized run:** `python -m scripts.article.reproduce_article resume --output <external-directory>` (**costly and requires the hash-qualified TracerLPM/Excel installation**).
- **Stabilized campaign output:** `<campaign>/tracerlpm/`.

Table 3 evidence is exported explicitly as
`article_package/tables/table3_pyages_tracerlpm_cases.csv`; no historical folder
alias is needed by the stabilized campaign.

Canonical campaign configurations and inputs remain under
`validation/tracerlpm/benchmark/`; external workbook mappings remain under
`validation/tracerlpm/config/`. The report builders live in
`validation/tracerlpm/benchmark/scripts/`, while safe post-processing is routed
through `scripts/article/postprocess_existing.py`.
