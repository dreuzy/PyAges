import os
from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
import multiprocessing as mp
import numpy as np

import global_parameters as gp
import ploemeur_postprocessing.folders as fold
import ploemeur_postprocessing.concentrations_obs as cobs
import ploemeur_postprocessing.concentrations_mod as cmod

from tracer.tracer_root import Tracer  # <-- ta classe Tracer
from appli_ploemeur_postprocessing_stat import generer_toutes_les_figures

# ✅ Styles globaux pour les figures (présentation/papier)
plt.rcParams.update({
    "figure.figsize": (12, 6),   # Taille par défaut des figures
    "axes.titlesize": 20,        # Taille des titres (plt.title ou ax.set_title)
    "axes.labelsize": 18,        # Taille des labels X/Y
    "xtick.labelsize": 16,       # Taille des ticks en X
    "ytick.labelsize": 16,       # Taille des ticks en Y
    "legend.fontsize": 16,       # Taille des légendes
})

def tracer_stat(df_stats, df_stat_prior, df_suc, distribution, puits, save_path=None):
    """
    Affiche :
    - une bande horizontale correspondant à la médiane ± écart-type
      en utilisant uniquement la ligne d'index 1 de df_stats ("Full Chronicle"),
    - les points issus de df_stat_prior ("In Chronicle") avec médiane ± écart-type en rouge,
    - les points issus de df_suc avec médiane ± écart-type en bleu.
    """

    # Extraire uniquement la ligne 1 de df_stats
    ligne = df_stats.iloc[1]
    median = ligne["median_mean"]
    std = ligne["median_std"]

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
        markersize=10
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
        markersize=10
    )

    # Légende mise à jour
    handles = [
        plt.Rectangle((0, 0), 1, 1, color="grey", alpha=0.3,
                      label=f"Full chronicle ({year_min_full}–{year_max_full})"),
        plt.Line2D([0], [0], color="red", marker="o", linestyle="None", label="In chronicle"),
        plt.Line2D([0], [0], color="blue", marker="o", linestyle="None", label="Independent"),
    ]
    plt.xlabel("Date")
    plt.ylabel("Median years")
    plt.title(f"{titre} - {puits}", fontweight="bold", fontsize=18)
    plt.legend(handles=handles, loc="upper left", frameon=False)
    plt.grid(True, alpha=0.4)
    plt.tight_layout()

    # Sauvegarde éventuelle
    if save_path is not None:
        fig.savefig(save_path, dpi=300)

    plt.show()


