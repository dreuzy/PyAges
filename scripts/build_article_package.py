"""Build a self-contained, publication-facing package of final article results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results" / "article_package"
SOURCE_MANIFESTS = {
    "shifted_exponential": ROOT
    / "results/final_article_simulations/shifted_exponential/manifest.json",
    "holten_h4": ROOT
    / "results/final_article_simulations/holten_h4_final/manifest.json",
    "ploemeur_shifted_exponential": ROOT
    / "results/final_article_simulations/ploemeur_shifted_exponential_final/manifest.json",
}


@dataclass(frozen=True)
class Artifact:
    identifier: str
    category: str
    source: Path
    destination: Path
    description: str


def _artifact(
    identifier: str,
    category: str,
    source: str,
    destination: str,
    description: str,
) -> Artifact:
    return Artifact(
        identifier,
        category,
        ROOT / source,
        Path(destination),
        description,
    )


ARTIFACTS = (
    _artifact(
        "figure1_svg",
        "figure",
        "docs/figures/figure1_overview.svg",
        "figures/figure1_overview.svg",
        "Figure 1, conceptual workflow",
    ),
    _artifact(
        "table3_cases",
        "table",
        "validation/tracerlpm/benchmark/generated/robustness-study/results.csv",
        "tables/table3_pyage_tracerlpm_cases.csv",
        "Table 3 and Supplement S2 paired PyAge-TracerLPM cases",
    ),
    _artifact(
        "table3_summary",
        "table",
        "validation/tracerlpm/benchmark/generated/robustness-study/summary.json",
        "tables/table3_pyage_tracerlpm_summary.json",
        "Table 3 and Supplement S2 machine-readable summary",
    ),
    _artifact(
        "tracerlpm_report",
        "report",
        "validation/tracerlpm/benchmark/generated/robustness-study/summary.md",
        "reports/00_pyage_tracerlpm.md",
        "Paired PyAge-TracerLPM robustness report",
    ),
    _artifact(
        "forward_results",
        "supporting_data",
        "validation/tracerlpm/benchmark/generated/pyage_comparison/case_results.csv",
        "supporting_data/supplement_s1_forward_results.csv",
        "Supplement S1 independent-forward comparison cases",
    ),
    _artifact(
        "forward_summary",
        "diagnostic",
        "validation/tracerlpm/benchmark/generated/pyage_comparison/summary.json",
        "diagnostics/supplement_s1_forward_summary.json",
        "Supplement S1 independent-forward summary",
    ),
    _artifact(
        "figure2_png",
        "figure",
        "results/final_article_simulations/shifted_exponential/figure2_shifted_exponential_final.png",
        "figures/figure2_shifted_exponential.png",
        "Figure 2, raster preview",
    ),
    _artifact(
        "figure2_pdf",
        "figure",
        "results/final_article_simulations/shifted_exponential/figure2_shifted_exponential_final.pdf",
        "figures/figure2_shifted_exponential.pdf",
        "Figure 2, vector insertion file",
    ),
    _artifact(
        "figure2_tiff",
        "figure",
        "results/final_article_simulations/shifted_exponential/figure2_shifted_exponential_final.tiff",
        "figures/figure2_shifted_exponential.tiff",
        "Figure 2, journal raster file",
    ),
    _artifact(
        "figure3_png",
        "figure",
        "results/final_article_simulations/holten_h4_final/figure3_holten_h4_final.png",
        "figures/figure3_holten_h4.png",
        "Figure 3, raster preview",
    ),
    _artifact(
        "figure3_pdf",
        "figure",
        "results/final_article_simulations/holten_h4_final/figure3_holten_h4_final.pdf",
        "figures/figure3_holten_h4.pdf",
        "Figure 3, vector insertion file",
    ),
    _artifact(
        "figure4_png",
        "figure",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/figure4_ploemeur_shiftedexp_final.png",
        "figures/figure4_ploemeur_shifted_exponential.png",
        "Figure 4, raster preview",
    ),
    _artifact(
        "figure4_pdf",
        "figure",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/figure4_ploemeur_shiftedexp_final.pdf",
        "figures/figure4_ploemeur_shifted_exponential.pdf",
        "Figure 4, vector insertion file",
    ),
    _artifact(
        "table4_csv",
        "table",
        "results/final_article_simulations/shifted_exponential/table4_final.csv",
        "tables/table4.csv",
        "Table 4, machine-readable",
    ),
    _artifact(
        "table4_markdown",
        "table",
        "results/final_article_simulations/shifted_exponential/table4_final.md",
        "tables/table4.md",
        "Table 4, formatted",
    ),
    _artifact(
        "shifted_posterior_summary",
        "table",
        "results/final_article_simulations/shifted_exponential/posterior_summaries.csv",
        "tables/shifted_exponential_posterior_summaries.csv",
        "Shifted-exponential posterior summaries",
    ),
    _artifact(
        "holten_posterior_summary",
        "table",
        "results/final_article_simulations/holten_h4_final/posterior_summaries.csv",
        "tables/holten_h4_posterior_summaries.csv",
        "Holten H4 posterior summaries",
    ),
    _artifact(
        "holten_comparison",
        "table",
        "results/final_article_simulations/holten_h4_final/visser_vs_pyage_h4.csv",
        "tables/holten_visser_vs_pyage.csv",
        "Holten fraction comparison",
    ),
    _artifact(
        "ploemeur_shifted_summary",
        "table",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/ploemeur_shiftedexp_final_summary.csv",
        "tables/ploemeur_shifted_exponential_summary.csv",
        "Ploemeur shifted-exponential summary",
    ),
    _artifact(
        "ploemeur_ig_summary",
        "table",
        "results/ploemeur_targeted_ig_reproduction/ploemeur_ig_stabilized_results.csv",
        "tables/ploemeur_ig_stabilized.csv",
        "Ploemeur stabilized physical-IG summary",
    ),
    _artifact(
        "shifted_report",
        "report",
        "results/final_article_simulations/shifted_exponential/shifted_exponential_final.md",
        "reports/01_shifted_exponential.md",
        "Shifted-exponential article results",
    ),
    _artifact(
        "holten_report",
        "report",
        "results/final_article_simulations/holten_h4_final/holten_h4_final_multichain.md",
        "reports/02_holten_h4.md",
        "Holten H4 article results",
    ),
    _artifact(
        "ploemeur_shifted_report",
        "report",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/PLOEMEUR_SHIFTED_EXPONENTIAL_FINAL.md",
        "reports/03_ploemeur_shifted_exponential.md",
        "Ploemeur shifted-exponential results",
    ),
    _artifact(
        "ploemeur_ig_report",
        "report",
        "results/ploemeur_targeted_ig_reproduction/PLOEMEUR_IG_STABILIZED.md",
        "reports/04_ploemeur_ig_stabilized.md",
        "Ploemeur stabilized physical-IG campaign",
    ),
    _artifact(
        "shifted_convergence",
        "diagnostic",
        "results/final_article_simulations/shifted_exponential/convergence_diagnostics.csv",
        "diagnostics/shifted_exponential_convergence.csv",
        "Figure 2 and Table 4 convergence",
    ),
    _artifact(
        "holten_convergence",
        "diagnostic",
        "results/final_article_simulations/holten_h4_final/convergence_diagnostics.csv",
        "diagnostics/holten_h4_convergence.csv",
        "Figure 3 convergence",
    ),
    _artifact(
        "ploemeur_shifted_convergence",
        "diagnostic",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/convergence_diagnostics.csv",
        "diagnostics/ploemeur_shifted_exponential_convergence.csv",
        "Figure 4 convergence",
    ),
    _artifact(
        "ploemeur_tracer_fit",
        "diagnostic",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/tracer_fit_diagnostics.csv",
        "diagnostics/ploemeur_tracer_fit.csv",
        "Ploemeur tracer-wise residuals",
    ),
    _artifact(
        "ploemeur_pairing",
        "diagnostic",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/pairing_correction_effect.csv",
        "diagnostics/ploemeur_pairing_effect.csv",
        "Posterior row-pairing sensitivity",
    ),
    _artifact(
        "ploemeur_ig_gate",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/full_series_gate.json",
        "diagnostics/ploemeur_ig_full_series_gate.json",
        "Physical-IG full-series quality gate",
    ),
    _artifact(
        "ploemeur_ig_equivalence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/distribution_equivalence_checks.csv",
        "diagnostics/ploemeur_ig_distribution_equivalence.csv",
        "Physical/legacy IG equivalence",
    ),
    _artifact(
        "ig_f09_full_convergence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/full_series/F09/convergence_diagnostics.csv",
        "diagnostics/ig_f09_full_convergence.csv",
        "F09 full-series convergence",
    ),
    _artifact(
        "ig_f11_full_convergence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/full_series/F11/convergence_diagnostics.csv",
        "diagnostics/ig_f11_full_convergence.csv",
        "F11 full-series convergence",
    ),
    _artifact(
        "ig_f09_span_convergence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/span_2012_2024_conditioned_on_full/F09/convergence_diagnostics.csv",
        "diagnostics/ig_f09_span_convergence.csv",
        "F09 conditioned-span convergence",
    ),
    _artifact(
        "ig_f11_span_convergence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/span_2012_2024_conditioned_on_full/F11/convergence_diagnostics.csv",
        "diagnostics/ig_f11_span_convergence.csv",
        "F11 conditioned-span convergence",
    ),
    _artifact(
        "ig_f09_window_convergence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/window_2014_2015_conditioned/F09/convergence_diagnostics.csv",
        "diagnostics/ig_f09_window_convergence.csv",
        "F09 conditioned-window convergence",
    ),
    _artifact(
        "ig_f11_window_convergence",
        "diagnostic",
        "results/ploemeur_targeted_ig_reproduction/window_2014_2015_conditioned/F11/convergence_diagnostics.csv",
        "diagnostics/ig_f11_window_convergence.csv",
        "F11 conditioned-window convergence",
    ),
    _artifact(
        "figure2_grid",
        "supporting_data",
        "results/final_article_simulations/shifted_exponential/figure2_objective_grid_sqrt_J_data_over_4.csv",
        "supporting_data/figure2_objective_grid.csv",
        "Figure 2 objective surface",
    ),
    _artifact(
        "figure2_samples",
        "supporting_data",
        "results/final_article_simulations/shifted_exponential/figure2_final_chain_samples.csv",
        "supporting_data/figure2_chain_samples.csv",
        "Figure 2 plotted posterior sample",
    ),
    _artifact(
        "figure4_intervals",
        "supporting_data",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/figure4_prediction_intervals.csv",
        "supporting_data/figure4_prediction_intervals.csv",
        "Figure 4 posterior intervals",
    ),
    _artifact(
        "figure4_predictions",
        "supporting_data",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/figure4_rowwise_posterior_predictions.csv.gz",
        "supporting_data/figure4_rowwise_predictions.csv.gz",
        "Figure 4 row-wise predictions",
    ),
    _artifact(
        "shifted_manifest",
        "provenance",
        "results/final_article_simulations/shifted_exponential/manifest.json",
        "provenance/source_manifests/shifted_exponential.json",
        "Source manifest for Table 4 and Figure 2",
    ),
    _artifact(
        "holten_manifest",
        "provenance",
        "results/final_article_simulations/holten_h4_final/manifest.json",
        "provenance/source_manifests/holten_h4.json",
        "Source manifest for Figure 3",
    ),
    _artifact(
        "ploemeur_manifest",
        "provenance",
        "results/final_article_simulations/ploemeur_shifted_exponential_final/manifest.json",
        "provenance/source_manifests/ploemeur_shifted_exponential.json",
        "Source manifest for Figure 4",
    ),
    _artifact(
        "runner_shifted",
        "code",
        "scripts/run_final_shifted_exponential.py",
        "provenance/code/run_final_shifted_exponential.py",
        "Table 4 and Figure 2 runner",
    ),
    _artifact(
        "runner_holten",
        "code",
        "scripts/run_final_holten_h4.py",
        "provenance/code/run_final_holten_h4.py",
        "Figure 3 runner",
    ),
    _artifact(
        "runner_ploemeur_shifted",
        "code",
        "scripts/run_ploemeur_shifted_exponential_final.py",
        "provenance/code/run_ploemeur_shifted_exponential_final.py",
        "Figure 4 runner",
    ),
    _artifact(
        "runner_ploemeur_ig",
        "code",
        "scripts/run_ploemeur_targeted_ig_reproduction.py",
        "provenance/code/run_ploemeur_targeted_ig_reproduction.py",
        "Physical-IG reproduction runner",
    ),
    _artifact(
        "mcmc_diagnostics",
        "code",
        "scripts/common/mcmc_diagnostics.py",
        "provenance/code/common/mcmc_diagnostics.py",
        "Shared split-Rhat and ESS implementation",
    ),
    _artifact(
        "reporting_helpers",
        "code",
        "scripts/common/reporting.py",
        "provenance/code/common/reporting.py",
        "Dependency-light Markdown reporting",
    ),
    _artifact(
        "package_builder",
        "code",
        "scripts/build_article_package.py",
        "provenance/code/build_article_package.py",
        "This package builder",
    ),
    _artifact(
        "pyproject",
        "environment",
        "pyproject.toml",
        "provenance/environment/pyproject.toml",
        "Project metadata and dependencies",
    ),
    _artifact(
        "constraints",
        "environment",
        "install/constraints.txt",
        "provenance/environment/constraints.txt",
        "Pinned compatibility constraints",
    ),
)


def artifacts_for_campaign(campaign_root: Path) -> tuple[Artifact, ...]:
    """Rebase generated artifacts from ``results/`` to a fresh campaign."""
    campaign_root = campaign_root.resolve()
    prefixes = {
        ROOT / "results/final_article_simulations/shifted_exponential": campaign_root
        / "shifted_exponential",
        ROOT / "results/final_article_simulations/holten_h4_final": campaign_root
        / "holten_h4",
        ROOT
        / "results/final_article_simulations/ploemeur_shifted_exponential_final": campaign_root
        / "ploemeur_shifted_exponential",
        ROOT / "results/ploemeur_targeted_ig_reproduction": campaign_root
        / "ploemeur_physical_ig",
        ROOT / "validation/tracerlpm/benchmark/generated/robustness-study": campaign_root
        / "tracerlpm/benchmark/generated/robustness-study",
        ROOT / "validation/tracerlpm/benchmark/generated/pyage_comparison": campaign_root
        / "forward",
    }
    rebased = []
    for artifact in ARTIFACTS:
        source = artifact.source
        for source_root, current_root in prefixes.items():
            try:
                source = current_root / source.relative_to(source_root)
                break
            except ValueError:
                continue
        rebased.append(
            Artifact(
                artifact.identifier,
                artifact.category,
                source,
                artifact.destination,
                artifact.description,
            )
        )
    return tuple(rebased)


def source_manifests_for_campaign(campaign_root: Path) -> dict[str, Path]:
    campaign_root = campaign_root.resolve()
    return {
        "shifted_exponential": campaign_root / "shifted_exponential/manifest.json",
        "holten_h4": campaign_root / "holten_h4/manifest.json",
        "ploemeur_shifted_exponential": campaign_root
        / "ploemeur_shifted_exponential/manifest.json",
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _source_label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _execution_source_snapshots(
    staging: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    entries = []
    audit = {}
    for run_name, manifest_path in SOURCE_MANIFESTS.items():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        git_head = manifest["git_head"]
        run_audit = {
            "manifest": _source_label(manifest_path),
            "total": 0,
            "working_tree_matches": 0,
            "recovered_from_git_head": 0,
        }
        for raw_relative, expected in manifest.get("source_sha256", {}).items():
            relative = Path(raw_relative)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe source path in manifest: {raw_relative}")
            current = ROOT / relative
            data = current.read_bytes() if current.is_file() else None
            origin = "working_tree"
            if data is None or hashlib.sha256(data).hexdigest() != expected:
                revision_path = relative.as_posix()
                process = subprocess.run(
                    ["git", "show", f"{git_head}:{revision_path}"],
                    cwd=ROOT,
                    capture_output=True,
                    check=True,
                )
                data = process.stdout
                origin = f"git:{git_head}"
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                raise RuntimeError(
                    f"Cannot recover execution source {run_name}:{raw_relative}"
                )
            packaged = Path("provenance") / "execution_source" / run_name / relative
            destination = staging / packaged
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            run_audit["total"] += 1
            if origin == "working_tree":
                run_audit["working_tree_matches"] += 1
            else:
                run_audit["recovered_from_git_head"] += 1
            entries.append(
                {
                    "identifier": f"execution_source:{run_name}:{relative.as_posix()}",
                    "category": "execution_source",
                    "source": origin,
                    "destination": packaged.as_posix(),
                    "packaged_path": packaged.as_posix(),
                    "description": f"Exact execution source for {run_name}",
                    "bytes": len(data),
                    "sha256": actual,
                }
            )
        audit[run_name] = run_audit
    return entries, audit


def _standard_diagnostic(path: Path, group: str, ess_column: str) -> dict[str, object]:
    frame = pd.read_csv(path)
    return {
        "groups": int(frame[group].nunique()),
        "max_split_rhat": float(frame["split_rhat"].max()),
        "min_ess": float(frame[ess_column].min()),
        "all_converged": bool(
            frame["converged"].astype(str).str.lower().eq("true").all()
        ),
    }


def _artifact_source(identifier: str) -> Path:
    for artifact in ARTIFACTS:
        if artifact.identifier == identifier:
            return artifact.source
    raise KeyError(f"Unknown article artifact: {identifier}")


def scientific_summary() -> dict[str, object]:
    ig_rows = []
    for artifact in ARTIFACTS:
        if artifact.identifier.startswith("ig_") and artifact.identifier.endswith(
            "convergence"
        ):
            frame = pd.read_csv(artifact.source)
            ig_rows.append(frame)
    ig = pd.concat(ig_rows, ignore_index=True)
    tracerlpm = pd.read_csv(_artifact_source("table3_cases"))
    forward = json.loads(_artifact_source("forward_summary").read_text(encoding="utf-8"))
    return {
        "thresholds": {"split_rhat_lt": 1.01, "ess_gte": 300.0},
        "pyage_tracerlpm": {
            "paired_cases": int(len(tracerlpm)),
            "pyage_successful": int(
                tracerlpm["pyage_success"].astype(str).str.lower().eq("true").sum()
            ),
            "tracerlpm_successful": int(
                tracerlpm["tracerlpm_success"]
                .astype(str)
                .str.lower()
                .eq("true")
                .sum()
            ),
        },
        "forward_verification": {
            "case_count": int(forward["case_count"]),
            "status": forward["status"],
        },
        "shifted_exponential": _standard_diagnostic(
            _artifact_source("shifted_convergence"),
            "case",
            "ess_sum_chains",
        ),
        "holten_h4": _standard_diagnostic(
            _artifact_source("holten_convergence"),
            "well",
            "ess_sum_chains",
        ),
        "ploemeur_shifted_exponential": _standard_diagnostic(
            _artifact_source("ploemeur_shifted_convergence"),
            "case",
            "ESS",
        ),
        "ploemeur_physical_ig": {
            "posterior_sets": len(ig_rows),
            "max_split_rhat": float(ig["split_rhat"].max()),
            "min_bulk_ess": float(ig["bulk_ess"].min()),
            "min_tail_ess": float(ig["tail_ess"].min()),
            "all_converged": bool(
                (ig["split_rhat"] < 1.01).all()
                and (ig["bulk_ess"] >= 300.0).all()
                and (ig["tail_ess"] >= 300.0).all()
            ),
            "stabilized_campaign_converged": bool(
                (ig["split_rhat"] < 1.01).all()
                and (ig["bulk_ess"] >= 300.0).all()
                and (ig["tail_ess"] >= 300.0).all()
            ),
        },
    }


def _readme(summary: dict[str, object]) -> str:
    shifted = summary["shifted_exponential"]
    tracerlpm = summary["pyage_tracerlpm"]
    forward = summary["forward_verification"]
    holten = summary["holten_h4"]
    ploemeur = summary["ploemeur_shifted_exponential"]
    ig = summary["ploemeur_physical_ig"]
    ig_campaign_converged = ig["stabilized_campaign_converged"]
    return f"""# PyAge — paquet de résultats pour l'article

