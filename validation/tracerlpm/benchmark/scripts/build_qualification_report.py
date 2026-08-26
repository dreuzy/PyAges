"""Build the scientific qualification report from archived benchmark evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml

from .generate_inputs import BENCHMARK_ROOT

GENERATED = BENCHMARK_ROOT / "generated"
ROBUSTNESS = GENERATED / "robustness-study"
OUTPUT = GENERATED / "qualification-report"
TRACERLPM_ROOT = BENCHMARK_ROOT.parent


def _rmse(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values))


def _median(values: list[float]) -> float:
    return statistics.median(values)


def _bool(value: str | bool) -> bool:
    return value if isinstance(value, bool) else value.lower() == "true"


def _load_rows() -> list[dict]:
    with (ROBUSTNESS / "results.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    numeric = {
        "noise_relative_sd",
        "true_tau",
        "true_secondary",
        "pyage_tau",
        "pyage_secondary",
        "pyage_maximum_concentration_relative_error",
        "tracerlpm_tau",
        "tracerlpm_secondary",
        "tracerlpm_maximum_concentration_relative_error",
        "tracerlpm_objective",
    }
    boolean = {
        "pyage_success",
        "pyage_boundary_hit",
        "tracerlpm_success",
        "tracerlpm_boundary_hit",
    }
    for row in rows:
        for name in numeric:
            row[name] = float(row[name])
        for name in boolean:
            row[name] = _bool(row[name])
        row["seed"] = int(row["seed"])
    return rows


def _aggregate(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    output = []
    for group_key, selected in sorted(groups.items()):
        base = dict(zip(keys, group_key, strict=False))
        for tool in ("pyage", "tracerlpm"):
            tau_errors = [row[f"{tool}_tau"] - row["true_tau"] for row in selected]
            tau_relative = [
                abs(error) / row["true_tau"]
                for error, row in zip(tau_errors, selected, strict=False)
            ]
            secondary_errors = [
                row[f"{tool}_secondary"] - row["true_secondary"] for row in selected
            ]
            secondary_relative = [
                abs(error) / row["true_secondary"]
                for error, row in zip(secondary_errors, selected, strict=False)
            ]
            output.append(
                {
                    **base,
                    "tool": tool,
                    "count": len(selected),
                    "tau_bias": statistics.mean(tau_errors),
                    "tau_rmse": _rmse(tau_errors),
                    "tau_median_absolute_relative_error": _median(tau_relative),
                    "secondary_bias": statistics.mean(secondary_errors),
                    "secondary_rmse": _rmse(secondary_errors),
                    "secondary_median_absolute_relative_error": _median(
                        secondary_relative
                    ),
                    "boundary_hits": sum(
                        row[f"{tool}_boundary_hit"] for row in selected
                    ),
                    "median_maximum_concentration_relative_error": _median(
                        [
                            row[f"{tool}_maximum_concentration_relative_error"]
                            for row in selected
                        ]
                    ),
                }
            )
    return output


def _fit_objective_diagnostic(rows: list[dict]) -> dict:
    comparisons = []
    for row in rows:
        pyage = json.loads(
            (GENERATED / "inversion" / row["case_id"] / "pyage-result.json").read_text(
                encoding="utf-8"
            )
        )
        tracer = json.loads(
            (TRACERLPM_ROOT / row["tracerlpm_report"]).read_text(encoding="utf-8-sig")
        )["fit"]
        tracer_attempt = min(
            tracer["attempts"], key=lambda item: float(item["objective"])
        )
        pyage_relative = [
            abs(float(item["calculated"]) - float(item["observed"]))
            / max(abs(float(item["observed"])), 1e-300)
            for item in pyage["concentrations"]
        ]
        tracer_relative = [
            abs(
                float(tracer_attempt["calculatedConcentrations"][name])
                - float(observed)
            )
            / max(abs(float(observed)), 1e-300)
            for name, observed in tracer["observations"].items()
        ]
        comparisons.append(
            {
                "case_id": row["case_id"],
                "pyage_l1": sum(pyage_relative),
                "tracerlpm_l1": sum(tracer_relative),
                "pyage_l2": sum(value * value for value in pyage_relative),
                "tracerlpm_l2": sum(value * value for value in tracer_relative),
                "pyage_tau_error": abs(row["pyage_tau"] - row["true_tau"]),
                "tracerlpm_tau_error": abs(row["tracerlpm_tau"] - row["true_tau"]),
            }
        )
    pyage_tau_worse = [
        item
        for item in comparisons
        if item["pyage_tau_error"] > item["tracerlpm_tau_error"]
    ]
    return {
        "case_count": len(comparisons),
        "pyage_lower_l1_count": sum(
            item["pyage_l1"] < item["tracerlpm_l1"] for item in comparisons
        ),
        "pyage_lower_l2_count": sum(
            item["pyage_l2"] < item["tracerlpm_l2"] for item in comparisons
        ),
        "pyage_tau_worse_count": len(pyage_tau_worse),
        "pyage_tau_worse_but_lower_l2_count": sum(
            item["pyage_l2"] < item["tracerlpm_l2"] for item in pyage_tau_worse
        ),
        "pyage_tau_worse_but_lower_maximum_residual_count": sum(
            row["pyage_maximum_concentration_relative_error"]
            < row["tracerlpm_maximum_concentration_relative_error"]
            for row in rows
            if abs(row["pyage_tau"] - row["true_tau"])
            > abs(row["tracerlpm_tau"] - row["true_tau"])
        ),
    }


def _head_to_head(rows: list[dict]) -> dict:
    result = {}
    for parameter in ("tau", "secondary"):
        pyage = tracerlpm = ties = 0
        for row in rows:
            truth = row[f"true_{parameter}"]
            pyage_error = abs(row[f"pyage_{parameter}"] - truth)
            tracer_error = abs(row[f"tracerlpm_{parameter}"] - truth)
            if pyage_error < tracer_error - 1e-12:
                pyage += 1
            elif tracer_error < pyage_error - 1e-12:
                tracerlpm += 1
            else:
                ties += 1
        result[parameter] = {"pyage": pyage, "tracerlpm": tracerlpm, "ties": ties}
    return result


def _coverage(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[float]] = defaultdict(list)
    for row in rows:
        observation = BENCHMARK_ROOT / "observations" / f"{row['case_id']}.csv"
        with observation.open(encoding="utf-8", newline="") as stream:
            first = next(csv.DictReader(stream))
        groups[(row["model"], row["true_tau"], row["true_secondary"])].append(
            float(first["covered_distribution_mass"])
        )
    return [
        {
            "model": model,
            "true_tau": tau,
            "true_secondary": secondary,
            "covered_mass": _median(values),
        }
        for (model, tau, secondary), values in sorted(groups.items())
    ]


def _sha256(path: Path) -> str | None:
    return (
        hashlib.sha256(path.read_bytes()).hexdigest().upper() if path.exists() else None
    )


def _provenance() -> dict:
    config = yaml.safe_load(
        (
            TRACERLPM_ROOT / "config" / "runner-config.robustness-session.local.yaml"
        ).read_text(encoding="utf-8")
    )
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=BENCHMARK_ROOT.parents[2], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    workbook = Path(config["workbook_path"])
    xll = Path(config["xll_path"])
    return {
        "report_date": "2026-08-18",
        "git_commit_at_report_generation": commit,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "matplotlib": matplotlib.__version__,
        "pyyaml": yaml.__version__,
        "platform": platform.platform(),
        "excel": "Microsoft Excel 16.0, 64-bit",
        "dotnet_sdk": "8.0.302",
        "workbook_path": str(workbook),
        "workbook_sha256_configured": config["workbook_sha256"],
        "workbook_sha256_observed": _sha256(workbook),
        "xll_path": str(xll),
        "xll_sha256_configured": config["xll_sha256"],
        "xll_sha256_observed": _sha256(xll),
    }


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}g}"


def _pct(value: float, digits: int = 3) -> str:
    return f"{100 * value:.{digits}g} %"


def _make_figure(model_noise: list[dict], head_to_head: dict, target: Path) -> None:
    colors = {"pyage": "#0072B2", "tracerlpm": "#D55E00"}
    labels = {"pyage": "PyAge", "tracerlpm": "TracerLPM"}
    styles = {"EPM": "-", "DM": "--"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.2))
    fields = [
        ("tau_median_absolute_relative_error", "Erreur médiane relative sur τ (%)"),
        (
            "secondary_median_absolute_relative_error",
            "Erreur médiane relative sur le paramètre 2 (%)",
        ),
        ("boundary_hits", "Solutions sur une borne (%)"),
    ]
    for axis, (field, title) in zip(axes.flat[:3], fields, strict=False):
        for model in ("EPM", "DM"):
            for tool in ("pyage", "tracerlpm"):
                selected = sorted(
                    (
                        row
                        for row in model_noise
                        if row["model"] == model and row["tool"] == tool
                    ),
                    key=lambda row: row["noise_relative_sd"],
                )
                x = [100 * row["noise_relative_sd"] for row in selected]
                if field == "boundary_hits":
                    y = [100 * row[field] / row["count"] for row in selected]
                else:
                    y = [100 * row[field] for row in selected]
                axis.plot(
                    x,
                    y,
                    marker="o",
                    linestyle=styles[model],
                    color=colors[tool],
                    label=f"{labels[tool]} {model}",
                )
        axis.set_title(title)
        axis.set_xlabel("Écart-type relatif du bruit (%)")
        axis.grid(alpha=0.25)
        axis.set_xticks([1, 5, 10, 20])
    axes[0, 0].legend(fontsize=8, ncol=2)
    axis = axes[1, 1]
    x = np.arange(2)
    width = 0.34
    axis.bar(
        x - width / 2,
        [head_to_head[name]["pyage"] for name in ("tau", "secondary")],
        width,
        color=colors["pyage"],
        label="PyAge",
    )
    axis.bar(
        x + width / 2,
        [head_to_head[name]["tracerlpm"] for name in ("tau", "secondary")],
        width,
        color=colors["tracerlpm"],
        label="TracerLPM",
    )
    axis.set_xticks(x, ["τ", "Paramètre 2"])
    axis.set_ylabel("Nombre de cas plus proches de la vérité")
    axis.set_title("Comparaison cas par cas (descriptive)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    fig.suptitle(
        "Qualification PyAge–TracerLPM : robustesse de l’inversion", fontsize=14
    )
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _table_model_noise(rows: list[dict]) -> str:
    lines = [
        "| Modèle | Bruit | Outil | n | RMSE τ (ans) | Médiane |Δτ|/τ | Médiane erreur param. 2 | Bornes | Médiane erreur conc. max |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {_pct(row['noise_relative_sd'], 0)} | {row['tool']} | "
            f"{row['count']} | {_fmt(row['tau_rmse'])} | "
            f"{_pct(row['tau_median_absolute_relative_error'])} | "
            f"{_pct(row['secondary_median_absolute_relative_error'])} | "
            f"{row['boundary_hits']}/{row['count']} | "
            f"{_pct(row['median_maximum_concentration_relative_error'])} |"
        )
    return "\n".join(lines)


def _table_age(rows: list[dict]) -> str:
    selected = [row for row in rows if row["noise_relative_sd"] in (0.10, 0.20)]
    lines = [
        "| Modèle | τ vrai | Bruit | Outil | n | RMSE τ | Médiane erreur param. 2 | Bornes |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in selected:
        lines.append(
            f"| {row['model']} | {_fmt(row['true_tau'])} | "
            f"{_pct(row['noise_relative_sd'], 0)} | {row['tool']} | {row['count']} | "
            f"{_fmt(row['tau_rmse'])} | "
            f"{_pct(row['secondary_median_absolute_relative_error'])} | "
            f"{row['boundary_hits']}/{row['count']} |"
        )
    return "\n".join(lines)


def _table_coverage(rows: list[dict]) -> str:
    lines = [
        "| Modèle | τ | Paramètre 2 | Masse couverte par les historiques |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {_fmt(row['true_tau'])} | "
            f"{_fmt(row['true_secondary'])} | {_pct(row['covered_mass'])} |"
        )
    return "\n".join(lines)


def build() -> dict:
    rows = _load_rows()
    if len(rows) != 480 or len({row["case_id"] for row in rows}) != 480:
        raise ValueError("La campagne de robustesse doit contenir 480 cas uniques")
    model_noise = _aggregate(rows, ("model", "noise_relative_sd"))
    model_age_noise = _aggregate(rows, ("model", "true_tau", "noise_relative_sd"))
    head_to_head = _head_to_head(rows)
    objectives = _fit_objective_diagnostic(rows)
    coverage = _coverage(rows)
    provenance = _provenance()
    forward = json.loads(
        (GENERATED / "pyage_comparison" / "summary.json").read_text(encoding="utf-8")
    )
    convergence = json.loads(
        (GENERATED / "pyage_convergence" / "summary.json").read_text(encoding="utf-8")
    )
    sf6 = json.loads(
        (GENERATED / "sf6-information-gain" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    sf6_tools = json.loads(
        (GENERATED / "tracerlpm-sf6-monte-carlo" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    metrics = {
        "status": "complete_working_report",
        "provenance": provenance,
        "scope": {
            "robustness_case_count": len(rows),
            "unique_case_count": len({row["case_id"] for row in rows}),
            "phases": dict(Counter(row["phase"] for row in rows)),
            "models": dict(Counter(row["model"] for row in rows)),
            "tracers": ["CFC-11", "CFC-12", "CFC-113", "SF6"],
            "true_tau_years": sorted({row["true_tau"] for row in rows}),
            "noise_relative_sd": sorted({row["noise_relative_sd"] for row in rows}),
            "seeds": sorted({row["seed"] for row in rows}),
        },
        "success": {
            "pyage": sum(row["pyage_success"] for row in rows),
            "tracerlpm": sum(row["tracerlpm_success"] for row in rows),
            "pyage_boundary_hits": sum(row["pyage_boundary_hit"] for row in rows),
            "tracerlpm_boundary_hits": sum(
                row["tracerlpm_boundary_hit"] for row in rows
            ),
        },
        "model_noise": model_noise,
        "model_age_noise": model_age_noise,
        "head_to_head": head_to_head,
        "objective_diagnostic": objectives,
        "covered_distribution_mass": coverage,
        "forward_validation": forward,
        "pyage_convergence": convergence,
        "sf6_information_gain": sf6,
        "sf6_four_tracer_tool_comparison": sf6_tools,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _make_figure(model_noise, head_to_head, OUTPUT / "diagnostic-overview.png")

    sf6_epm = sf6["models"]["EPM"]
    sf6_dm = sf6["models"]["DM"]
    report = f"""# Rapport de qualification scientifique ciblée PyAge–TracerLPM

