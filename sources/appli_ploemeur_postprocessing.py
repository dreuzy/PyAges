import os
from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
import multiprocessing as mp
import numpy as np
import warnings
from matplotlib.ticker import MaxNLocator
from matplotlib.dates import DateFormatter

import global_parameters as gp
import ploemeur_postprocessing.folders as fold
import ploemeur_postprocessing.concentrations_obs as cobs
import ploemeur_postprocessing.concentrations_mod as cmod

from tracer.tracer_root import Tracer  # <-- ta classe Tracer
from appli_ploemeur_postprocessing_stat import generer_toutes_les_figures, build_output_filepath

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


def tracer_stat(df_stats, df_stat_prior, df_suc, distribution, puits, save_path=None, use_multiprocessing=False):
    """
    Affiche :
    - une bande horizontale correspondant à la médiane ± écart-type
      en utilisant uniquement la ligne d'index 1 de df_stats ("Full Chronicle"),
    - les points issus de df_stat_prior ("In Chronicle") avec médiane ± écart-type en rouge,
    - les points issus de df_suc avec médiane ± écart-type en bleu.
    """

    # Vérifier le nombre de lignes
    n_lignes = len(df_stats)
    
    if n_lignes == 0 or n_lignes > 4:
        raise ValueError(
            f"❌ ERREUR dans tracer_stat : df_stats contient {n_lignes} lignes, "
            "attendu entre 1 et 4.\n"
            f"- distribution : {distribution}\n"
            f"- puits        : {puits}\n"
            f"- shape        : {df_stats.shape if df_stats is not None else 'None'}\n"
            f"- colonnes     : {None if df_stats is None else list(df_stats.columns)}\n"
            f"- aperçu       :\n{None if df_stats is None else df_stats.head()}\n"
        )
    
    elif n_lignes >= 2:
        ligne = df_stats.iloc[1]   # ✅ 2ème ligne
    else:
        # warnings.warn(
        #     f"⚠️ df_stats ne contient qu'une seule ligne, "
        #     f"on utilise la première ({puits}, {distribution}).",
        #     UserWarning
        # )
        ligne = df_stats.iloc[0]
    
    median = ligne["median_mean"]
    std = ligne["median_std"]
    
    # ... reste du code pour le tracé ...

    # Conversion des colonnes date en datetime
    df_stats = df_stats.copy()
    df_stats["date"] = pd.to_datetime(df_stats["date"].astype(int), format="%Y")
    df_stat_prior = df_stat_prior.copy()
    df_stat_prior["date"] = pd.to_datetime(df_stat_prior["date"].astype(int), format="%Y")
    df_suc = df_suc.copy()
    df_suc["date"] = pd.to_datetime(df_suc["date"].astype(int), format="%Y")

    # Bornes temporelles
    year_min_full = df_stats["date"].dt.year.min()
    year_max_full = df_stats["date"].dt.year.max()
    date_min = min(df_stats["date"].min(), df_stat_prior["date"].min(), df_suc["date"].min())
    date_max = max(df_stats["date"].max(), df_stat_prior["date"].max(), df_suc["date"].max())
    dates = [date_min, date_max]

    # Mapping titres mis à jour
    titles_map = {
        "exp_shifted": "Shifted Exponential",
        "ig": "Inverse Gaussian",
        "ig_shifted": "Shifted Inverse Gaussian",
    }
    titre = titles_map.get(distribution, distribution)

    fig = plt.figure(figsize=(14, 6))

    # Bande ± écart-type
    plt.fill_between(dates, [median - std, median - std], [median + std, median + std],
                     color="grey", alpha=0.3)
    plt.plot(dates, [median, median], color="grey", linewidth=2)

    # Points rouges = "In Chronicle"
    plt.errorbar(
        df_stat_prior["date"],
        df_stat_prior["median_mean"],
        yerr=df_stat_prior["median_std"],
        fmt="o",
        color="red",
        ecolor="red",
        elinewidth=2,
        capsize=5,
        markersize=15
    )

    # Points bleus = df_suc
    plt.errorbar(
        df_suc["date"],
        df_suc["median_mean"],
        yerr=df_suc["median_std"],
        fmt="o",
        color="blue",
        ecolor="blue",
        elinewidth=2,
        capsize=5,
        markersize=15
    )

    # Légende mise à jour
    handles = [
        plt.Rectangle(
            (0, 0), 1, 1,
            color="grey",
            alpha=0.3,
            label=f"p$_{{series}}$"
        ),
        plt.Line2D(
            [0], [0],
            color="red",
            marker="o",
            linestyle="None",
            label="p$_{constrained}$"
        ),
        plt.Line2D(
            [0], [0],
            color="blue",
            marker="o",
            linestyle="None",
            label="p$_{independent}$"
        ),
    ]
    plt.xlabel("Date",fontsize=plt.rcParams["axes.titlesize"]+10)
    plt.ylabel("Median years",fontsize=plt.rcParams["axes.titlesize"]+10)
    plt.title(f"{titre} - {puits}", fontweight="bold",fontsize=plt.rcParams["figure.titlesize"]+4)

    plt.legend(
        handles=handles,
        loc="best",
        frameon=False,
        fontsize=plt.rcParams["legend.fontsize"]+10,
        markerscale=2.1   # ✅ Agrandit les symboles dans la légende
    )
        
    plt.grid(True, alpha=0.4)
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_linewidth(3)  # tu peux mettre 3 ou 4 si tu veux encore plus épais
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))     # ✅ Limite à 4 graduations
    ax.xaxis.set_major_formatter(DateFormatter('%Y'))    # ✅ Affiche uniquement l’année
    ax.tick_params(axis="both", labelsize=plt.rcParams["xtick.labelsize"]+10)
    # Axe Y : max 4 ticks
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    plt.tight_layout()

    # Sauvegarde éventuelle
    if save_path is not None:
        fig.savefig(save_path, dpi=300)

    if use_multiprocessing==False: 
        plt.show()
    plt.close(fig) 


