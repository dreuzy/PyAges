# Ploemeur data workflow

For provenance, attribution, and redistribution conditions, see
[`NOTICE-DATA.md`](../../../NOTICE-DATA.md).

Data lifecycle (source → outputs):

```
Excel (.xlsx) in data/brut/
  → manual updates → data/brut/*.txt
    → normalization script → data/ori/ori_ploemeur_{well}_{start}_{end}.txt
      → workflow selection → OS temp/pyage-ploemeur-*/{well}_{start}_{end}
```

Notes
- The source data comes from the Excel files in this folder.
- The raw text files are maintained manually in `data/brut/`.
- The normalization step is performed by:
  - `python -m sites.ploemeur.scripts.prepare_observations`
- Selection files are generated in a unique operating-system temporary
  directory for each simulation run. They are removed after all worker
  processes finish and are never written to the repository data directory.
