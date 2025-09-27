import os
from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt

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
    df_conc_red=None   # <-- option pour superposer des points rouges
):
    """
    Trace les concentrations expérimentales (points noirs), 
    l’enveloppe des modèles calibrés (gris) 
    et éventuellement des modèles prior (rouge).
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

        # Points noirs (calibrés, durée max)
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

        # Axe X : de 2000 à max_date + 2.5 ans
        ax.set_xlim(left=2000, right=max_date + 2.5)

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


def traiter_un_repertoire(
    df,
    row=None,
    n_curves=20,
    fontsize_labels=16,
    fontsize_ticks=12,
    layout="colonne",
    prior_global=False,
    annee_debut_prior=None,
    annee_fin_prior=None,
):
    """
    Charge et trace les données pour un répertoire (row) ou pour un prior global.

    Paramètres
    ----------
    df : DataFrame
        DataFrame complet des répertoires.
    row : Series, optionnel
        Ligne du DataFrame pour un répertoire spécifique.
        Ignoré si prior_global=True.
    n_curves : int
        Nombre de courbes rouges (prior) à tracer (sauf prior_global).
    fontsize_labels, fontsize_ticks : int
        Tailles de police pour labels et ticks.
    layout : str
        "colonne" ou "ligne".
    prior_global : bool
        Si True → trace uniquement les calibrations globales
                   (sans prior rouge, sans points rouges).
    annee_debut_prior, annee_fin_prior : int
        Années utilisées si prior_global=True.
    """

    # Chargement des modèles calibrés (durée max global)
    df_conc_all, df_mod_all, gaz_mod_all = charger_donnees(df, mode="calib")

    if prior_global:
        # On ne trace QUE les calibrés, les points restent noirs
        prior_years = (annee_debut_prior, annee_fin_prior)
        gaz_prior_all = None
        df_conc = None  # pas de points rouges

    else:
        # Cas d'un répertoire spécifique → on ajoute le prior rouge
        dossier_cible = row["chemin"]
        prior_years = (row["annee_debut"], row["annee_fin"])
        df_conc = cobs.charger_concentrations(dossier_cible)

        try:
            df_prior_all, gaz_prior_all = cmod.charger_concentrations(dossier_cible)
        except Exception:
            gaz_prior_all = None

    # Tracé
    tracer_concentrations(
        df_conc_all,          # observations calibrées globales (points noirs)
        gaz_mod_all,
        fontsize_labels=fontsize_labels,
        fontsize_ticks=fontsize_ticks,
        layout=layout,
        gaz_prior=gaz_prior_all,  # prior rouge seulement si row
        n_curves=n_curves,
        prior_years=prior_years,
        df_conc=df_conc          # points rouges seulement si row
    )


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




# ======================================================================
# === MAIN =============================================================
# ======================================================================
# ======================================================================
# === MAIN =============================================================
# ======================================================================
if __name__ == "__main__":
    # =======================
    # PARAMÈTRES À CONFIGURER
    # =======================

    # --- Données sources ---
    dossier = Path(r"2025-09-24, err02")
    puits = "F11"
    distribution = "exp_shifted"

    # --- Recherche subset et prior ---
    base_type = "suc"
    prior_flag = "prior"
    submode = "double"
    
    # Application du mapping conditionnel avec les variables définies
    base_type_cond, prior_flag_cond, submode_cond = map_conditionnement(
        base_type, prior_flag, submode
    )

    # --- Options de tracé ---
    layout = "colonne"       # "ligne" ou "colonne"
    n_curves = 20            # nombre max de courbes rouges (None = toutes)
    fontsize_labels = 16
    fontsize_ticks = 12

    # --- Activation des cas ---
    tracer_global = True     # tracer le cas global (points noirs + gris)
    tracer_subset = True     # tracer les répertoires subset (rouge)

    # =======================
    # RECHERCHE DES RÉPERTOIRES
    # =======================
    folders = fold.trouver_repertoires(dossier, [puits, distribution])
    df = fold.construire_dataframe(folders)

    # Données calibrées globales (durée max)
    df_conc_all, df_mod_all, gaz_mod_all = charger_donnees(df, mode="calib")

    # base_type_cond, prior_flag_cond, submode_cond = map_conditionnement(base_type, prior_flag, submode)
    # df_mod_al2, gaz_mod_all2 = charger_donnees(
    #     df,
    #     mode=prior_flag_cond,
    #     base_type=base_type_cond,
    #     prior=prior_flag,
    #     submode=submode_cond,
    #     annee_debut=None,   # optionnel
    #     annee_fin=None      # optionnel
    # )
    

    # =======================
    # CAS 1 : GLOBAL
    # =======================
    if tracer_global:
        df_prior_all, gaz_prior_all = charger_donnees(
            df,
            mode="prior",
            base_type=base_type,
            prior=prior_flag,
            submode=submode,
            annee_debut=None,   # optionnel
            annee_fin=None      # optionnel
        )

        tracer_concentrations(
            df_conc_all,         # points noirs
            gaz_mod_all,         # enveloppe grise
            fontsize_labels=fontsize_labels,
            fontsize_ticks=fontsize_ticks,
            layout=layout,
            gaz_prior=None,   # prior global
            n_curves=n_curves,
            prior_years=None,          # pas d’années affichées
            df_conc_red=None           # pas de points rouges
        )

    # =======================
    # CAS 2 : SUBSET
    # =======================
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
            
            print(dossier_cible)

            # Points expérimentaux spécifiques → rouge
            df_conc_red = cobs.charger_concentrations(dossier_cible)

            # Modèles prior spécifiques → courbes rouges
            try:
                df_prior_all, gaz_prior_all = cmod.charger_concentrations(dossier_cible)
            except Exception:
                df_prior_all, gaz_prior_all = None, None

            tracer_concentrations(
                df_conc_all,          # points noirs (global)
                gaz_mod_all,          # enveloppe grise (global)
                fontsize_labels=fontsize_labels,
                fontsize_ticks=fontsize_ticks,
                layout=layout,
                gaz_prior=gaz_prior_all,   # courbes rouges
                n_curves=n_curves,
                prior_years=prior_years,   # années affichées
                df_conc_red=df_conc_red    # points rouges
            )