def tracer_concentrations(
    df_conc_all,
    gaz_mod,
    layout="colonne",
    gaz_prior=None,
    n_curves=5,
    prior_years=None,
    df_conc_red=None,
    result_dir=None,
    gaz_suc=None,
    with_atm_ref=False,
    distribution=None,
    puits=None,
    use_multiprocessing=False, 
    plt_models=True
):
    # ✅ Mapping du titre comme dans tracer_stat
    titles_map = {
        "exp_shifted": "Shifted Exponential",
        "ig": "Inverse Gaussian",
        "ig_shifted": "Shifted Inverse Gaussian",
    }
    titre = titles_map.get(distribution, distribution)

    traceurs = df_conc_all["element"].unique()

    # Layout
    if layout == "ligne":
        fig, axes = plt.subplots(1, len(traceurs), figsize=(6 * len(traceurs), 5), sharey=False)
    else:
        fig, axes = plt.subplots(len(traceurs), 1, figsize=(8, 4 * len(traceurs)), sharex=True)

    # ✅ Titre global
    if distribution is not None and puits is not None:
        fig.suptitle(f"{titre} - {puits}", fontweight="bold", fontsize=plt.rcParams["axes.titlesize"])

    if len(traceurs) == 1:
        axes = [axes]

    mid_idx = len(axes) // 2

    if gaz_mod != None: 
        max_date = max([df_conc_all["date"].max()] + [df.index.max() for df in gaz_mod.values()])
    else: 
        max_date = [df_conc_all["date"].max()]

    # Optionnel : références atmosphériques
    chroniques_ref = {}
    if with_atm_ref:
        tracer_dir = Path(r"D:\codes\pyage\sources\tracer_data")
        for name in ["cfc11", "cfc12", "cfc113"]:
            try:
                tr = Tracer(tracer_dir, name=name)
                date = np.linspace(tr.datemin, tr.datemax, 1000)
                time = tr.datemax - date
                conc = tr.get_concentration(date, time)
                chroniques_ref[name.upper()] = (date, conc)
            except Exception as e:
                print(f"⚠️ Impossible de charger la chronique {name}: {e}")

    def _fmt_years_tuple(yrs, fallback_min=None, fallback_max=None):
        if yrs is not None:
            debut, fin = yrs
            try:
                debut_i = int(debut)
                fin_i = int(fin)
                return f"({debut_i})" if debut_i == fin_i else f"({debut_i}–{fin_i})"
            except Exception:
                pass
        if fallback_min is not None and fallback_max is not None:
            try:
                fmin = int(fallback_min)
                fmax = int(fallback_max)
                return f"({fmin})" if fmin == fmax else f"({fmin}–{fmax})"
            except Exception:
                pass
        return ""

    for i, (ax, traceur) in enumerate(zip(axes, traceurs)):
        # Enveloppe calibrée
        if (traceur in gaz_mod) and (plt_models == True):
            cmod.tracer_enveloppe(ax, gaz_mod[traceur], traceur, color="#606060", alpha=0.5)

        # SUC (rouge)
        df_suc = None
        if gaz_suc is not None and traceur in gaz_suc:
            df_suc = gaz_suc[traceur]
            cols = df_suc.columns
            if n_curves is not None and n_curves < len(cols):
                step = max(1, len(cols) // n_curves)
                cols = cols[::step]
            for col in cols:
                ax.plot(df_suc.index, df_suc[col], lw=1.5, alpha=0.8, color="red")

        # PRIOR (bleu)
        df_prior = None
        if gaz_prior is not None and traceur in gaz_prior:
            df_prior = gaz_prior[traceur]
            cols = df_prior.columns
            if n_curves is not None and n_curves < len(cols):
                step = max(1, len(cols) // n_curves)
                cols = cols[::step]
            for col in cols:
                ax.plot(df_prior.index, df_prior[col], lw=1.5, alpha=0.8, color="blue")

        # Données expérimentales (noir)
        data = df_conc_all[df_conc_all["element"] == traceur]
        ax.errorbar(
            data["date"], data["concentration"],
            yerr=0.2 * data["concentration"],
            fmt="o", capsize=4, color="black", markersize=10, zorder=5,
        )

        # Points rouges spécifiques
        if df_conc_red is not None:
            data_red = df_conc_red[df_conc_red["element"] == traceur]
            ax.errorbar(
                data_red["date"], data_red["concentration"],
                yerr=0.2 * data_red["concentration"],
                fmt="o", capsize=4, color="red", markersize=10, zorder=10,
            )

        # Références atmosphériques
        if with_atm_ref and traceur.upper() in chroniques_ref:
            date_ref, conc_ref = chroniques_ref[traceur.upper()]
            ax.plot(date_ref, conc_ref, "k--", lw=1.5, alpha=0.8, label=f"{traceur} atm.")

        ax.set_xlabel("Date")
        ax.set_ylabel(f"{traceur} (pptv)")
        ax.xaxis.set_major_locator(plt.MaxNLocator(6))
        ax.yaxis.set_major_locator(plt.MaxNLocator(4))
        ax.set_xlim(left=1960, right=max_date + 2.5)
        ax.xaxis.set_major_locator(plt.MaxNLocator(6))
        ax.tick_params(axis="both")

        # ✅ LÉGENDE restaurée
        if i == mid_idx:
            handles = [
                plt.Line2D([0], [0], color="black", marker="o", linestyle="None", label="Data"),
            ]
            data_min, data_max = int(data["date"].min()), int(data["date"].max())
            if plt_models == True: 
                handles.append(
                    plt.Rectangle(
                        (0, 0), 1, 1, color="darkgrey", alpha=0.9,
                        # label=f"p$_{{series}}$ ${{{data_min}–{data_max}}}$"
                        label=f"p$_{{series}}$"
                    )
                )

            if df_suc is not None:
                label_years = _fmt_years_tuple(
                    prior_years,
                    fallback_min=(int(df_suc.index.min()) if df_suc is not None else None),
                    fallback_max=(int(df_suc.index.max()) if df_suc is not None else None),
                )
                handles.append(plt.Line2D([0], [0], color="blue", lw=1,
                                          # label=f"p$_{{constrained}}$ {label_years}".strip()))
                                          label=f"p$_{{constrained}}$".strip()))

            if df_prior is not None:
                label_years = _fmt_years_tuple(
                    prior_years,
                    fallback_min=(int(df_prior.index.min()) if df_prior is not None else None),
                    fallback_max=(int(df_prior.index.max()) if df_prior is not None else None),
                )
                handles.append(plt.Line2D([0], [0], color="red", lw=1,
                                          # label=f"p$_{{independent}}$ {label_years}".strip()))
                                          label=f"p$_{{independent}}$".strip()))

            if with_atm_ref and traceur.upper() in chroniques_ref:
                handles.append(plt.Line2D([0], [0], color="black", ls="--", lw=1.2,
                                          label="Atmospheric ref."))

            ax.legend(handles=handles, loc="upper left", frameon=False)

    plt.tight_layout()

    # ✅ SAUVEGARDE + RETOUR
    saved_file = None
    if result_dir is not None:
        result_dir = Path(result_dir)
        result_dir.mkdir(parents=True, exist_ok=True)

        idx = 1
        while (result_dir / f"figure_{idx:03d}.png").exists():
            idx += 1

        out_file = result_dir / f"figure_{idx:03d}.png"
        fig.savefig(out_file, dpi=300)
        saved_file = out_file

    if use_multiprocessing == False: 
        plt.show()
    plt.close(fig) 
    return saved_file


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
    annee_fin=None,
    distribution=None
):
    """
    Charge les données (calibrées ou prior) selon le mode choisi
    et ajoute le chargement des paramètres de simulation.

    Paramètres
    ----------
    df : DataFrame
        DataFrame des répertoires construits par fold.construire_dataframe.
    mode : {"calib", "prior"}
        - "calib" → répertoire avec durée max
        - "prior" → répertoire filtré par critères
    distribution : str, optionnel
        Nom de la distribution (utile pour localiser le sous-dossier Metropolis_Hastings).

    Retour
    ------
    tuple :
        - Si mode="calib" → (df_conc, df_mod, gaz_mod, simul_param)
        - Si mode="prior" → (df_mod, gaz_mod, simul_param)
    """
    if df is None or df.empty:
        raise ValueError(
            "⚠️ ERREUR : le DataFrame fourni à charger_donnees est vide.\n"
            f"  - mode        : {mode}\n"
            f"  - base_type   : {base_type}\n"
            f"  - prior       : {prior}\n"
            f"  - submode     : {submode}\n"
            f"  - annee_debut : {annee_debut}\n"
            f"  - annee_fin   : {annee_fin}\n"
            f"  - distribution: {distribution}\n"
        )

    if mode == "calib":
        df_all = fold.trouver_repertoires_df(df, duree_max=True, afficher=False)
        if df_all.empty:
            raise ValueError(
                f"⚠️ Aucun répertoire trouvé en mode 'calib'. "
                f"DataFrame initial contenait {len(df)} lignes."
            )
        dossier_cible = df_all.iloc[0]["chemin"]

        # Charger données principales
        df_conc = cobs.charger_concentrations(dossier_cible)
        df_mod, gaz_mod = cmod.charger_concentrations(dossier_cible)

        # Charger paramètres de simulation
        mh_dir = os.path.join(dossier_cible, "Metropolis_Hastings")
        param_file = os.path.join(mh_dir, "parameters_calibration.txt")
        result_file = os.path.join(mh_dir, "results_calibration.txt")
        simul_param = fold.charger_plusieurs_kv_df(param_file, result_file)

        return df_conc, df_mod, gaz_mod, simul_param

    elif mode == "prior":
        criteres = {
            "base_type": base_type,
            "prior": prior,
            "mode": submode,
        }
        if annee_debut is not None:
            criteres["annee_debut"] = annee_debut
        if annee_fin is not None:
            criteres["annee_fin"] = annee_fin

        df_year_prior = fold.trouver_repertoires_df(df, criteres=criteres, afficher=False)
        if df_year_prior.empty:
            raise ValueError(
                f"⚠️ Aucun répertoire trouvé en mode 'prior' avec critères : {criteres}. "
                f"DataFrame initial contenait {len(df)} lignes."
            )
        dossier_cible = df_year_prior.iloc[0]["chemin"]

        # Charger données principales
        df_mod, gaz_mod = cmod.charger_concentrations(dossier_cible)

        # Charger paramètres de simulation
        mh_dir = os.path.join(dossier_cible, "Metropolis_Hastings")
        param_file = os.path.join(mh_dir, "parameters_calibration.txt")
        result_file = os.path.join(mh_dir, "results_calibration.txt")
        simul_param = fold.charger_plusieurs_kv_df(param_file, result_file)

        return df_mod, gaz_mod, simul_param

    else:
        raise ValueError("mode doit être 'calib' ou 'prior'")


def charger_statistiques(
    df,
    distribution,
    mode="calib",
    base_type=None,
    prior=None,
    submode=None,
    annee_debut=None,
    annee_fin=None, 
    dossier=None
):
    """
    Charge les statistiques (quantiles) associées à une distribution.

    Paramètres
    ----------
    df : DataFrame
        DataFrame des répertoires construits par fold.construire_dataframe.
    distribution : str
        Nom de la distribution (utilisé pour retrouver le fichier
        "<distribution>_stats_quantiles.txt").
    mode : {"calib", "prior", "suc"}
        - "calib" → répertoire avec durée max
        - "prior" → répertoire filtré par critères
        - "suc"   → répertoire fourni explicitement
    base_type, prior, submode, annee_debut, annee_fin : str ou int
        Critères utilisés uniquement si mode="prior".

    Retour
    ------
    DataFrame :
        Contenu du fichier de statistiques quantiles.
    """
    # ✅ Vérification du DataFrame en entrée (sauf si mode="suc")
    if mode != "suc" and (df is None or df.empty):
        # Forcer pandas à tout afficher dans les messages d’erreur
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", None)
        pd.set_option("display.max_colwidth", None)
        raise ValueError(
            "⚠️ ERREUR : le DataFrame fourni à charger_statistiques est vide.\n"
            "Détails des paramètres d'entrée :\n"
            f"  - mode        : {mode}\n"
            f"  - distribution: {distribution}\n"
            f"  - base_type   : {base_type}\n"
            f"  - prior       : {prior}\n"
            f"  - submode     : {submode}\n"
            f"  - annee_debut : {annee_debut}\n"
            f"  - annee_fin   : {annee_fin}\n"
            f"  - dossier     : {dossier}\n"
        )

    if mode == "calib":
        df_all = fold.trouver_repertoires_df(df, duree_max=True, afficher=False)
        if df_all.empty:
            raise ValueError(
                f"⚠️ Aucun répertoire trouvé en mode 'calib'.\n"
                f"DataFrame initial contenait {len(df)} lignes."
            )
        dossier_cible = df_all.iloc[0]["chemin"]

    elif mode == "prior":
        criteres = {
            "base_type": base_type,
            "prior": prior,
            "mode": submode,
        }
        if annee_debut is not None:
            criteres["annee_debut"] = annee_debut
        if annee_fin is not None:
            criteres["annee_fin"] = annee_fin

        df_year_prior = fold.trouver_repertoires_df(df, criteres=criteres, afficher=False)
        if df_year_prior.empty:
            raise ValueError(
                f"⚠️ Aucun répertoire trouvé en mode 'prior' avec les critères : {criteres}\n"
                f"DataFrame initial contenait {len(df)} lignes."
            )
        dossier_cible = df_year_prior.iloc[0]["chemin"]

    elif mode == "suc":
        if dossier is None:
            raise ValueError("⚠️ En mode 'suc', le paramètre 'dossier' doit être fourni.")
        dossier_cible = dossier

    else:
        raise ValueError("mode doit être 'calib', 'prior' ou 'suc'")

    # Remonter deux niveaux au-dessus
    dossier_parent = os.path.dirname(os.path.dirname(dossier_cible))

    # Construire le chemin vers le fichier
    fichier_stats = os.path.join(dossier_parent, distribution + "_stats_quantiles.txt")

    # Vérifier existence du fichier
    if not os.path.exists(fichier_stats):
        raise FileNotFoundError(
            f"⚠️ Fichier introuvable : {fichier_stats}\n"
            f"(répertoire cible : {dossier_cible})"
        )

    # Charger en DataFrame
    df_stats = pd.read_csv(fichier_stats, sep=None, engine="python")

    # Vérifier si vide
    if df_stats.empty:
        raise ValueError(
            f"⚠️ Le fichier de statistiques {fichier_stats} est vide."
        )


    return df_stats



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
        ("suc", "prior", "simple"): ("span", "prior", "simple"),
    }

    return mapping.get((base_type, prior_flag, submode), (base_type, prior_flag, submode))