def tracer_concentrations(
    df_conc_all,
    gaz_mod,
    fontsize_labels=16,
    fontsize_ticks=14,
    layout="colonne",
    gaz_prior=None,
    n_curves=5,
    prior_years=None,
    df_conc_red=None,
    result_dir=None,
    gaz_suc=None,
    with_atm_ref=False,
    distribution=None,
    puits=None
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
        fig.suptitle(f"{titre} - {puits}", fontweight="bold", fontsize=18)

    if len(traceurs) == 1:
        axes = [axes]

    mid_idx = len(axes) // 2

    max_date = max([df_conc_all["date"].max()] + [df.index.max() for df in gaz_mod.values()])

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
        if traceur in gaz_mod:
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
            handles.append(
                plt.Rectangle(
                    (0, 0), 1, 1, color="darkgrey", alpha=0.9,
                    label=f"Full chronicle ({data_min}–{data_max})"
                )
            )

            if df_suc is not None:
                label_years = _fmt_years_tuple(
                    prior_years,
                    fallback_min=(int(df_suc.index.min()) if df_suc is not None else None),
                    fallback_max=(int(df_suc.index.max()) if df_suc is not None else None),
                )
                handles.append(plt.Line2D([0], [0], color="blue", lw=1,
                                          label=f"In chronicle {label_years}".strip()))

            if df_prior is not None:
                label_years = _fmt_years_tuple(
                    prior_years,
                    fallback_min=(int(df_prior.index.min()) if df_prior is not None else None),
                    fallback_max=(int(df_prior.index.max()) if df_prior is not None else None),
                )
                handles.append(plt.Line2D([0], [0], color="red", lw=1,
                                          label=f"Independent {label_years}".strip()))

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

    plt.show()
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
    mode : {"calib", "prior"}
        - "calib" → répertoire avec durée max
        - "prior" → répertoire filtré par critères
    base_type, prior, submode, annee_debut, annee_fin : str ou int
        Critères utilisés uniquement si mode="prior".

    Retour
    ------
    DataFrame :
        Contenu du fichier de statistiques quantiles.
    """
    if mode == "calib":
        df_all = fold.trouver_repertoires_df(df, duree_max=True, afficher=False)
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
        dossier_cible = df_year_prior.iloc[0]["chemin"]
    elif mode =="suc": 
        dossier_cible = dossier
    else:
        raise ValueError("mode doit être 'calib' ou 'prior'")

    # Remonter deux niveaux au-dessus
    dossier_parent = os.path.dirname(os.path.dirname(dossier_cible))

    # Construire le chemin vers le fichier
    fichier_stats = os.path.join(dossier_parent, distribution + "_stats_quantiles.txt")

    # Charger en DataFrame
    if not os.path.exists(fichier_stats):
        raise FileNotFoundError(f"Fichier introuvable : {fichier_stats}")

    # Pandas sait gérer automatiquement le séparateur si on met sep=None + engine="python"
    df_stats = pd.read_csv(fichier_stats, sep=None, engine="python")
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
    df_stat_all = charger_statistiques(df, distribution, mode="calib")

    # Répertoire de sortie
    result_dir = fold.make_subdirs(dossier, "postproc", puits, distribution)

    # ✅ Liste des figures sauvegardées
    fichiers_video = []

    # CAS 1 : GLOBAL
    if tracer_global:
        df_prior_all, gaz_prior_all = charger_donnees(
            df,
            mode="prior",
            base_type=base_type,
            prior=prior_flag,
            submode=submode,
        )

        fichier = tracer_concentrations(
            df_conc_all, gaz_mod_all,
            fontsize_labels=fontsize_labels,
            fontsize_ticks=fontsize_ticks,
            layout=layout,
            gaz_prior=None,   # prior global désactivé
            n_curves=n_curves,
            prior_years=None,
            df_conc_red=None,
            result_dir=result_dir, 
            distribution=distribution,
            puits=puits
        )

        if fichier:
            fichiers_video.append(str(fichier))

        df_stat_prior = charger_statistiques(
            df,
            distribution=distribution,
            mode="prior",
            base_type=base_type,
            prior=prior_flag,
            submode=submode,
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

            df_conc_red = cobs.charger_concentrations(dossier_cible)

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

            fichier = tracer_concentrations(
                df_conc_all, gaz_mod_all,
                fontsize_labels=fontsize_labels,
                fontsize_ticks=fontsize_ticks,
                layout=layout,
                gaz_prior=gaz_prior_all,
                n_curves=n_curves,
                prior_years=prior_years,
                df_conc_red=df_conc_red,
                result_dir=result_dir, 
                gaz_suc=gaz_suc, 
                distribution=distribution,
                puits=puits
            )

            if fichier:
                fichiers_video.append(str(fichier))

        df_stat_suc = charger_statistiques(
            df_subset,
            distribution=distribution,
            mode="suc",
            base_type=base_type,
            prior=prior_flag,
            submode=submode,
            dossier=dossier_suc
        )
        
        tracer_stat(
            df_stat_all, df_stat_prior, df_stat_suc,
            distribution, puits, save_path=result_dir
        )

    # ✅ Appel vidéo avec la liste de fichiers
    if fichiers_video:
        fold.make_video_from_figures(
            fichiers_video,
            "concentrations_video.mp4",
            fps=1
        )
    else:
        print("⚠️ Aucun fichier généré, pas de vidéo.")
    
    return df_stat_prior


# ======================
# MAIN
# ======================

def run_case(args):
    dossier, puits, distribution, base_type, prior_flag, submode, erreur = args
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
        fontsize_labels=16,
        fontsize_ticks=12
    )

    # ✅ La clé contient désormais aussi "erreur"
    return (puits, distribution, erreur), df_res


if __name__ == "__main__":
    # --- Données sources AVEC erreurs associées ---
    dossiers_list = [
        (Path(r"2025-09-28, err03"), 0.3),
        (Path(r"2025-09-28, err02"), 0.2),
        (Path(r"2025-09-28, err04"), 0.4)
    ]
    # dossiers_list = [
    #     (Path(r"2025-10-01, err03"), 0.3),
    #     (Path(r"2025-10-01, err02"), 0.2),
    #     (Path(r"2025-10-01, err04"), 0.4)
    # ]
    # dossiers_list = [
    #     (gp.ROOT_DIRECTORY_RESULTS / d, erreur)
    #     for (d, erreur) in dossiers_list
    # ]

    # --- Listes de cas à traiter ---
    puits_list = ["F09", "F11"]
    puits_list = ["F11","F09","F34","PE","MF1","MF4","F38"]#,"PZ2","PSR1"]
    # distributions_list = ["exp_shifted", "ig_shifted", "ig"]
    distributions_list = ["exp_shifted", "ig_shifted"]

    # --- Options globales ---
    base_type = "suc"
    prior_flag = "prior"
    submode = "double"

    # --- Paramètre global ---
    use_multiprocessing = False

    # ✅ Générer toutes les combinaisons AVEC l'erreur
    combos = [
        (dossier, puits, distribution, base_type, prior_flag, submode, erreur)
        for (dossier, erreur) in dossiers_list
        for puits in puits_list
        for distribution in distributions_list
    ]

    # ✅ Lancement des traitements
    print("Exécution séquentielle" if not use_multiprocessing else "Exécution parallèle")
    
    if use_multiprocessing:
        n_cores = mp.cpu_count()
        print(f"Utilisation de {n_cores} cœurs en parallèle")
        with mp.Pool(processes=n_cores) as pool:
            results_list = pool.map(run_case, combos)
    else:
        results_list = []
        for args in combos:
            result = run_case(args)
            results_list.append(result)

    # ✅ Stockage final dans un dictionnaire clé → DataFrame
    resultats_df = {
        (puits, distribution, erreur): df
        for (puits, distribution, erreur), df in results_list
    }

    print("\n✅ Résultats enregistrés :")
    for key in resultats_df:
        print(f" - {key}")

    # ✅ Concaténation dans un grand dataframe (avec clef en colonnes)
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
        
        # ✅ Sauvegarde dans un fichier CSV
        output_file = gp.ROOT_DIRECTORY_RESULTS / "resultats_global_large.csv"
        df_global.to_csv(output_file, index=False)
        print(f"\n✅ DataFrame global sauvegardé dans : {output_file}")

        # ✅ Relecture pour vérification
        df_test = pd.read_csv(output_file)
        print(f"✅ Test de lecture réussi : {df_test.shape[0]} lignes chargées")

    else:
        print("\n⚠️ Aucun DataFrame valide à concaténer.")
        
    generer_toutes_les_figures()