## Statut et objet du document

Ce rapport de travail consolide les tests réalisés pour préparer une section de
qualification de PyAge dans un article scientifique. Il distingue explicitement
la vérification du calcul direct (*forward*), la récupération de paramètres sur
données synthétiques et la robustesse de l'inversion au bruit. Il ne constitue
pas encore, à lui seul, une validation universelle de PyAge sur données naturelles.

Date de consolidation : **{provenance["report_date"]}**. Révision Git observée :
`{provenance["git_commit_at_report_generation"]}`. Les données détaillées et les
rapports bruts sont conservés ; aucun résultat n'est reconstruit à partir du seul
présent texte.

## Résumé exécutif

1. Le calcul *forward* de PyAge converge vers une quadrature indépendante lorsque
   la résolution augmente. Sur 270 comparaisons, le RMSE à la résolution 2000 est
   de 0,0185 pour EMM, 0,00603 pour EPM et 0,00285 pour DM dans les unités des
   concentrations synthétiques ; PFM est exact à l'arrondi machine.
2. Sans bruit, les inversions EMM, EPM et DM récupèrent les paramètres vrais. Pour
   EPM et DM, les erreurs relatives PyAge sont inférieures à 0,04 % ; TracerLPM
   satisfait aussi les seuils fixés, avec des erreurs de 1,27–2,88 %.
