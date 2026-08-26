# Section 4.2 — Ploemeur CFC

- **Objective:** benchmark the Ploemeur F09/F11 CFC time series and independent 2014–2015 windows.
- **Manuscript output:** Figure 4, posterior summaries, fit and pairing diagnostics.
- **Inputs/config:** `sites/ploemeur/data/`, `sites/ploemeur/params/`, and archived Article selections recorded by the manifest.
- **Check:** `python article/run_case.py check s4_2_ploemeur`
- **Post-process:** `python article/run_case.py postprocess s4_2_ploemeur`.
- **Full run:** `python article/run_case.py run s4_2_ploemeur` (**costly: four five-chain calibrations**).
- **Stabilized campaign outputs:** `<campaign>/ploemeur_shifted_exponential/`
  and `<campaign>/ploemeur_physical_ig/`.

`results/ploemeur_figure4_final/` is an older, separate Figure 4 generation and
is not silently substituted for the canonical shifted-exponential campaign.

Site configurations and observations remain under `sites/ploemeur/`; the
run-specific selection audit is stored with the canonical results. The
scientific runner is `scripts/run_ploemeur_shifted_exponential_final.py`, while
safe rendering uses `article/common/postprocess_existing.py`.
