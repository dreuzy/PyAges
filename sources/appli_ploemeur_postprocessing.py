import os
from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
import multiprocessing as mp

import global_parameters as gp
import ploemeur_postprocessing.folders as fold
import ploemeur_postprocessing.concentrations_obs as cobs
import ploemeur_postprocessing.concentrations_mod as cmod


def tracer_concentrations(
    df_conc_all,
    gaz_mod,
    fontsize_labels=14,
    fontsize_ticks=12,
    layout="colonne",
    gaz_prior=None,
    n_curves=5,
    prior_years=None,
    df_conc_red=None,   # <-- option pour superposer des points rouges
    result_dir=None
):
    """
    Trace les concentrations expérimentales (points noirs), 
    l’enveloppe des modèles calibrés (gris) 
    et éventuellement des modèles prior (rouge).
    Sauvegarde aussi la figure dans result_dir si fourni.
    """
    traceurs = df_conc_all["element"].unique()

    # Layout
    if layout == "ligne":
        fig, axes = plt.subplots(1, len(traceurs), figsize=(6 * len(traceurs), 5), sharey=False)
    else:  # colonne
        fig, axes = plt.subplots(len(traceurs), 1, figsize=(8, 4 * len(traceurs)), sharex=True)

    if len(traceurs) == 1:
        axes = [axes]

    # Date max dans toutes les sources
    max_date = max([df_conc_all["date"].max()] + [df.index.max() for df in gaz_mod.values()])

    for i, (ax, traceur) in enumerate(zip(axes, traceurs)):
        # Enveloppe gris des calibrés
        if traceur in gaz_mod:
            cmod.tracer_enveloppe(ax, gaz_mod[traceur], traceur, color="#606060", alpha=0.5)

        # Courbes prior rouges
        if gaz_prior is not None and traceur in gaz_prior:
            df_prior = gaz_prior[traceur]
            cols = df_prior.columns
            if n_curves is not None and n_curves < len(cols):
                step = max(1, len(cols) // n_curves)
                cols = cols[::step]
            for col in cols:
                ax.plot(df_prior.index, df_prior[col], lw=1, alpha=0.8, color="red")

        # Points noirs
        data = df_conc_all[df_conc_all["element"] == traceur]
        ax.errorbar(
            data["date"],
            data["concentration"],
            yerr=0.2 * data["concentration"],
            fmt="o",
            capsize=3,
            color="black",
            markersize=5,
            zorder=5,
        )

        # Points rouges (prior, si dispo)
        if df_conc_red is not None:
            data_red = df_conc_red[df_conc_red["element"] == traceur]
            ax.errorbar(
                data_red["date"],
                data_red["concentration"],
                yerr=0.2 * data_red["concentration"],
                fmt="o",
                capsize=3,
                color="red",
                markersize=5,
                zorder=10,
            )

        # Axes
        ax.set_xlabel("Date", fontsize=fontsize_labels)
        ax.set_ylabel(f"{traceur} (pptv)", fontsize=fontsize_labels)
        ax.set_ylim(bottom=0)
        ax.set_xlim(left=1960, right=max_date + 2.5)

        yticks = ax.get_yticks()
        ax.set_yticks(yticks[::2])
        ax.tick_params(axis="both", labelsize=fontsize_ticks)

        # Légende
        if i == 0:
            handles = [
                plt.Line2D([0], [0], color="black", marker="o", linestyle="None", label="Data"),
                plt.Rectangle((0, 0), 1, 1, color="darkgrey", alpha=0.9, label="Calibrated models\n(2004–2024)"),
            ]
            if gaz_prior is not None:
                if prior_years is not None:
                    debut, fin = prior_years
                    label_prior = f"Prior models\n({debut}–{fin})"
                else:
                    label_prior = "Prior models"
                handles.append(plt.Line2D([0], [0], color="red", lw=1, label=label_prior))
            ax.legend(handles=handles, loc="upper left", fontsize=fontsize_labels, frameon=False)

    plt.tight_layout()

    # --- Sauvegarde optionnelle ---
    if result_dir is not None:
        result_dir = Path(result_dir)
        result_dir.mkdir(parents=True, exist_ok=True)

        # Cherche un index libre (figure_001.png, figure_002.png, …)
        idx = 1
        while (result_dir / f"figure_{idx:03d}.png").exists():
            idx += 1

        out_file = result_dir / f"figure_{idx:03d}.png"
        fig.savefig(out_file, dpi=300)
        # print(f"Figure sauvegardée : {out_file}")
        
        # 🔥 Créer la vidéo avec toutes les figures sauvegardées

    plt.show()



# ======================================================================
# === Fonctions utilitaires pour charger les données ===================
# ======================================================================

def charger_donnees(
    df,
    mode="calib",
    base_type=None,
    prior=None,
    submode=None,
    annee_debut=None,
    annee_fin=None
):
    """
    Charge les données (calibrées ou prior) selon le mode choisi.

    Paramètres
    ----------
    df : DataFrame
        DataFrame des répertoires construits par fold.construire_dataframe.
    mode : {"calib", "prior"}
        - "calib" → répertoire avec durée max
        - "prior" → répertoire filtré par critères
    base_type, prior, submode, annee_debut, annee_fin : str ou int
        Critères utilisés uniquement si mode="prior".

    Retour
    ------
    tuple :
        - Si mode="calib" → (df_conc, df_mod, gaz_mod)
        - Si mode="prior" → (df_mod, gaz_mod)
    """
    if mode == "calib":
        df_all = fold.trouver_repertoires_df(df, duree_max=True, afficher=False)
        dossier_cible = df_all.iloc[0]["chemin"]

        df_conc = cobs.charger_concentrations(dossier_cible)
        df_mod, gaz_mod = cmod.charger_concentrations(dossier_cible)

        return df_conc, df_mod, gaz_mod

    elif mode == "prior":
        criteres = {
            "base_type": base_type,
            "prior": prior,
            "mode": submode,
        }
        # Ajouter les années seulement si elles sont fournies
        if annee_debut is not None:
            criteres["annee_debut"] = annee_debut
        if annee_fin is not None:
            criteres["annee_fin"] = annee_fin

        df_year_prior = fold.trouver_repertoires_df(df, criteres=criteres, afficher=False)
        dossier_cible = df_year_prior.iloc[0]["chemin"]

        df_mod, gaz_mod = cmod.charger_concentrations(dossier_cible)
        return df_mod, gaz_mod

    else:
        raise ValueError("mode doit être 'calib' ou 'prior'")


def lister_plages_annees(df_subset):
    """
    Affiche et retourne la liste des couples (annee_debut, annee_fin)
    pour un DataFrame subset.
    """
    plages = list(zip(df_subset["annee_debut"], df_subset["annee_fin"]))
    
    print("\n=== Plages d'années trouvées ===")
    for debut, fin in plages:
        print(f"  {debut} – {fin}")
    
    return plages


def map_conditionnement(base_type, prior_flag, submode):
    """
    Mappe une combinaison (base_type, prior_flag, submode) vers
    une combinaison éventuellement transformée.

    Exemple :
        ("suc", "prior", "double")  -> ("span", "prior", "double")
        ("span", "prior", "double") -> ("span", "", "double")
    """
    mapping = {
        ("suc", "prior", "double"): ("span", "prior", "double"),
        ("span", "prior", "double"): ("span", "", "double"),
    }

    return mapping.get((base_type, prior_flag, submode), (base_type, prior_flag, submode))


def analyser_puits_distribution(
    dossier, puits, distribution,
    base_type="suc", prior_flag="prior", submode="double",
    tracer_global=True, tracer_subset=True,
    layout="colonne", n_curves=20,
    fontsize_labels=16, fontsize_ticks=12
):
    """
    Pipeline complet pour un puits + une distribution.
    """
    # Application du mapping conditionnel
    base_type_cond, prior_flag_cond, submode_cond = map_conditionnement(
        base_type, prior_flag, submode
    )

    # Recherche des répertoires
    folders = fold.trouver_repertoires(dossier, [puits, distribution])
    df = fold.construire_dataframe(folders)

    # Données calibrées globales
    df_conc_all, df_mod_all, gaz_mod_all = charger_donnees(df, mode="calib")

    # Répertoire de sortie
    result_dir = fold.make_subdirs(dossier, "postproc", puits, distribution)
    # print("Chemin final :", result_dir)

    # CAS 1 : GLOBAL
    if tracer_global:
        df_prior_all, gaz_prior_all = charger_donnees(
            df,
            mode="prior",
            base_type=base_type,
            prior=prior_flag,
            submode=submode,
        )

        tracer_concentrations(
            df_conc_all, gaz_mod_all,
            fontsize_labels=fontsize_labels,
            fontsize_ticks=fontsize_ticks,
            layout=layout,
            gaz_prior=None,   # prior global désactivé
            n_curves=n_curves,
            prior_years=None,
            df_conc_red=None,
            result_dir=result_dir
        )

    # CAS 2 : SUBSET
    if tracer_subset:
        df_subset = fold.trouver_sauf_annees(
            df,
            base_type=base_type,
            prior=prior_flag,
            submode=submode,
            afficher=False
        )

        for _, row in df_subset.iterrows():
            dossier_cible = row["chemin"]
            prior_years = (row["annee_debut"], row["annee_fin"])
            
            # print("Subset :", dossier_cible)

            # Points expérimentaux spécifiques (rouge)
            df_conc_red = cobs.charger_concentrations(dossier_cible)

            # Modèles prior spécifiques (rouge)
            try:
                df_prior_all, gaz_prior_all = cmod.charger_concentrations(dossier_cible)
            except Exception:
                df_prior_all, gaz_prior_all = None, None

            tracer_concentrations(
                df_conc_all, gaz_mod_all,
                fontsize_labels=fontsize_labels,
                fontsize_ticks=fontsize_ticks,
                layout=layout,
                gaz_prior=gaz_prior_all,
                n_curves=n_curves,
                prior_years=prior_years,
                df_conc_red=df_conc_red,
                result_dir=result_dir
            )

    # Vidéo finale
    fold.make_video_from_figures(result_dir, "concentrations_video.mp4", fps=1)


# ======================
# MAIN
# ======================

def run_case(args):
    dossier, puits, distribution, base_type, prior_flag, submode = args
    print(f"=== Analyse {puits} | {distribution} ===")
    return analyser_puits_distribution(
        dossier, puits, distribution,
        base_type=base_type,
        prior_flag=prior_flag,
        submode=submode,
        tracer_global=True,
        tracer_subset=True,
        layout="colonne",
        n_curves=20,
        fontsize_labels=16,
        fontsize_ticks=12
    )



if __name__ == "__main__":
    # --- Données sources : plusieurs dossiers racines ---
    dossiers_list = [
        Path(r"2025-09-24, err03"),
        Path(r"2025-09-24, err02"),
        Path(r"2025-09-24, err02, new")
    ]
    dossiers_list = [gp.ROOT_DIRECTORY_RESULTS / d for d in dossiers_list]

    # --- Listes de cas à traiter ---
    # puits_list = ["PE", "F11", "F09", "F34", "MF1", "MF4", "F38"]
    # distributions_list = ["exp_shifted", "ig_shifted", "ig"]
    puits_list = ["F11", "F09"]
    distributions_list = ["exp_shifted", "ig_shifted"]

    # --- Options globales ---
    base_type = "suc"
    prior_flag = "prior"
    submode = "double"

    # --- Paramètre global ---
    use_multiprocessing = True   # ⬅️ change à False pour exécution séquentielle

    # Générer toutes les combinaisons (dossier, puits, distribution)
    combos = [
        (dossier, puits, distribution, base_type, prior_flag, submode)
        for dossier in dossiers_list
        for puits in puits_list
        for distribution in distributions_list
    ]

    if use_multiprocessing:
        n_cores = mp.cpu_count()
        print(f"Utilisation de {n_cores} cœurs en parallèle")
        with mp.Pool(processes=n_cores) as pool:
            pool.map(run_case, combos)
    else:
        print("Exécution séquentielle")
        for args in combos:
            run_case(args)