Ce dossier est le point d'entrée unique pour les résultats finaux de l'article.
Il contient les fichiers prêts à insérer, les tableaux sources, les diagnostics
qui soutiennent les affirmations et la provenance exacte de chaque fichier.

## Carte d'insertion

| Élément | Fichier principal | Source quantitative |
| --- | --- | --- |
| Figure 1 | `figures/figure1_overview.svg` | conceptual workflow, no simulation |
| Table 3 | `tables/table3_pyage_tracerlpm_cases.csv` | `tables/table3_pyage_tracerlpm_summary.json` |
| Table 4 | `tables/table4.md` | `tables/table4.csv` |
| Figure 2 | `figures/figure2_shifted_exponential.pdf` | `supporting_data/figure2_objective_grid.csv` |
| Figure 3 | `figures/figure3_holten_h4.pdf` | `tables/holten_visser_vs_pyage.csv` |
| Figure 4 | `figures/figure4_ploemeur_shifted_exponential.pdf` | `supporting_data/figure4_prediction_intervals.csv` |

La Figure 1 est conceptuelle et ne dépend pas des simulations finales; son SVG
versionné est néanmoins inclus pour que le jeu des figures soit complet.

## Statut scientifique encapsulé

- Forward indépendant : {forward["case_count"]} cas, statut `{forward["status"]}`.
- PyAge–TracerLPM : {tracerlpm["paired_cases"]} cas appariés,
  {tracerlpm["pyage_successful"]} succès PyAge et
  {tracerlpm["tracerlpm_successful"]} succès TracerLPM.
