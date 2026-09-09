# Ploemeur

The Ploemeur directory contains the site observations, workflow configuration,
and postprocessing used for reproducible field studies. It is not a second
generic PyAges API and should not be copied as an implicit preprocessing recipe
for another site.

Use the two canonical local guides in the repository:

- [`sites/ploemeur/README.md`](https://github.com/dreuzy/PyAges/blob/main/sites/ploemeur/README.md)
  describes the site workflow, data lifecycle, configuration, and quick run;
- [`sites/ploemeur/studies/HYP-26-0172/README.md`](https://github.com/dreuzy/PyAges/blob/main/sites/ploemeur/studies/HYP-26-0172/README.md)
  describes the experiment matrix, dry-run and execution commands, manifests,
  derived tables, publication figures, restart procedure, and interpretation
  limits for the long-term CFC study.

The main site workflow can be inspected without starting a calibration:

```powershell
python -m sites.ploemeur.scripts.ploemeur_driver --help
```

The HYP-26-0172 experiment matrix is also safe to validate before any long
calculation:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.validate_study
python -m sites.ploemeur.studies.HYP-26-0172.scripts.run_matrix `
  --select article_outputs=Figure6
```

`run_matrix` is a dry run unless `--execute` is supplied. Generated results
belong below the configured results root, not in the versioned study directory.