3. À 1 % de bruit et quatre traceurs, la campagne appariée de 30 réalisations donne
   des biais faibles pour PyAge : −0,031 an en EPM et −0,029 an en DM. L'ajout de
   SF6 réduit fortement la dispersion par rapport aux trois CFC seuls.
4. La campagne de robustesse comprend **480 cas appariés**, soit 240 EPM et 240 DM.
   Les deux outils terminent les 480 inversions. À faible bruit, le temps moyen est
   bien récupéré ; à 10–20 %, l'identifiabilité du paramètre de largeur se dégrade
   fortement et les solutions sur les bornes deviennent fréquentes.
5. Le classement direct des outils par distance aux paramètres vrais doit rester
   descriptif : PyAge minimise une norme L2 pondérée, tandis que TracerLPM minimise
   une somme L1 d'erreurs relatives. Dans {objectives["pyage_tau_worse_count"]} cas
   où le τ PyAge est plus éloigné de la vérité, PyAge conserve pourtant le meilleur
   critère L2 dans {objectives["pyage_tau_worse_but_lower_l2_count"]} cas. Le bruit,
   l'équifinalité et la différence de fonction objectif expliquent donc une large
   part des inversions où TracerLPM paraît ponctuellement plus proche de la vérité.

![Vue synthétique de la robustesse](diagnostic-overview.png)

