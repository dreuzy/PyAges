import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import random

import global_parameters as gp
import ploemeur_postprocessing.folders as fold
import ploemeur_postprocessing.concentrations_obs as cobs
import ploemeur_postprocessing.concentrations_mod as cmod
from matplotlib.ticker import MaxNLocator
from matplotlib.dates import DateFormatter

import numpy as np


def build_output_filepath( date, result_scope, submode, extension="csv"):
    """
    Construit le chemin complet du fichier de sortie avec les conventions standardisées.

    Paramètres
    ----------
    gp : module ou objet contenant ROOT_DIRECTORY_RESULTS
    date : str, par ex. "2025-10-02"
    result_scope : str, par ex. "ploemeur_es"
    submode : str, par ex. "double"
    extension : str, par défaut "csv"

    Retour
    ------
    pathlib.Path
        Chemin complet du fichier
    """
    return gp.ROOT_DIRECTORY_RESULTS / f"{date}_resultats_global_{result_scope}_{submode}.{extension}"



# ✅ Styles globaux pour les figures (présentation/papier)
plt.rcParams.update({
    "figure.figsize": (12, 6),    # Taille par défaut des figures
    "figure.titlesize": 28,       # ✅ Taille du titre principal (plt.suptitle)
    "axes.titlesize": 26,         # Taille des titres locaux (plt.title ou ax.set_title)
    "axes.labelsize": 20,         # Taille des labels X/Y
    "xtick.labelsize": 18,        # Taille des ticks en X
    "ytick.labelsize": 18,        # Taille des ticks en Y
    "legend.fontsize": 20,        # Taille des légendes
})

def visualiser_results_global(
    df,
    puits=None,
    distribution=None,
    erreur=None,
    colonne_date="date",
    colonne_mediane="median_mean",
    colonne_std="median_std",
    save_dir=None, 
    suffix=""
):
    """
    Affiche (et éventuellement sauvegarde) les courbes
    médiane ± écart-type en fonction de la date,
    avec un style adapté à une présentation PowerPoint.
    """

    # Vérification des colonnes attendues
    colonnes_requises = {
        colonne_date, colonne_mediane, colonne_std,
        "puits", "distribution", "erreur", "prior_option"
    }
    if not colonnes_requises.issubset(df.columns):
        raise ValueError(f"Le DataFrame doit contenir au moins : {colonnes_requises}")

    # ✅ Filtrer sur prior_option == True
    filtered_df = df[df["prior_option"] == True].copy()

    # Identifier le paramètre laissé variable
    params = {"puits": puits, "distribution": distribution, "erreur": erreur}
    unset_params = [k for k, v in params.items() if v is None]
    
    if len(unset_params) != 1:
        raise ValueError("Fixer exactement 2 des paramètres (puits, distribution, erreur) et laisser le 3e à None.")
    
    param_variable = unset_params[0]

    # Filtrer selon les paramètres fixés
    for k, v in params.items():
        if v is not None:
            filtered_df = filtered_df[filtered_df[k] == v]

    if filtered_df.empty:
        # print("⚠️ Aucun résultat trouvé pour ces filtres.")
        return

    # Traduction des distributions
    dist_nice = {
        "exp_shifted": "Shifted Exponential",
        "ig": "Inverse Gaussian",
        "ig_shifted": "Shifted Inverse Gaussian"
    }

    # Nom dans la légende selon le paramètre variable
    legend_label_name = {
        "puits": "well",
        "distribution": "distribution",
        "erreur": "error"
    }[param_variable]

    # Valeurs du paramètre variable (ceux qui changent dans la figure)
    valeurs = sorted(filtered_df[param_variable].unique())

    # ✅ Couleurs spécifiques uniquement si ce sont les puits qui varient
    couleurs_puits = {
        "F09": "black",
        "F11": "red",
        "F34": "blue",
        "MF1": "green",
        "F38": "orange",
        "MF4": "purple",
        "PE": "brown",
        "PZ2": "pink",
        "PSR1": "cyan",
    }
    couleurs_distributions = {
        "exp_shifted": "red",
        "ig_shifted": "green",
        "ig": "blue",
        "dirac_double_1_set": "black",
        "gamma": "orange",
        "uniform": "purple",
        "exp": "brown",
    }
    couleurs_erreur = {
        0.1: "black",
        0.2: "red",
        0.3: "blue",
        0.4: "green",
    }
    use_puits_colors = (param_variable == "puits")

    plt.figure()

    for val in valeurs:
        df_sub = filtered_df[filtered_df[param_variable] == val]
        if df_sub.empty:
            continue

        # Label selon ce qui varie
        if param_variable == "distribution":
            val_label = dist_nice.get(val, val)
        elif param_variable == "erreur":
            val_label = f"{int(val * 100)}%"
        else:
            val_label = val

        # ✅ Gestion des couleurs
        if param_variable == "puits":
            # Cas où les puits varient → couleur selon le dictionnaire
            color = couleurs_puits.get(str(val), None)
        elif param_variable == "distribution":
            color = couleurs_distributions.get(str(val), None)
        elif param_variable == "erreur":
            color = couleurs_erreur.get(str(val), None)
        else:
            color = random.choice(["black", "red", "blue", "green", "orange", "purple", "brown", "cyan", "pink"])
            
        plt.errorbar(
            df_sub[colonne_date],
            df_sub[colonne_mediane],
            yerr=df_sub[colonne_std],
            fmt='o--',          # ⬅ points + ligne en dash
            markersize=15,      # ⬅ points plus gros
            capsize=5,
            elinewidth=3,
            linewidth=2.5,      # ⬅ épaisseur de la ligne
            # label=f"{legend_label_name}={val_label}",
            label=f"{val_label}",
            color=color
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

    plt.title(titre_final)
    plt.xlabel(colonne_date)
    plt.ylabel("Median")
    
    plt.xlabel(colonne_date,fontsize=plt.rcParams["axes.titlesize"]+10)
    plt.ylabel("Median (years)",fontsize=plt.rcParams["axes.titlesize"]+10)
    plt.title(titre_final, fontweight="bold",fontsize=plt.rcParams["figure.titlesize"]+4)


    # =========================================================
    # ✅ Axe Y : 3 à 4 ticks, entiers ou multiples de 2.5,
    #            sans valeurs négatives, marges automatiques
    # =========================================================
    y_data = filtered_df[colonne_mediane]
    y_min_raw, y_max_raw = y_data.min(), y_data.max()
    
    if y_min_raw == y_max_raw:
        base = y_min_raw
        ticks = [base, base + 2.5, base + 5]
        ticks = [t for t in ticks if t >= 0]
        plt.yticks(ticks)
    else:
        range_y = y_max_raw - y_min_raw
        margin = 0.1 * range_y
        y_min_adj = y_min_raw - margin
        y_max_adj = y_max_raw + margin
        y_min_tick = np.floor(y_min_adj)
        y_max_tick = np.ceil(y_max_adj)
        max_ticks = 4
        min_ticks = 3

        step_y = 5
        ticks = list(np.arange(
            np.floor(y_min_tick / step_y) * step_y,
            np.ceil(y_max_tick / step_y) * step_y + step_y,
            step_y
        ))
        if len(ticks) < min_ticks:
            step_y = 2.5
            ticks = list(np.arange(
                np.floor(y_min_tick / step_y) * step_y,
                np.ceil(y_max_tick / step_y) * step_y + step_y,
                step_y
            ))
        if len(ticks) > max_ticks:
            indices = np.linspace(0, len(ticks) - 1, max_ticks).astype(int)
            ticks = [ticks[i] for i in indices]
        ticks = [t for t in ticks if t >= 0]
        ticks = [round(t, 2) for t in ticks]
        plt.yticks(ticks)

    # =========================================================
    # ✅ Axe X : ticks 2005, 2010, 2015, 2020
    # =========================================================
    plt.xlim(2004, 2026)
    xticks = [year for year in range(2005, 2026) if year % 5 == 0]
    plt.xticks(xticks)


    # ✅ Récupération de l'axe courant
    ax = plt.gca()

    # ✅ Rendre les axes (spines) deux fois plus épais
    for spine in ax.spines.values():
        spine.set_linewidth(2)    

    
    plt.grid(True, alpha=0.4)
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_linewidth(3)  # tu peux mettre 3 ou 4 si tu veux encore plus épais

    ax.tick_params(axis="both", labelsize=plt.rcParams["xtick.labelsize"]+10)
    # Axe Y : max 4 ticks
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    
    plt.legend(
        loc="best",
        frameon=False,
        fontsize=plt.rcParams["legend.fontsize"]+10,
        markerscale=1.0   # ✅ Agrandit les symboles dans la légende
    )
    
    plt.tight_layout()


    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{param_variable}_" +
            "_".join(f"{k}-{v}" for k, v in params.items() if v is not None) +
            (suffix if suffix else "") +
            ".png"
        )
        filepath = save_dir / filename
        plt.savefig(filepath, dpi=300)
    else:
        plt.show()


