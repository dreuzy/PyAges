# Archived article-development material

This directory preserves scripts and configurations that were used before the
experiment matrix became the authoritative HYP-26-0172 workflow.

They are kept for provenance only. New runs and publication figures must use:

- `../experiment_matrix.csv` for experiment selection;
- `../params/` for configurations;
- `../postprocessing/build_products.py` for derived tables and figures.

Legacy scripts may search historical output folders and therefore do not meet
the reproducibility contract of the finalized study.