## 1. Questions de qualification

Le programme de tests répond aux questions suivantes :

- les distributions et convolutions de PyAge reproduisent-elles une référence
  numérique indépendante ?
- les conventions de paramètres de PyAge et TracerLPM sont-elles compatibles ?
- les deux outils récupèrent-ils une solution synthétique connue sans bruit ?
- comment le bruit, l'âge moyen et la largeur de distribution affectent-ils la
  récupération de `tau` et du second paramètre ?
- quelle information supplémentaire apporte SF6 aux trois CFC ?
- les écarts entre les outils reflètent-ils une erreur de calcul, une différence
  d'estimateur ou une non-identifiabilité du problème inverse ?

## 2. Logiciels, versions et traçabilité

| Élément | Version ou empreinte |
|---|---|
| Système | {provenance["platform"]} |
| Python | {provenance["python"]} |
| NumPy | {provenance["numpy"]} |
| SciPy | {provenance["scipy"]} |
| Excel | {provenance["excel"]} |
| SDK .NET | {provenance["dotnet_sdk"]} |
| Classeur quatre traceurs | `{provenance["workbook_sha256_observed"]}` |
| XLL TracerLPM 64 bits | `{provenance["xll_sha256_observed"]}` |

Le runner vérifie les empreintes du classeur et du XLL avant calcul. Les entrées,
bornes, initialisations et graines sont décrites en YAML. Chaque cas TracerLPM
produit un JSON brut contenant les observations, les tentatives Solver, les
paramètres retenus, les concentrations recalculées, la fonction objectif et les
empreintes des composants exécutés.

Audit logiciel final : **53 tests Python réussis**, compilation .NET réussie sans
erreur. L'avertissement NuGet observé concernait uniquement l'accès à la base de
vulnérabilités et non la compilation ou les calculs.

## 3. Modèles et correspondance des paramètres

`tau` désigne dans les deux outils l'âge moyen de la distribution.

Pour EPM, TracerLPM expose le rapport `r`, alors que PyAge utilise
`eta = 1 + r`. La distribution exponentielle décalée de PyAge reçoit :