def analyser_puits_distribution(
    dossier, puits, distribution,
    base_type="suc", prior_flag="prior", submode="double",
    tracer_global=True, tracer_subset=True,
    layout="colonne", n_curves=20, use_multiprocessing=False
):
    """
    Pipeline complet pour un puits + une distribution.
    Retourne :
      - un DataFrame concaténé regroupant uniquement les statistiques "all" et "prior"
        (les "suc" sont tracées mais non sauvegardées dans le concat final).
    """
    # Application du mapping conditionnel
    base_type_cond, prior_flag_cond, submode_cond = map_conditionnement(
        base_type, prior_flag, submode
    )

    # Recherche des répertoires
    folders = fold.trouver_repertoires(dossier, [puits, distribution])
    df = fold.construire_dataframe(folders)

    # Données calibrées globales
    df_conc_all, df_mod_all, gaz_mod_all, simul_param_all = charger_donnees(df, mode="calib")
    df_stat_all = charger_statistiques(df, distribution, mode="calib")

    result_dir = fold.make_subdirs(dossier, f"postproc_{submode}", puits, distribution)

    fichiers_video = []
    df_concat_list = []

    # --- CASE ALL ---
    if df_stat_all is not None and not df_stat_all.empty:
        df_tmp = df_stat_all.copy()
        df_tmp["type"] = "all"
        if simul_param_all is not None and not simul_param_all.empty:
            for col in simul_param_all.columns:
                df_tmp[col] = simul_param_all.iloc[0][col]
        df_concat_list.append(df_tmp)

    # --- CASE GLOBAL PRIOR ---
    df_stat_prior = None
    if tracer_global:
        df_prior_all, gaz_prior_all, simul_param_prior = charger_donnees(
            df, mode="prior", base_type=base_type, prior=prior_flag, submode=submode
        )

        fichier = tracer_concentrations(
            df_conc_all, gaz_mod_all,
            layout=layout, gaz_prior=None, n_curves=n_curves,
            prior_years=None, df_conc_red=None,
            result_dir=result_dir, distribution=None, puits=puits,
            with_atm_ref=True,
            use_multiprocessing=use_multiprocessing, 
            plt_models=False
        )

        fichier = tracer_concentrations(
            df_conc_all, gaz_mod_all,
            layout=layout, gaz_prior=None, n_curves=n_curves,
            prior_years=None, df_conc_red=None,
            result_dir=result_dir, distribution=distribution, puits=puits,
            use_multiprocessing=use_multiprocessing
        )
        if fichier:
            fichiers_video.append(str(fichier))

        df_stat_prior = charger_statistiques(
            df, distribution=distribution, mode="prior",
            base_type=base_type, prior=prior_flag, submode=submode
        )

        if df_stat_prior is not None and not df_stat_prior.empty:
            df_tmp = df_stat_prior.copy()
            df_tmp["type"] = "prior"
            if simul_param_prior is not None and not simul_param_prior.empty:
                for col in simul_param_prior.columns:
                    df_tmp[col] = simul_param_prior.iloc[0][col]
            df_concat_list.append(df_tmp)

    # --- CASE SUBSET ---
    if tracer_subset:
        df_subset = fold.trouver_sauf_annees(
            df, base_type=base_type, prior=prior_flag, submode=submode, afficher=False
        )

        df_stat_suc_all = []

        for _, row in df_subset.iterrows():
            dossier_cible = row["chemin"]
            prior_years = (row["annee_debut"], row["annee_fin"])
            df_conc_red = cobs.charger_concentrations(dossier_cible)

            param_file = os.path.join(dossier_cible, "Metropolis_Hastings", "parameters_calibration.txt")
            result_file = os.path.join(dossier_cible, "Metropolis_Hastings", "results_calibration.txt")
            simul_param = fold.charger_plusieurs_kv_df(param_file, result_file)

            try:
                df_prior_all, gaz_prior_all = cmod.charger_concentrations(dossier_cible)
            except Exception:
                df_prior_all, gaz_prior_all = None, None

            exist_suc, dossier_suc = fold.corresp_folder_suc(dossier_cible, distribution)
            df_suc, gaz_suc = (None, None)
            if exist_suc >= 0:
                try:
                    df_suc, gaz_suc = cmod.charger_concentrations(dossier_suc)
                except Exception as e:
                    print(f"⚠️ Erreur chargement concentrations depuis {dossier_cible} : {e}")

            # Tracé
            fichier = tracer_concentrations(
                df_conc_all, gaz_mod_all,
                layout=layout, gaz_prior=gaz_prior_all, n_curves=n_curves,
                prior_years=prior_years, df_conc_red=df_conc_red,
                result_dir=result_dir, gaz_suc=gaz_suc,
                distribution=distribution, puits=puits,
                use_multiprocessing=use_multiprocessing, 
                plt_models=True
            )
            if fichier:
                fichiers_video.append(str(fichier))

            # Stats suc uniquement pour tracer_stat (⚠️ pas ajouté dans df_concat_list)
            df_stat_suc_local = charger_statistiques(
                pd.DataFrame([row]),
                distribution=distribution,
                mode="suc",
                base_type=base_type,
                prior=prior_flag,
                submode=submode,
                dossier=dossier_suc
            )
            if df_stat_suc_local is not None and not df_stat_suc_local.empty:
                df_stat_suc_local["type"] = "suc"
                df_stat_suc_all.append(df_stat_suc_local)

        df_stat_suc = pd.concat(df_stat_suc_all, ignore_index=True) if df_stat_suc_all else None

        tracer_stat(
            df_stat_all, df_stat_prior, df_stat_suc,
            distribution, puits, save_path=result_dir,
            use_multiprocessing=use_multiprocessing
        )

    if fichiers_video:
        try:
            fold.make_video_from_figures(fichiers_video, "concentrations_video.mp4", fps=1)
        except (MemoryError, OSError, Exception) as e:
            print(f"[AVERTISSEMENT] Vidéo non générée pour cause d'erreur : {e}")
    else:
        print("⚠️ Aucun fichier généré, pas de vidéo.")

    df_concat = None
    if df_concat_list:
        df_concat = pd.concat(df_concat_list, ignore_index=True)

    return df_concat