- Shifted exponential : {shifted["groups"]}/19 cas, split-Rhat maximal
  `{shifted["max_split_rhat"]:.5f}`, ESS minimal `{shifted["min_ess"]:.1f}`.
- Holten H4 : {holten["groups"]}/7 puits, split-Rhat maximal
  `{holten["max_split_rhat"]:.5f}`, ESS minimal `{holten["min_ess"]:.1f}`.
- Ploemeur shifted exponential : {ploemeur["groups"]}/4 calibrations,
  split-Rhat maximal `{ploemeur["max_split_rhat"]:.5f}`, ESS minimal
  `{ploemeur["min_ess"]:.1f}`.
- Ploemeur IG physique : {ig["posterior_sets"]}/6 ensembles, split-Rhat maximal
  `{ig["max_split_rhat"]:.5f}`, ESS bulk/tail minimaux
  `{ig["min_bulk_ess"]:.1f}/{ig["min_tail_ess"]:.1f}`; campagne stabilisée
  convergée : `{ig_campaign_converged}`.

## Organisation

- `figures/` : formats d'insertion et aperçus ;
- `tables/` : valeurs finales citées dans le texte ;
- `reports/` : interprétation scientifique détaillée ;
- `diagnostics/` : convergence, résidus, pairing et équivalence IG ;
- `supporting_data/` : données effectivement tracées dans les figures ;
- `provenance/` : manifests sources, code de génération et environnement.