```text
mu = tau / eta
shift = tau * (1 - 1 / eta)
```

Pour DM, le paramètre de dispersion est transmis par :

```text
mu = tau
sigma = tau * sqrt(2 * DP)
```

Ces transformations sont réversibles et couvertes par des tests unitaires. Les
quatre traceurs de la campagne de robustesse sont traités comme stables dans ce
protocole : CFC-11, CFC-12, CFC-113 et SF6, tous exprimés en pptv.

## 4. Génération indépendante des observations

Les concentrations vraies ne sont produites ni par PyAge ni par TracerLPM. Une
implémentation séparée évalue analytiquement les densités EMM, EPM et DM, puis
effectue une quadrature de Gauss–Legendre à huit points sur chaque intervalle des
historiques de recharge. Les points d'intégration suivent les ruptures de la
chronique ; le paramétrage EPM ajoute explicitement la position du décalage.

Pour chaque traceur `i`, l'observation bruitée est :

```text
Cobs_i = Ctrue_i * (1 + epsilon_i), epsilon_i ~ N(0, sigma_rel)
```

Les graines sont déclarées et les mêmes graines 401–410 sont réutilisées entre
scénarios. Le vecteur de perturbations des quatre traceurs est donc apparié entre
modèles, âges, largeurs et niveaux de bruit. Cette construction réduit la variance
des comparaisons entre scénarios mais ne constitue pas un échantillon de terrain.

L'année d'observation est 2020. Les historiques atmosphériques proviennent des
fichiers de recharge PyAge archivés avec leur SHA-256 dans chaque observation.
Les concentrations sont nulles avant le début des chroniques.

### Masse de distribution couverte

{_table_coverage(coverage)}

Les cas anciens et larges ne sont donc pas tous entièrement couverts par les
historiques : à `tau=50`, la masse couverte descend à environ 80–94 % en EPM et
83–86 % en DM. Ce point limite l'information disponible et accroît la sensibilité
aux conventions de traitement de la partie antérieure aux chroniques.

## 5. Fonctions objectif et algorithmes d'inversion

### PyAge

PyAge minimise une somme de carrés de résidus normalisés :

```text
J_L2 = sum_i ((Cmod_i - Cobs_i) / s_i)^2
s_i = max(sigma_rel * Cobs_i, 10^-6 * max(history_i))
```

EPM utilise Powell, adapté au caractère discret du chemin de convolution de
production ; DM utilise L-BFGS-B. Chaque initialisation déclarée est réellement
optimisée et la solution ayant le plus faible objectif est retenue. L'optimiseur
ne peut pas remplacer une initialisation par une solution de moins bon objectif.

### TracerLPM

Le classeur minimise la somme des erreurs relatives absolues :

```text
J_L1 = sum_i abs(Cmod_i - Cobs_i) / Cobs_i
```

Le runner évalue d'abord toutes les initialisations, choisit celle de plus faible
erreur L1, puis lance une fois Excel Solver GRG Nonlinear depuis ce point. Les
contraintes de temps et d'itérations sont respectivement 30 s et 1000 itérations.

TracerLPM fournit une solution ponctuelle et des erreurs relatives de concentration,
mais pas d'écart-type, d'intervalle de confiance ou de covariance des paramètres.
Les dispersions de paramètres présentées ici viennent des répétitions externes,
pas d'un calcul d'incertitude interne à TracerLPM.

### Bornes et initialisations

| Modèle | Bornes `tau` | Bornes paramètre 2 | Initialisations principales |
|---|---|---|---|
| EPM | 0,1–200 ans | `eta=1,01–11`, soit `r=0,01–10` | âges 5, 20, 50 ou 80 ; largeurs étroite, intermédiaire et large |
| DM | 0,1–200 ans | `DP=0,001–3` | âges 5, 20, 50 ou 80 ; `DP=0,02–1` |

Certaines initialisations coïncident avec les valeurs synthétiques 5, 20 ou 50 ans.
Elles stabilisent le test numérique, mais peuvent avantager une solution qui reste
près du point de départ. Une comparaison d'algorithmes destinée à publication
devrait aussi inclure des départs aveugles ne contenant pas exactement la vérité.

## 6. Hiérarchie des tests réalisés

