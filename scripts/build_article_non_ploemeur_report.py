# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build the final article report and artifact inventory for the final run."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "results" / "article_non_ploemeur_final"
TRACERLPM = ROOT / "validation" / "tracerlpm" / "benchmark"
HOLTEN = (
    ROOT / "examples" / "natural" / "holten" / "generated" / "benchmark" / "four_bin"
)


def _markdown(frame: pd.DataFrame) -> str:
    values = frame.copy().replace({np.nan: ""})
    headers = [str(column).replace("|", "\\|") for column in values.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in values.itertuples(index=False, name=None):
        lines.append(
            "| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |"
        )
    return "\n".join(lines)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def _table(path: Path, limit: int | None = None) -> str:
    if not path.exists():
        return f"Livrable manquant: `{path}`."
    frame = pd.read_csv(path)
    if limit is not None:
        frame = frame.head(limit)
    return _markdown(frame)


def _tracerlpm_summary(run: Path) -> tuple[str, str]:
    results_path = run / "robustness_480" / "new" / "results.csv"
    if not results_path.exists():
        results_path = TRACERLPM / "generated" / "robustness-study" / "results.csv"
    if not results_path.exists():
        return "Résultats de robustesse manquants.", "Résultats détaillés manquants."
    frame = pd.read_csv(results_path)
    counts = {
        "cases": int(len(frame)),
        "models": sorted(frame["model"].astype(str).unique().tolist()),
        "noise": sorted(frame["noise_relative_sd"].astype(float).unique().tolist()),
    }
    numeric = frame.select_dtypes(include=[np.number])
    summary = pd.DataFrame(
        {
            "metric": numeric.columns,
            "median": [float(numeric[column].median()) for column in numeric],
            "p95": [float(numeric[column].quantile(0.95)) for column in numeric],
            "maximum": [float(numeric[column].max()) for column in numeric],
        }
    )
    main = f"Campagne appariée: {counts['cases']} cas; modèles {counts['models']}; niveaux de bruit {counts['noise']}.\n\n"
    main += _markdown(
        summary.loc[
            summary["metric"].str.contains("objective|error|boundary", case=False)
        ]
    )
    no_noise_path = (
        run / "inversion_four_tracer" / "pyages_tracerlpm_no_noise_parameters.csv"
    )
    if no_noise_path.exists():
        no_noise = pd.read_csv(no_noise_path)
        main += "\n\n### Qualification finale sans bruit et contrôles aveugles\n\n"
        main += _markdown(no_noise)
    supplement = "# Supplement S2 — qualification PyAges–TracerLPM\n\n"
    supplement += "Les pseudo-observations proviennent de la quadrature Gauss–Legendre indépendante segmentée. "
    supplement += "Les quatre traceurs CFC-11, CFC-12, CFC-113 et SF6 sont utilisés dans la campagne finale.\n\n"
    supplement += "Le consolidateur refuse un cas si les pseudo-observations remises aux deux outils diffèrent de plus de `1e-12`.\n\n"
    supplement += "## Transformations\n\n"
    supplement += "EPM: `eta=1+r`, `mu=tau/eta`, `shift=tau*(1-1/eta)`.  "
    supplement += "DM: `mu=tau`, `sigma=tau*sqrt(2*DP)`.\n\n"
    supplement += (
        "## Objectifs\n\n"
        "PyAges minimise sa L2 pondérée native; TracerLPM minimise sa somme L1 "
        "relative native. Pour rendre les sorties comparables, "
        "`sum(abs((Cmod-Cobs)/Cobs))` et "
        "`sum(((Cmod-Cobs)/Cobs)^2)` sont aussi recalculées pour les deux outils "
        "et conservées pour chaque cas.\n\n"
    )
    supplement += "## Bornes, initialisations et seeds\n\nLes YAML de campagne sont normatifs; les seeds 401–410 sont appariées. "
    supplement += (
        "Les contrôles aveugles sont dans `inversion-final-four-tracer-blind.yaml`.\n\n"
    )
    supplement += "## Résultats détaillés\n\n"
    supplement += _markdown(frame)
    if no_noise_path.exists():
        supplement += "\n\n## Cas sans bruit et départs aveugles\n\n"
        supplement += _markdown(pd.read_csv(no_noise_path))
    return main, supplement


def _holten_summary(run: Path) -> str:
    holten = run / "holten" / "new"
    posterior = holten / "holten_4bin_mh_summary.csv"
    comparison = holten / "holten_4bin_paper_vs_mh.csv"
    modeled = holten / "holten_4bin_modeled_vs_observed.csv"
    old_summary_path = run / "holten" / "old" / "holten_4bin_mh_summary.csv"
    old_new_text = "Comparaison historique indisponible."
    if old_summary_path.exists() and posterior.exists():
        old_new = pd.read_csv(old_summary_path).merge(
            pd.read_csv(posterior), on="well_id", suffixes=("_old", "_new")
        )
        changes = []
        for metric in (
            "f_0_20_median",
            "f_20_40_median",
            "f_40_60_median",
            "f_old_median",
        ):
            difference = (old_new[f"{metric}_new"] - old_new[f"{metric}_old"]).abs()
            index = int(difference.idxmax())
            changes.append(
                {
                    "fraction": metric.removesuffix("_median"),
                    "maximum_absolute_old_new_difference": float(difference.loc[index]),
                    "well": old_new.loc[index, "well_id"],
                }
            )
        old_new_text = (
            "Les écarts ancienne/nouvelle calibration ne sont pas négligeables, car "
            "l'ancienne version employait aussi l'observable hélium. La version finale "
            "calibre uniquement 3H, 85Kr et 39Ar; l'hélium reste diagnostique.\n\n"
            + _markdown(pd.DataFrame(changes))
        )
    return (
        "### Périmètre et comparaison ancienne/nouvelle\n\n" + old_new_text + "\n\n"
        "### Médianes et intervalles des quatre fractions\n\n"
        + _table(posterior)
        + "\n\n### Comparaison Visser et al.\n\n"
        + _table(comparison)
        + "\n\n### Concentrations modélisées\n\n"
        + _table(modeled)
    )


def _inventory(run: Path) -> pd.DataFrame:
    manifest = run / "run_manifest.yaml"
    manifest_hash = _sha(manifest)
    rows = []
    for path in sorted(item for item in run.rglob("*") if item.is_file()):
        if path.name == "artifact_inventory.csv":
            continue
        relative = path.relative_to(run)
        if path.name.startswith("~$") or (
            "work" in relative.parts
            and any(part.startswith("tracerlpm_") for part in relative.parts)
        ):
            continue
        rows.append(
            {
                "artifact": relative.as_posix(),
                "sha256": _sha(path),
                "bytes": path.stat().st_size,
                "run_manifest_sha256": manifest_hash,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(run / "artifact_inventory.csv", index=False)
    return frame


def _write_holten_old_new(run: Path) -> Path | None:
    old_path = run / "holten" / "old" / "holten_4bin_mh_summary.csv"
    new_path = run / "holten" / "new" / "holten_4bin_mh_summary.csv"
    if not old_path.exists() or not new_path.exists():
        return None
    old = pd.read_csv(old_path).set_index("well_id")
    new = pd.read_csv(new_path).set_index("well_id")
    rows = []
    numeric_columns = [
        column
        for column in old.select_dtypes(include=[np.number]).columns
        if column in new.select_dtypes(include=[np.number]).columns
    ]
    for well_id in old.index.intersection(new.index):
        for column in numeric_columns:
            old_value = float(old.loc[well_id, column])
            new_value = float(new.loc[well_id, column])
            difference = abs(new_value - old_value)
            rows.append(
                {
                    "well_id": well_id,
                    "column": column,
                    "old_value": old_value,
                    "new_value": new_value,
                    "absolute_difference": difference,
                    "relative_difference": difference / abs(old_value)
                    if old_value
                    else np.nan,
                }
            )
    path = run / "holten" / "holten_old_new_all_numeric_columns.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_robustness_old_new(run: Path) -> Path | None:
    old_path = run / "robustness_480" / "old" / "results.csv"
    new_path = run / "robustness_480" / "new" / "results.csv"
    if not old_path.exists() or not new_path.exists():
        return None
    old = pd.read_csv(old_path).set_index("case_id")
    new = pd.read_csv(new_path).set_index("case_id")
    common_cases = old.index.intersection(new.index)
    numeric_columns = [
        column
        for column in old.select_dtypes(include=[np.number]).columns
        if column in new.select_dtypes(include=[np.number]).columns
    ]
    rows = []
    for case_id in common_cases:
        for column in numeric_columns:
            old_value = float(old.loc[case_id, column])
            new_value = float(new.loc[case_id, column])
            difference = abs(new_value - old_value)
            rows.append(
                {
                    "case_id": case_id,
                    "column": column,
                    "old_value": old_value,
                    "new_value": new_value,
                    "absolute_difference": difference,
                    "relative_difference": difference / abs(old_value)
                    if old_value
                    else np.nan,
                }
            )
    path = run / "robustness_480" / "old_new_all_numeric_columns.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def build(run: Path) -> Path:
    run = run.resolve()
    if any(re.match(r"^ploemeur(?:_|$)", part.lower()) for part in run.parts):
        raise ValueError(f"Excluded path: {run}")
    manifest_path = run / "run_manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    _write_holten_old_new(run)
    _write_robustness_old_new(run)
    tracerlpm_main, supplement_s2 = _tracerlpm_summary(run)
    (run / "supplement_s2.md").write_text(supplement_s2, encoding="utf-8", newline="\n")
    s1 = _read(run / "supplement_s1" / "supplement_s1.md", "Supplement S1 manquant.")
    table3 = _read(run / "table3" / "table3_final.md", "Table 3 manquante.")
    figure2 = _read(
        run / "figure2" / "figure2_manifest.json", "Manifeste Figure 2 manquant."
    )
    tests = _read(run / "tests_summary.md", "Synthèse des tests manquante.")
    report = f"""# Final non-Ploemeur article run

## 1. Version exacte du code et manifeste

- Base Git: `{manifest["git"]["base_sha"]}`
- Dirty: `{manifest["git"]["dirty"]}`
- Diff global SHA-256: `{manifest["git"]["tracked_diff_sha256"]}`
- Diff du périmètre du run SHA-256: `{manifest["git"].get("run_scoped_tracked_diff_sha256", manifest["git"]["tracked_diff_sha256"])}`
- Snapshot workspace SHA-256: `{manifest["git"]["workspace_snapshot_sha256"]}`
- Manifeste complet: `run_manifest.yaml`

Tous les fichiers de ce run sont reliés au manifeste par `artifact_inventory.csv`.
Le contrôle antérieur aux calculs est consigné dans `preflight_audit.md`.

## 2. Supplement S1 — validation numérique, tolérances et performances

{s1}

## 3. Nouvelle Table 3

{table3}

La comparaison exhaustive des colonnes numériques est dans
`table3/table3_old_new_all_numeric_columns.csv`.

## 4. Nouvelle Figure 2

La figure utilise `x=mu`, `y=t0`; la cible est `(10,30)`. La couleur est
`sqrt(J_data/m)` avec `m=4` et les échantillons affichés sont ceux de la chaîne MCMC réelle.

```json
{figure2}
```

## 5. Benchmark inverse PyAges–TracerLPM

{tracerlpm_main}

Le détail complet et les conventions sont dans `supplement_s2.md`.

## 6. Supplement S2 — qualification détaillée

Le Supplement S2 complet est généré dans `supplement_s2.md`. Il contient les
480 lignes détaillées, les objectifs natifs et recalculés, les concentrations,
les bornes, les seeds et les contrôles sans bruit/aveugles.

## 7. Holten et nouvelle Figure 3

{_holten_summary(run)}

La Figure 3 régénérée est `holten/figure3_holten_4bin_posteriors.png`; la comparaison
exhaustive ancienne/nouvelle est `holten/holten_old_new_all_numeric_columns.csv`.

## 8. Suppression des anciens identifiants shifted-exponential

Les sources, scripts, configurations, documentations, notebooks et tests actifs
ne contiennent plus `exp_shifted_old` ni `exp_shifted_young`. Les variantes de
démarrage sont documentées comme sensibilités d'initialisation de `exp_shifted`.
Le périmètre et le résultat de recherche sont consignés dans `identifier_audit.md`.

## 9. Tests finaux hors Ploemeur

{tests}

## 10. Comparaisons old/new

- Table 3: `table3/table3_old_new_all_numeric_columns.csv`;
- Figure 2: ancien fond `0.5 ln(J)` remplacé par la grandeur prescrite;
- Holten: `holten/holten_old_new_all_numeric_columns.csv`;
- PyAges–TracerLPM: `robustness_480/old_new_all_numeric_columns.csv` et résultats
  détaillés avec objectifs recalculés dans le CSV S2.

## 11. Modifications à reporter dans le manuscrit

1. Remplacer la description PDF+Simpson par la grille pilotée par `K`, les masses CDF et les moments partiels.
2. Définir l'Inverse Gaussian par sa moyenne et son écart-type physiques.
3. Corriger la définition du mélange Dirac–exponentielle et retirer les deux faux modèles shifted-exponential.
4. Donner les unités 3H = TU et 39Ar = `fraction_modern`; documenter CFC-12 comme stable.
5. Remplacer tous les nombres de Table 3 par `table3/table3_final.csv`.
6. Remplacer Figure 2 et sa légende: cible `(mu,t0)=(10,30)`, quatre traceurs, erreur 8 %, couleur `sqrt(J_data/4)`.
7. Remplacer l'ancienne convergence Simpson de S1 par les invariants, la matrice indépendante, la sensibilité 0.5×/1×/2× et les performances multi-LPM.
8. Mettre à jour S2 avec quatre traceurs partout, les transformations EPM/DM, L1/L2, bornes, seeds et 480 cas; supprimer l'ancienne étude « gain de SF6 ».
9. Remplacer les fractions, intervalles et concentrations de Holten ainsi que Figure 3; préciser que 3H, 85Kr et 39Ar seuls entrent dans la calibration et que l'hélium reste diagnostique.

## 12. Exclusion de périmètre

Aucun calcul, résultat ou golden Ploemeur n'appartient à ce run. Une campagne
Ploemeur distincte détectée sur la machine n'a été ni pilotée ni modifiée ici.
"""
    path = run / "article_non_ploemeur_final_run.md"
    path.write_text(report, encoding="utf-8", newline="\n")
    _inventory(run)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-directory", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    print(build(args.run_directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