def generer_toutes_les_figures(csv_path,date,result_scope,submode):
    # 1) Lecture du fichier global
    if not csv_path.exists():
        raise FileNotFoundError(f"Le fichier {csv_path} est introuvable.")
    
    df_test = pd.read_csv(csv_path)

    # 2) Répertoire de sauvegarde des figures
    output_dir = build_output_filepath( date, result_scope, submode, extension="")
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
    
    for d in dist_vals:           # distribution fixée
        for e in err_vals:        # erreur fixée
            # for puits_group, label in groupes_puits:
            visualiser_results_global(
                df_test,
                puits=None,  # ✅ liste de puits ici
                distribution=d,
                erreur=e,
                save_dir=output_dir,
                suffix=f""  # ✅ suffixe ajouté au nom du fichier
            )    
            
    groupes_puits = [
        (["F09", "F34"], "F09_F34"),
        # (["F11", "F38", "MF1"], "F11_F38_MF1"),
        # (["MF4", "PE"], "MF4_PE"),
        (["F11", "F38", "MF1", "MF4", "PE"], "F11_F38_MF1_MF4_PE"),
        # (["MF4", "PE"], "MF4_PE"),
        (["PZ2","PSR1"], "PZ2_PSR1") 
    ]
    
    for d in dist_vals:           # distribution fixée
        for e in err_vals:        # erreur fixée
            for puits_group, label in groupes_puits:
                
                # ✅ On filtre df_test uniquement sur CE groupe de puits
                df_subset = df_test[df_test["puits"].isin(puits_group)]
                
                if df_subset.empty:
                    # print(f"⚠️ Aucun résultat trouvé pour {label} (distribution={d}, erreur={e})")
                    continue
    
                # ✅ Appel normal, mais sur df_subset et avec suffix explicite
                visualiser_results_global(
                    df_subset,
                    puits=None,  # important : c'est maintenant df_subset qui contient les bons puits
                    distribution=d,
                    erreur=e,
                    save_dir=output_dir,
                    suffix=f"_{label}"
                )

    print(f"\n✅ Toutes les figures ont été générées dans : {output_dir}")


# -------------------------------------------
#            EXECUTION DIRECTE
# -------------------------------------------
if __name__ == "__main__":
    generer_toutes_les_figures(Path(r"D:\results\PyAge\2025-10-02_resultats_global_ploemeur_es_double"), "2025-10-02", "ploemeur_es","double")