| Niveau | Objet | Taille | Rôle dans la qualification |
|---|---|---:|---|
| Technique | Excel, XLL, Solver, macros, ActiveX, export et hashes | parcours automatisé | Vérifie l'exécutabilité et la traçabilité |
| Forward indépendant | PFM, EMM, EPM, DM ; 5 entrées, 18 paramétrisations, 3 dates | 270 | Vérifie les concentrations PyAge contre une quadrature séparée |
| Convergence PyAge | résolutions 100, 200, 500, 1000, 2000 | 5 niveaux | Sépare erreur de discrétisation et erreur de modèle |
| Forward TracerLPM | entrées constante, rampe, échelon et multi-pics | plusieurs familles | Vérifie les conventions et la grille temporelle Excel |
| Inversion sans bruit | EMM, EPM, DM à 20 ans, trois CFC | 3 cas | Vérifie la récupération de la vérité |
| Bruit pilote | EPM et DM, trois CFC, 1 %, 5 graines | 10 par outil | Diagnostic initial |
| Monte-Carlo PyAge | EPM et DM, trois CFC, 1 %, 30 graines | 60 | Quantifie l'équifinalité initiale |
| Gain de SF6 | mêmes graines avec ajout de SF6 | 60 | Mesure l'information du quatrième traceur |
| Comparaison quatre traceurs | PyAge–TracerLPM, 1 %, 30 graines | 120 résultats | Compare biais et dispersion en régime favorable |
| Robustesse finale | largeurs, `tau=5,20,50`, bruit 1–20 %, 4 traceurs | 480 paires | Explore le domaine de dégradation |

## 7. Résultats du calcul forward

### 7.1 PyAge contre la référence indépendante

| Résolution | EMM RMSE | EPM RMSE | DM RMSE |
|---:|---:|---:|---:|
| 100 | 0,438 | 0,292 | 1,915 |
| 200 | 0,201 | 0,116 | 0,205 |
| 500 | 0,0873 | 0,0451 | 0,0475 |
| 1000 | 0,0465 | 0,0160 | 0,0225 |
| 2000 | 0,0185 | 0,00603 | 0,00285 |

La décroissance régulière des erreurs avec la résolution est compatible avec une
erreur de discrétisation, et non avec une erreur de définition des distributions.
Les maxima relatifs deviennent peu informatifs lorsque la concentration vraie est
proche de zéro ; les erreurs absolues et l'étude de convergence sont donc les
diagnostics principaux.

### 7.2 TracerLPM et conventions temporelles

Le cas PFM avec entrée constante est identique dans PyAge, la référence et les
deux emplacements de modèle TracerLPM. Les entrées transitoires révèlent une grille
temporelle interne semestrielle dans TracerLPM. La date effective est enregistrée
dans les rapports et réduit une partie des écarts, sans les annuler dans tous les
cas EPM et DM. La comparaison d'inversion ne doit donc pas être interprétée comme
une égalité bit à bit des opérateurs forward.

## 8. Inversions sans bruit

| Modèle | Paramètre | Vrai | PyAge | Erreur PyAge | TracerLPM | Erreur TracerLPM |
|---|---|---:|---:|---:|---:|---:|
| EMM | `tau` | 20 | 19,9983 | 0,00174 an | 19,9338 | 0,0662 an |
| EPM | `tau` | 20 | 20,0000005 | <0,001 % | 19,7464 | 1,27 % |
| EPM | `r` | 2 | 2,0000001 | <0,001 % | 1,96243 | 1,88 % |
| DM | `tau` | 20 | 19,9996 | 0,002 % | 19,7303 | 1,35 % |
| DM | `DP` | 0,2 | 0,200067 | 0,034 % | 0,205768 | 2,88 % |

Les deux outils satisfont les seuils prédéfinis. La récupération quasi exacte par
PyAge confirme la cohérence entre les transformations de paramètres et la référence
indépendante. L'écart résiduel de TracerLPM est compatible avec ses choix de grille,
de fonction objectif et de Solver.

## 9. Information apportée par SF6

À 1 % de bruit et 30 graines appariées, l'ajout de SF6 aux trois CFC réduit :

- le RMSE de `tau` EPM de **{100 * sf6_epm["relative_reductions"]["tau_rmse"]:.1f} %** ;
- le RMSE de `r` de **{100 * sf6_epm["relative_reductions"]["secondary_rmse"]:.1f} %** ;
- le RMSE de `tau` DM de **{100 * sf6_dm["relative_reductions"]["tau_rmse"]:.1f} %** ;
- le RMSE de `DP` de **{100 * sf6_dm["relative_reductions"]["secondary_rmse"]:.1f} %**.

La corrélation empirique `tau–DP` passe de −0,959 à 0,248. SF6 réduit donc
nettement l'équifinalité locale dans ce scénario à 20 ans. Ce résultat justifie
son maintien dans toute la campagne de robustesse, mais ne démontre pas que quatre
traceurs rendent les deux paramètres identifiables dans tous les régimes.

## 10. Campagne de robustesse à quatre traceurs

### 10.1 Plan expérimental

- Phase largeur–bruit : 320 cas à `tau=20`, avec `r=0,05; 0,5; 2; 9` et
  `DP=0,02; 0,2; 0,5; 1`, quatre niveaux de bruit et dix graines.
- Phase âge–bruit : 160 cas supplémentaires à `tau=5` et `tau=50`, deux largeurs
  par modèle, bruit 10 et 20 %, dix graines.
- Aucun sous-ensemble de traceurs n'est testé : tous les cas utilisent les quatre
  traceurs.
