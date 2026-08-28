# Section 3.2 — shifted exponential

- **Objective:** quantify Bayesian uncertainty and identifiability for 19 synthetic cases.
- **Manuscript output:** Figure 2 and Table 4.
- **Inputs/config:** four distributed tracer chronicles and `data_core/data_lpm/exp_shifted/params.yaml`.
- **Historical evidence check:** `python -m scripts.article.run_case check s3_2_shifted_exponential`
- **Post-process:** `python -m scripts.article.run_case postprocess s3_2_shifted_exponential`.
- **Full run:** `python -m scripts.article.run_case run s3_2_shifted_exponential` (**costly: 19 pilots and 95 production chains**).
- **Stabilized campaign output:** `<campaign>/shifted_exponential/`.

The generated Table 4 files are named `table4_final.csv` and
`table4_final.md`; no historical Table 3 alias is produced.

The canonical model configuration is
`data_core/data_lpm/exp_shifted/params.yaml`; tracer inputs remain under
`data_core/data_tracer/{cfc11,cfc12,cfc113,sf6}/`. The scientific runner is
`scripts/article/run_final_shifted_exponential.py`, with run parameters frozen in each
new campaign manifest.