Les chaînes MCMC brutes ne sont pas dupliquées dans ce paquet éditorial. Elles
restent dans les dossiers de la campagne et sont incluses dans l'archive GMD
complète construite par `scripts.build_reproduction_archive`. Les résumés,
diagnostics et données tracées nécessaires à l'audit sont inclus ici.

Les sources exactes enregistrées par chaque manifest d'exécution sont copiées
dans `provenance/execution_source/`. Si le fichier de travail a évolué après un
calcul, sa version exacte est récupérée depuis le commit consigné puis vérifiée
contre le SHA-256 historique; aucune provenance n'est réécrite rétroactivement.

## Vérification

`provenance/article_package_manifest.json` décrit chaque artefact et son SHA-256.
`CHECKSUMS.sha256` permet une vérification indépendante. Pour contrôler ce
paquet depuis la racine du dépôt :

```powershell
python -m scripts.build_article_package --validate-only results/article_package
```
"""


def _validated_artifacts(artifacts: Iterable[Artifact]) -> tuple[Artifact, ...]:
    result = tuple(artifacts)
    identifiers = [item.identifier for item in result]
    destinations = [item.destination.as_posix() for item in result]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Artifact identifiers must be unique")
    if len(destinations) != len(set(destinations)):
        raise ValueError("Artifact destinations must be unique")
    for artifact in result:
        if not artifact.source.is_file():
            raise FileNotFoundError(artifact.source)
        if artifact.destination.is_absolute() or ".." in artifact.destination.parts:
            raise ValueError(f"Unsafe package destination: {artifact.destination}")
    return result


def validate_package(output: Path) -> dict[str, object]:
    output = output.resolve()
    manifest_path = output / "provenance" / "article_package_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    for artifact in payload["artifacts"]:
        path = output / artifact["packaged_path"]
        if not path.is_file():
            failures.append(f"missing: {artifact['packaged_path']}")
        elif sha256(path) != artifact["sha256"]:
            failures.append(f"hash: {artifact['packaged_path']}")
        elif path.stat().st_size != artifact["bytes"]:
            failures.append(f"size: {artifact['packaged_path']}")
    if failures:
        raise RuntimeError("Invalid article package: " + ", ".join(failures))
    return payload


def build_package(
    output: Path = DEFAULT_OUTPUT,
    artifacts: Iterable[Artifact] = ARTIFACTS,
) -> Path:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing package: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    inventory = _validated_artifacts(artifacts)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        entries = []
        for artifact in inventory:
            destination = staging / artifact.destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact.source, destination)
            entries.append(
                {
                    **asdict(artifact),
                    "source": _source_label(artifact.source),
                    "destination": artifact.destination.as_posix(),
                    "packaged_path": artifact.destination.as_posix(),
                    "bytes": destination.stat().st_size,
                    "sha256": sha256(destination),
                }
            )
        execution_entries, source_audit = _execution_source_snapshots(staging)
        entries.extend(execution_entries)
        summary = scientific_summary()
        readme = staging / "README.md"
        readme.write_text(_readme(summary), encoding="utf-8", newline="\n")
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
            "git_head": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--short")),
            "scope": "Publication-facing Table 4 and Figures 2–4 with audit support",
            "raw_mcmc_chains_included": False,
            "scientific_summary": summary,
            "execution_source_audit": source_audit,
            "artifacts": entries,
        }
        manifest_path = staging / "provenance" / "article_package_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        checksum_paths = [readme, manifest_path]
        checksum_paths.extend(staging / item["packaged_path"] for item in entries)
        checksums = "\n".join(
            f"{sha256(path)}  {path.relative_to(staging).as_posix()}"
            for path in sorted(checksum_paths)
        )
        (staging / "CHECKSUMS.sha256").write_text(
            checksums + "\n", encoding="ascii", newline="\n"
        )
        validate_package(staging)
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output


def replace_package(
    output: Path = DEFAULT_OUTPUT,
    artifacts: Iterable[Artifact] = ARTIFACTS,
) -> Path:
    """Transactionally replace a package that already passes validation."""
    output = output.resolve()
    validate_package(output)
    backup = output.with_name(f".{output.name}.backup-{os.getpid()}")
    if backup.exists():
        raise FileExistsError(f"Refusing to replace existing backup: {backup}")
    output.rename(backup)
    try:
        rebuilt = build_package(output, artifacts)
    except Exception:
        if output.exists():
            shutil.rmtree(output, ignore_errors=True)
        backup.rename(output)
        raise
    shutil.rmtree(backup)
    return rebuilt


def main() -> int:
    global ARTIFACTS, SOURCE_MANIFESTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--campaign-root",
        type=Path,
        help="fresh campaign root containing all newly generated results",
    )
    parser.add_argument("--validate-only", type=Path)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument(
        "--reuse-valid",
        action="store_true",
        help="accept an existing package only after full hash validation",
    )
    args = parser.parse_args()
    if args.campaign_root is not None:
        ARTIFACTS = artifacts_for_campaign(args.campaign_root)
        SOURCE_MANIFESTS = source_manifests_for_campaign(args.campaign_root)
    if args.validate_only is not None:
        payload = validate_package(args.validate_only)
        print(f"Validated {len(payload['artifacts'])} packaged artifacts")
        return 0
    if args.reuse_valid and args.output.exists():
        payload = validate_package(args.output)
        print(f"Reused valid package with {len(payload['artifacts'])} artifacts")
        return 0
    output = (
        replace_package(args.output) if args.replace else build_package(args.output)
    )
    payload = validate_package(output)
    print(f"Built {output} with {len(payload['artifacts'])} verified artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