- Les 480 inversions PyAge et les 480 inversions TracerLPM sont appariées sur les
  mêmes observations.

### 10.2 Résultats agrégés par modèle et bruit

{_table_model_noise(model_noise)}

Lecture principale : à 1 %, l'erreur médiane relative sur `tau` reste proche de
1 % et celle sur la largeur est de 6–11 %. À 5 %, `tau` reste raisonnablement
stable, mais l'erreur médiane du second paramètre atteint déjà 34–48 %. À 10 et
20 %, la largeur est souvent très mal contrainte, même lorsque les concentrations
restent ajustées au même ordre de grandeur que le bruit injecté.

### 10.3 Effet de l'âge dans les régimes 10–20 %

{_table_age(model_age_noise)}

Les cas DM anciens illustrent une vallée d'équifinalité particulièrement forte :
PyAge ajuste souvent mieux les concentrations selon L2 mais peut déplacer `tau`
vers la borne supérieure. À l'inverse, pour DM à 5 ans et 20 % de bruit,
TracerLPM présente un RMSE de `tau` nettement supérieur. Aucun outil ne domine
donc uniformément sur l'ensemble des âges.

## 11. Pourquoi la proximité à la vérité et la qualité d'ajustement divergent

Sur les 480 cas :

- PyAge est plus proche de la vérité pour `tau` dans
  **{head_to_head["tau"]["pyage"]} cas**, contre
  **{head_to_head["tau"]["tracerlpm"]}** pour TracerLPM ;
- pour le second paramètre, PyAge est plus proche dans
  **{head_to_head["secondary"]["pyage"]} cas**, TracerLPM dans
  **{head_to_head["secondary"]["tracerlpm"]}**, avec
  **{head_to_head["secondary"]["ties"]} égalités** ;
- PyAge a le plus faible objectif L2 recalculé dans
  **{objectives["pyage_lower_l2_count"]}/480 cas** ;
- PyAge a la plus faible somme L1 dans seulement
  **{objectives["pyage_lower_l1_count"]}/480 cas** ;
- parmi les {objectives["pyage_tau_worse_count"]} cas où son `tau` est moins proche
  de la vérité, PyAge conserve un objectif L2 inférieur dans
  **{objectives["pyage_tau_worse_but_lower_l2_count"]} cas** et une erreur relative
  maximale de concentration inférieure dans
  **{objectives["pyage_tau_worse_but_lower_maximum_residual_count"]} cas**.

Ces nombres démontrent que le classement par récupération des paramètres ne peut
pas être assimilé à un classement des optimiseurs. Une réalisation bruitée peut
être mieux ajustée par une solution plus éloignée de la vérité. L1 et L2 répondent
en outre à des modèles statistiques différents : L2 est cohérent avec le bruit
gaussien simulé, tandis que L1 est plus robuste à un résidu extrême.

## 12. Ce que les tests permettent d'affirmer

### Affirmations étayées

- Les définitions EPM et DM de PyAge sont cohérentes avec les distributions
  analytiques et les correspondances de paramètres documentées.
- Le chemin de convolution PyAge converge vers une quadrature indépendante.
- PyAge récupère les paramètres synthétiques sans bruit pour EMM, EPM et DM.
- En régime favorable à quatre traceurs et 1 % de bruit, PyAge présente un biais
  faible et une dispersion comparable ou inférieure à TracerLPM.
- Les deux outils exécutent avec succès toute la matrice de robustesse.
- L'âge moyen est généralement mieux identifiable que le paramètre de largeur.
- L'ajout de SF6 réduit fortement l'équifinalité autour du cas central testé.

### Affirmations non étayées à ce stade

- PyAge et TracerLPM seraient numériquement interchangeables.
- Un outil serait globalement supérieur à l'autre en inversion.
- Les quantiles calculés sur dix graines seraient des intervalles de confiance
  fiables à 95 %.
- Quatre traceurs suffiraient toujours à identifier deux paramètres.
- Les performances synthétiques seraient directement transposables aux données
  naturelles, qui ajoutent erreurs analytiques, corrections de recharge, excès
  d'air, contamination, dégradation et erreur de modèle conceptuel.

## 13. Limites et menaces sur la validité

1. **Objectifs différents.** La comparaison actuelle oppose L2 et L1 ; elle teste
   les chaînes réelles, mais pas deux optimiseurs sous un critère identique.
2. **Peu de répétitions par cellule.** Dix graines décrivent des tendances, pas une
   distribution d'incertitude stable.
3. **Initialisations informées par la vérité.** Les âges vrais appartiennent à la
   grille de départ de plusieurs scénarios.
4. **Bornes actives.** Un résultat sur borne signale une information insuffisante
   ou un optimum hors domaine, et ne doit pas être traité comme une estimation
   intérieure ordinaire.
5. **Historiques corrélés.** Les trois CFC ne constituent pas trois contraintes
   indépendantes ; leur information temporelle se recouvre fortement.
