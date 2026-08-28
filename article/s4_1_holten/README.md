# Section 4.1 — Holten H4

- **Objective:** reproduce the four-bin Holten benchmark for seven wells.
- **Manuscript output:** Figure 3 and quantitative comparison tables.
- **Inputs/config:** `examples/natural/holten/doc/` and `examples/natural/holten/holten.yaml`.
- **Historical evidence check:** `python -m scripts.article.run_case check s4_1_holten`
- **Post-process:** `python -m scripts.article.run_case postprocess s4_1_holten`.
- **Full run:** `python -m scripts.article.run_case run s4_1_holten` (**costly: five chains per well**).
- **Stabilized campaign output:** `<campaign>/holten_h4/`.

The canonical configuration is `examples/natural/holten/holten.yaml`; inputs
remain under `examples/natural/holten/doc/` and their hashes are recorded in
each new campaign manifest. The scientific runner is
`scripts/article/run_final_holten_h4.py`, while safe rendering uses
`scripts/article/postprocess_existing.py`.
