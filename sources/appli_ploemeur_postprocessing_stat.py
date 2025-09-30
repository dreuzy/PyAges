import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

import global_parameters as gp
import ploemeur_postprocessing.folders as fold
import ploemeur_postprocessing.concentrations_obs as cobs
import ploemeur_postprocessing.concentrations_mod as cmod


import numpy as np

def visualiser_results_global(
    df,
    puits=None,
    distribution=None,
    erreur=None,
    colonne_date="date",
    colonne_mediane="median_mean",
    colonne_std="median_std",
    save_dir=None
):
    """
    Affiche (et éventuellement sauvegarde) les courbes
    médiane ± écart-type en fonction de la date,
    avec un style adapté à une présentation PowerPoint.
    """

    # Vérification des colonnes attendues
    colonnes_requises = {
        colonne_date, colonne_mediane, colonne_std,
        "puits", "distribution", "erreur"
    }
    if not colonnes_requises.issubset(df.columns):
        raise ValueError(f"Le DataFrame doit contenir au moins : {colonnes_requises}")

    # Identifier le paramètre laissé variable
    params = {"puits": puits, "distribution": distribution, "erreur": erreur}
    unset_params = [k for k, v in params.items() if v is None]
    
    if len(unset_params) != 1:
        raise ValueError("Fixer exactement 2 des paramètres (puits, distribution, erreur) et laisser le 3e à None.")
    
    param_variable = unset_params[0]

    # Filtrer selon les paramètres fixés
    filtered_df = df.copy()
    for k, v in params.items():
        if v is not None:
            filtered_df = filtered_df[filtered_df[k] == v]

    if filtered_df.empty:
        print("⚠️ Aucun résultat trouvé pour ces filtres.")
        return

    # Traduction des distributions
    dist_nice = {
        "exp_shifted": "Shifted Exponential",
        "ig": "Inverse Gaussian",
        "ig_shifted": "Shifted Inverse Gaussian"
    }

    # Nom dans la légende selon le paramètre variable
    legend_label_name = {
        "puits": "piezos",
        "distribution": "distribution",
        "erreur": "error"
    }[param_variable]

    # Valeurs du paramètre variable
    valeurs = sorted(filtered_df[param_variable].unique())

    plt.figure(figsize=(10, 6))

    for val in valeurs:
        df_sub = filtered_df[filtered_df[param_variable] == val]
        if df_sub.empty:
            continue

        # Formatage du label
        if param_variable == "distribution":
            val_label = dist_nice.get(val, val)
        elif param_variable == "erreur":
            val_label = f"{int(val * 100)}%"
        else:
            val_label = val

        # Tracé en points + barres d'erreur
        plt.errorbar(
            df_sub[colonne_date],
            df_sub[colonne_mediane],
            yerr=df_sub[colonne_std],
            fmt='o',          # points uniquement
            markersize=8,     # plus gros
            capsize=5,        # barres visibles
            elinewidth=2,     # barres épaisses
            linewidth=0.5,
            label=f"{legend_label_name}={val_label}"
        )

    # Construction du titre
    titre_parts = []
    if puits is not None:
        titre_parts.append(f"piezo={puits}")
    if distribution is not None:
        titre_parts.append(dist_nice.get(distribution, distribution))
    if erreur is not None:
        titre_parts.append(f"error={int(erreur * 100)}%")
    titre_final = " | ".join(titre_parts) if titre_parts else "Résultats globaux"

    plt.title(titre_final, fontsize=18)
    plt.xlabel(colonne_date, fontsize=16)
    plt.ylabel("Median", fontsize=16)

    # ✅ Axe X : années entières tous les 5 ans
    x_data = filtered_df[colonne_date]
    x_years = sorted(set(int(x) for x in x_data))
    xmin, xmax = min(x_years), max(x_years)
    step_x = 5
    ticks_x = list(range(xmin - (xmin % step_x), xmax + step_x, step_x))
    plt.xticks(ticks_x, [str(y) for y in ticks_x], fontsize=14)

    # ✅ Axe Y : ticks réguliers, min pas 5, max 6 valeurs
    y_data = filtered_df[colonne_mediane]
    y_min_raw, y_max_raw = y_data.min(), y_data.max()
    y_min = int(np.floor(y_min_raw))
    y_max = int(np.ceil(y_max_raw))

    range_y = y_max - y_min
    if range_y <= 25:
        step_y = 5
    elif range_y <= 50:
        step_y = 10
    elif range_y <= 100:
        step_y = 20
    else:
        step_y = max(5, round(range_y / 5))

    start_tick = y_min - (y_min % step_y)
    end_tick = y_max + (step_y - (y_max % step_y)) if (y_max % step_y) != 0 else y_max
    yticks = list(range(start_tick, end_tick + 1, step_y))

    if len(yticks) > 6:
        yticks = yticks[:6]

    plt.yticks(yticks, fontsize=14)

    plt.legend(fontsize=14)
    plt.grid(True, alpha=0.4)
    plt.tight_layout()

    # ✅ Sauvegarde ou affichage
    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{param_variable}_" + "_".join(
            f"{k}-{v}" for k, v in params.items() if v is not None
        ) + ".png"
        filepath = save_dir / filename
        plt.savefig(filepath, dpi=300)
        print(f"✅ Figure sauvegardée : {filepath}")
    else:
        plt.show()


def generer_toutes_les_figures():
    # 1) Lecture du fichier global
    csv_path = Path(gp.ROOT_DIRECTORY_RESULTS) / "resultats_global.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Le fichier {csv_path} est introuvable.")
    
    df_test = pd.read_csv(csv_path)

    # 2) Répertoire de sauvegarde des figures
    output_dir = Path(gp.ROOT_DIRECTORY_RESULTS) / "plots_globales"
    output_dir.mkdir(exist_ok=True, parents=True)

    # 3) Lister les valeurs uniques
    puits_vals = sorted(df_test["puits"].unique())
    dist_vals = sorted(df_test["distribution"].unique())
    err_vals = sorted(df_test["erreur"].unique())

    # ✅ VARIANT 1 : faire varier "erreur", fixer puits + distribution
    for p in puits_vals:
        for d in dist_vals:
            visualiser_results_global(
                df_test,
                puits=p,
                distribution=d,
                erreur=None,
                save_dir=output_dir
            )

    # ✅ VARIANT 2 : faire varier "distribution", fixer puits + erreur
    for p in puits_vals:
        for e in err_vals:
            visualiser_results_global(
                df_test,
                puits=p,
                distribution=None,
                erreur=e,
                save_dir=output_dir
            )

    # ✅ VARIANT 3 : faire varier "puits", fixer distribution + erreur
    for d in dist_vals:
        for e in err_vals:
            visualiser_results_global(
                df_test,
                puits=None,
                distribution=d,
                erreur=e,
                save_dir=output_dir
            )
    
    print(f"\n✅ Toutes les figures ont été générées dans : {output_dir}")


# -------------------------------------------
#            EXECUTION DIRECTE
# -------------------------------------------
if __name__ == "__main__":
    generer_toutes_les_figures()