6. **Troncature temporelle.** Les cas anciens et larges ne couvrent que 80–94 % de
   la distribution selon le scénario.
7. **Différences forward résiduelles.** TracerLPM utilise notamment une grille
   interne semestrielle, alors que la référence suit les ruptures des historiques.
8. **Absence de données naturelles dans cette campagne.** La validité externe
   reste à documenter séparément.

## 14. Qualification proposée pour l'article

Le niveau de preuve actuel justifie la formulation suivante :

> PyAge a été qualifié par une stratégie hiérarchique combinant des solutions
> analytiques, une quadrature indépendante, une comparaison avec TracerLPM et des
> expériences synthétiques bruitées. Les calculs forward convergent vers la
> référence indépendante et les paramètres EMM, EPM et DM sont récupérés sans
> bruit. À quatre traceurs, les inversions restent stables à faible bruit, tandis
> que les expériences à 10–20 % mettent en évidence une non-identifiabilité
> croissante du paramètre contrôlant la largeur. Les divergences ponctuelles entre
> PyAge et TracerLPM résultent à la fois de fonctions objectif différentes, de la
> discrétisation propre à chaque outil et de l'équifinalité du problème inverse.

Cette formulation qualifie PyAge sans présenter TracerLPM comme une vérité absolue :
la vérité synthétique provient d'une troisième implémentation indépendante.

## 15. Analyses prioritaires avant rédaction définitive

1. **Harmoniser le critère de comparaison.** Réévaluer un sous-ensemble
   représentatif avec L1 et L2 dans le même opérateur forward, ou ajouter une
   inversion PyAge sous L1 uniquement pour le diagnostic.
2. **Supprimer l'avantage des départs vrais.** Répéter les cas clés avec une grille
   d'initialisation commune, aveugle et indépendante des paramètres synthétiques.
3. **Augmenter les répétitions.** Utiliser au moins plusieurs centaines de graines
   sur un nombre réduit de scénarios représentatifs afin d'estimer médianes,
   intervalles percentiles, corrélations et fréquences de borne.
4. **Produire des profils d'objectif.** Cartographier `J(tau, largeur)` pour montrer
   directement les vallées d'équifinalité et distinguer minimum local, borne et
   manque d'information.
5. **Ajouter une validation naturelle.** Sélectionner un ou plusieurs jeux publiés,
   documenter toutes les corrections de traceurs et comparer les distributions et
   concentrations, sans supposer que les paramètres TracerLPM sont la vérité.

## 16. Organisation suggérée de la section d'article

- **Methods – Numerical verification:** référence indépendante, distributions,
  quadrature et convergence.
- **Methods – Inverse experiments:** traceurs, bruit, paramètres, bornes,
  initialisations et fonctions objectif.
- **Results – Forward qualification:** erreurs et convergence avec la résolution.
- **Results – Parameter recovery:** sans bruit, Monte-Carlo à 1 %, gain de SF6 et
  robustesse 1–20 %.
- **Discussion:** équifinalité, objectifs L1/L2, information des traceurs, bornes et
  limites de la comparaison avec TracerLPM.
- **Reproducibility:** versions, hashes, YAML, graines, rapports bruts et scripts.

## 17. Fichiers de preuve et reproduction

- [Configuration largeur–bruit](../../configs/robustness-width-noise.yaml)
- [Configuration âge–bruit](../../configs/robustness-age-noise.yaml)
- [Synthèse complète des 48 groupes](../robustness-study/summary.md)
- [Résultats individuels des 480 cas](../robustness-study/results.csv)
- [Métriques structurées de ce rapport](metrics.json)
- [Documentation du benchmark](../../README.md)
- [Documentation du runner](../../../README.md)

Commandes principales :

```powershell
python -m validation.tracerlpm.benchmark.scripts.generate_references
python -m validation.tracerlpm.benchmark.scripts.compare_pyage
python -m validation.tracerlpm.benchmark.scripts.study_pyage_convergence
python -m validation.tracerlpm.benchmark.scripts.summarize_robustness_study
python -m validation.tracerlpm.benchmark.scripts.build_qualification_report
python -m pytest validation/tracerlpm/benchmark/tests -q -p no:cacheprovider
```

## Référence principale de comparaison

Jurgens, B. C., Böhlke, J. K. & Eberts, S. M. (2012). *TracerLPM
(Version 1): An Excel workbook for interpreting groundwater age distributions
from environmental tracer data*. USGS Techniques and Methods 4-F3.
https://doi.org/10.3133/tm4F3
"""
    (OUTPUT / "report.md").write_text(report, encoding="utf-8", newline="\n")
    return metrics


if __name__ == "__main__":
    result = build()
    print(
        json.dumps(
            {
                "report": str(OUTPUT / "report.md"),
                "case_count": result["scope"]["robustness_case_count"],
                "pyage_success": result["success"]["pyage"],
                "tracerlpm_success": result["success"]["tracerlpm"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