# ======================
# MAIN
# ======================

def run_case(args):
    dossier, puits, distribution, base_type, prior_flag, submode, erreur, use_multiprocessing = args
    print(f"=== Analyse {puits} | {distribution} | erreur={erreur} ===")
    
    df_res = analyser_puits_distribution(
        dossier, puits, distribution,
        base_type=base_type,
        prior_flag=prior_flag,
        submode=submode,
        tracer_global=True,
        tracer_subset=True,
        layout="ligne",
        n_curves=20,
        use_multiprocessing=use_multiprocessing
    )

    # ✅ La clé contient désormais aussi "erreur"
    return (puits, distribution, erreur), df_res


def format_err(val: float) -> str:
    n = round(val * 100)
    if n % 10 == 0:  # multiple de 0.1
        return f"err{n // 10:02d}"  # 2 chiffres
    else:
        return f"err{n:03d}"        # 3 chiffres


if __name__ == "__main__":

    # ===========================================
    # 🔽 CHOISIR LE CAS À TESTER ICI 🔽
    option_case = 41  # ← mettre 1, 2 ou 3
    # ===========================================

    if option_case == 1:
        # --- Option 1 ---
        # Pour la date du 2025-09-28: simulations raisonnables (20 000)
        valeurs = [0.2, 0.3, 0.4]  # ordre spécifique
        date = "2025-09-28"
        puits_list = ["F11","F09","F34","PE","MF1","MF4","F38"]
        distributions_list = ["exp_shifted", "ig", "ig_shifted"]
        result_scope=""
        submode = "double"

    elif option_case == 2:
        # --- Option 2 ---
        # Pour la date du 2025-10-01: simulations longues /5
        valeurs = [0.2, 0.3, 0.4]
        date = "2025-10-01"
        puits_list = ["F11","F09","F34","PE","MF1","MF4","F38"]
        distributions_list = ["exp_shifted", "ig_shifted"]
        result_scope=""
        submode = "double"

    elif option_case == 31 or option_case == 32:
        # --- Option 3 ---
        # Pour la date du 2025-10-02
        valeurs = [0.1, 0.2, 0.3, 0.4]
        date = "2025-10-02"
        puits_list = ["F11","F09","F34","PE","MF1","MF4","F38b","F38","PZ2","PSR1"]
        distributions_list = ["exp_shifted","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"]
        # distributions_list = ["exp_shifted","ig_shifted","ig","gamma","uniform"]
        result_scope="all"
        if option_case == 31: 
            submode = "double"
        elif option_case == 32: 
            submode = "simple"

    elif option_case == 41 or option_case == 42:
        # --- Option 3 ---
        # Pour la date du 2025-10-02
        valeurs = [0.1, 0.2, 0.3, 0.4]
        # valeurs = [0.1]
        # valeurs = [0.3]
        date = "2025-10-02"
        puits_list = ["F11","F09","F34","PE","MF1","MF4","F38"]
        # puits_list = ["F38"]
        # distributions_list = ["exp_shifted","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"]
        distributions_list = ["exp_shifted","ig_shifted"]
        # distributions_list = ["exp_shifted"]
        result_scope="ploemeur_es"
        if option_case == 41: 
            submode = "double"
        elif option_case == 42: 
            submode = "simple"

    else:
        raise ValueError(f"Option inconnue : {option_case}")

    # Génération automatique des chemins
    dossiers_list = [
        (gp.ROOT_DIRECTORY_RESULTS / Path(f"{date}, {format_err(val)}"), val)
        for val in valeurs
    ]
    
    print("📂 Liste des dossiers générés :")
    for dossier, val in dossiers_list:
        print(f" - {dossier} (val={val})")

    # --- Options globales ---
    base_type = "suc"
    prior_flag = "prior"

    # --- Paramètre global ---
    use_multiprocessing = True

    # ✅ Générer toutes les combinaisons AVEC l'erreur
    combos = [
        (dossier, puits, distribution, base_type, prior_flag, submode, erreur, use_multiprocessing)
        for (dossier, erreur) in dossiers_list
        for puits in puits_list
        for distribution in distributions_list
    ]

    print("Exécution séquentielle" if not use_multiprocessing else "Exécution parallèle")
    
    if use_multiprocessing:
        n_cores = mp.cpu_count()
        print(f"Utilisation de {n_cores} cœurs en parallèle")
        with mp.Pool(processes=n_cores) as pool:
            results_list = pool.map(run_case, combos)
    else:
        results_list = [run_case(args) for args in combos]

    # ✅ Stockage séparé dans deux dictionnaires
    resultats_df = {
        (puits, distribution, erreur): df
        for (puits, distribution, erreur), df in results_list
    }

    # ✅ Concaténation DataFrames statistiques
    df_global = []
    for (puits, distribution, erreur), df in resultats_df.items():
        if df is not None and not df.empty:
            df = df.copy()
            df["puits"] = puits
            df["distribution"] = distribution
            df["erreur"] = erreur
            df_global.append(df)

    if df_global:
        df_global = pd.concat(df_global, ignore_index=True)
        output_file = build_output_filepath( date, result_scope, submode)
        df_global.to_csv(output_file, index=False)
        df_test = pd.read_csv(output_file)
        print(f"✅ Stats sauvegardées : {df_test.shape[0]} lignes")
    else:
        print("\n⚠️ Aucun DataFrame valide à concaténer (stats).")


        
    # Génération des figures finales
    generer_toutes_les_figures(output_file, date, result_scope, submode)
    print(output_file, date, result_scope)

