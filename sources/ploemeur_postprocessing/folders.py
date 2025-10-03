import os
from pathlib import Path
import re
import pandas as pd
import imageio.v2 as imageio



def corresp_folder_suc(base_path, distribution=None):
    """
    Corrige le chemin cible en supprimant '_apriori_double' et '_prior'
    et renvoie le chemin du sous-dossier avec puits horodaté et distribution.

    Retourne (status, path):
      0 = trouvé normalement (unique ou sélection claire)
      1 = plusieurs résultats, distribution préférée (shifted vs non-shifted) choisie
      2 = plusieurs résultats, préférence introuvable, premier pris
     -1 = aucun résultat trouvé
    """
    base_path = Path(base_path)

    # Morceaux du chemin d'entrée
    dist_in = (distribution or base_path.name)   # p.ex. "ig" ou "ig_shifted"
    base = dist_in.replace("_shifted", "")       # base "ig"
    dist_shifted = f"{base}_shifted"             # "ig_shifted"
    dist_plain = base                            # "ig"

    puits_horodate = base_path.parent.name       # "F11_2004_2005"
    run_dir = base_path.parent.parent.name       # "2025_09_28-18_15_17"
    scenario_dir = base_path.parents[2].name     # "ploemeur_apriori_double_0.3suc_prior"
    root_dir = base_path.parents[3]              # "D:/results/PyAge/2025-09-28, err03"

    # Nom de scénario nettoyé
    scenario_clean = scenario_dir.replace("_apriori_double", "").replace("_prior", "")

    # On se limite au run courant pour éviter les collisions entre runs
    search_root = root_dir / scenario_clean / run_dir

    # On cherche tous les dossiers qui contiennent *exactement* le puits horodaté
    # (fonction supposée faire une correspondance exacte sur les parties de chemin)
    folders = trouver_repertoires(root_dir / scenario_clean, [puits_horodate])

    if not folders:
        print(f"❌ Aucun dossier trouvé pour {puits_horodate} dans {search_root}")
        return -1, None

    # Convertir en Path et ne garder que les dossiers au niveau distribution (dernier segment)
    candidates = [Path(f) for f in folders if Path(f).name in {dist_shifted, dist_plain}]

    # S’il n’y a pas de candidats stricts, on garde tous les folders trouvés (fallback)
    if not candidates:
        # Fallback: tout ce qui matche le puits dans ce run, on choisit le premier
        # print(f"⚠️ Aucun dossier {dist_plain} ou {dist_shifted} trouvé sous {puits_horodate}.")
        # print("→ Utilisation du premier candidat :", folders[0])
        return 2, Path(folders[0])

    # Préférence : shifted > plain
    exact_shifted = [p for p in candidates if p.name == dist_shifted]
    if exact_shifted:
        if len(candidates) > 1:
            # print(f"ℹ️ Plusieurs dossiers trouvés, préférence pour '{dist_shifted}': {exact_shifted[0]}")
            return 1, exact_shifted[0]
        return 0, exact_shifted[0]

    exact_plain = [p for p in candidates if p.name == dist_plain]
    if exact_plain:
        if len(candidates) > 1:
            print(f"ℹ️ Plusieurs dossiers trouvés, préférence pour '{dist_plain}': {exact_plain[0]}")
            return 1, exact_plain[0]
        return 0, exact_plain[0]

    # Dernier fallback: premier candidat
    print("⚠️ Préférences introuvables, utilisation du premier candidat :", candidates[0])
    return 2, candidates[0]




def make_video_from_figures(fichiers, output_name="video.mp4", fps=1, format="FFMPEG"):
    """
    Assemble les images listées dans `fichiers` en une vidéo.
    Chaque image reste affichée 1s (fps=1).
    """
    if not fichiers:
        print("⚠️ Aucun fichier image fourni")
        return None

    # On déduit le dossier de sortie depuis le premier fichier
    result_dir = Path(fichiers[0]).parent
    out_path = result_dir / output_name

    with imageio.get_writer(
        out_path,
        fps=fps,
        format=format,
        codec="libx264",
        ffmpeg_log_level="quiet"
    ) as writer:
        for img_path in fichiers:
            img_path = Path(img_path)
            if img_path.is_file():
                writer.append_data(imageio.imread(img_path))
            else:
                print(f"⚠️ Fichier introuvable : {img_path}")

    return out_path



def make_subdirs(root, *subdirs):
    """
    Crée une arborescence de sous-dossiers sous root.
    
    Exemple:
        make_subdirs("C:/tmp", "puits", "distribution", "postproc", "dossier")
        -> C:/tmp/puits/distribution/postproc/dossier
    """
    root = Path(root)
    path = root.joinpath(*subdirs)
    path.mkdir(parents=True, exist_ok=True)
    return path


def racine_et_suffixes(base_dir):
    """
    Cherche la chaîne commune (racine) entre les sous-répertoires immédiats
    de base_dir (en excluant 'prior_distributions') et retourne
    la racine + la liste des suffixes.
    """
    repertoires = [
        d for d in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, d)) and d != "prior_distributions"
    ]

    if not repertoires:
        return "", []

    racine = os.path.commonprefix(repertoires)
    suffixes = [d[len(racine):] for d in repertoires]

    return racine, suffixes


def trouver_repertoires(base_dir, motifs):
    """
    Parcourt récursivement tous les sous-répertoires de base_dir
    et retourne la liste des chemins complets des répertoires qui :
      - contiennent toutes les chaînes de 'motifs' dans leur chemin
      - ne se terminent pas par 'Metropolis_Hastings'
      - apparaissent une seule fois (unicité)
    """
    base_dir = Path(base_dir)
    resultats = set()

    for d in base_dir.rglob("*"):
        if d.is_dir():
            chemin_str = str(d)
            if all(m in chemin_str for m in motifs):
                if not chemin_str.endswith("Metropolis_Hastings"):
                    resultats.add(chemin_str)

    resultats = sorted(resultats)

    if not resultats:
        raise FileNotFoundError(
            f"⚠️  Aucun répertoire trouvé.\n"
            f"Base_dir : {base_dir}\n"
            f"Motifs   : {motifs}"
        )

    return resultats


def parser_chemin(chemin):
    """
    Extrait les informations utiles à partir d’un chemin de simulation.
    """
    # Nom du dernier dossier
    nom_dossier = Path(chemin).name

    # Erreur + type
    m_err_type = re.search(r"(?P<err>\d+(?:\.\d+)?)(?P<type>(?:suc|span)[A-Za-z_]*)", chemin)
    erreur = float(m_err_type.group("err")) if m_err_type else None

    # Puits
    m_puits = re.search(r"(F\d+)", chemin)
    puits = m_puits.group(1) if m_puits else ""

    # Années
    m_annees = re.search(r"(?:F\d+|PE)_(\d{4})_(\d{4})", chemin)
    annee_debut, annee_fin = (int(m_annees.group(1)), int(m_annees.group(2))) if m_annees else (None, None)

    # Distribution
    distribution = "exp_shifted" if "exp_shifted" in chemin else ""

    # Mode
    if "simple" in chemin:
        mode = "simple"
    elif "double" in chemin:
        mode = "double"
    else:
        mode = ""

    # Base type
    if "suc" in chemin:
        base_type = "suc"
    elif "span" in chemin:
        base_type = "span"
    else:
        base_type = ""

    # Prior
    prior = "prior" if "prior" in chemin else ""

    return {
        "puits": puits,
        "annee_debut": annee_debut,
        "annee_fin": annee_fin,
        "erreur": erreur,
        "mode": mode,
        "base_type": base_type,
        "distribution": distribution,
        "prior": prior,
        "nom_dossier": nom_dossier,
        "chemin": chemin,
    }


def construire_dataframe(chemins):
    data = [parser_chemin(c) for c in chemins]
    df = pd.DataFrame(data)
    
    if df.empty:
        raise ValueError(
            f"⚠️  Sécurité : le DataFrame construit est vide !\n"
            f"Chemins analysés : {chemins}"
        )
    
    return df


def afficher_dataframe_aligne(df):
    """
    Affiche un DataFrame avec des colonnes ajustées à la taille du contenu
    (style tableau fixe en console).
    """
    # Détermination de la largeur max pour chaque colonne
    col_widths = {}
    for col in df.columns:
        max_content_len = df[col].astype(str).map(len).max()
        col_widths[col] = max(max_content_len, len(col))

    # Construire le header
    header = " | ".join(f"{col:<{col_widths[col]}}" for col in df.columns)
    print(header)
    print("-" * len(header))

    # Construire chaque ligne
    for _, row in df.iterrows():
        line = " | ".join(f"{str(val):<{col_widths[col]}}" for col, val in row.items())
        print(line)


def afficher_noms_repertoires(df):
    """
    Affiche uniquement la colonne 'chemin' du DataFrame.
    """
    if "nom_dossier" not in df.columns:
        print("⚠️ La colonne 'chemin' est absente du DataFrame.")
        return
    
    print("\n=== Noms des répertoires ===")
    for nom in df["chemin"]:
        print(nom)


def trouver_chemin_specifique(
    df, 
    base_type="suc", 
    prior="prior", 
    mode="double", 
    annee_debut=2007, 
    annee_fin=2010, 
    afficher=False
):
    """
    Trouve les lignes du DataFrame correspondant à des critères précis :
      - base_type (ex: 'suc' ou 'span')
      - prior (ex: 'prior' ou '')
      - mode (ex: 'simple', 'double' ou '')
      - annee_debut et annee_fin
    
    Retourne un sous-DataFrame contenant uniquement les lignes correspondantes.
    
    Paramètres
    ----------
    df : DataFrame
        Le DataFrame contenant les chemins.
    base_type : str
        Type de base ('suc' ou 'span').
    prior : str
        Indique si 'prior' doit être présent ('prior' ou '').
    mode : str
        Mode ('simple', 'double' ou '').
    annee_debut : int
        Année de début.
    annee_fin : int
        Année de fin.
    afficher : bool, optionnel (par défaut False)
        Si True, affiche le résultat avec `afficher_dataframe_aligne`.
    """
    masque = (
        (df["base_type"] == base_type) &
        (df["prior"] == prior) &
        (df["mode"] == mode) &
        (df["annee_debut"] == annee_debut) &
        (df["annee_fin"] == annee_fin)
    )
    
    result = df[masque]
    
    if afficher:
        print("\n=== Répertoires correspondant aux critères ===")
        afficher_dataframe_aligne(result)
    
    return result


def trouver_repertoires_df(df, criteres=None, duree_max=False, afficher=False):
    """
    Filtre un DataFrame de répertoires selon des critères précis
    ou selon la durée maximale (annee_fin - annee_debut).

    Paramètres
    ----------
    df : DataFrame
        Le DataFrame contenant les chemins.
    criteres : dict, optionnel
        Dictionnaire {colonne: valeur} pour filtrer (ex: {"base_type": "suc", "mode": "double"}).
        Ignoré si duree_max=True.
    duree_max : bool, optionnel
        Si True, retourne uniquement les lignes dont la durée est maximale.
    afficher : bool, optionnel
        Si True, affiche le résultat avec `afficher_dataframe_aligne`.

    Retour
    ------
    DataFrame filtré
    """
    result = df.copy()

    if duree_max:
        result["duree"] = result["annee_fin"] - result["annee_debut"]
        max_duree = result["duree"].max()
        result = result[result["duree"] == max_duree]

        if afficher:
            print(f"\nDurée maximale : {max_duree} ans")
            print("\n=== Répertoires avec la durée maximale ===")
            afficher_dataframe_aligne(result)

    elif criteres:
        masque = pd.Series(True, index=result.index)
        for col, val in criteres.items():
            masque &= result[col] == val
        result = result[masque]

        if afficher:
            print("\n=== Répertoires correspondant aux critères ===")
            afficher_dataframe_aligne(result)

    # 🚨 Contrôle d'erreur si vide
    if result.empty:
        raise ValueError(
            f"⚠️  Aucun répertoire trouvé dans le DataFrame.\n"
            f"Critères  : {criteres}\n"
            f"Duree_max : {duree_max}"
        )

    return result



def charger_lpm_dist(dossier_cible):
    """
    Cherche et charge le fichier Metropolis_Hastings/lpm_dist_calibrated.txt
    dans un répertoire donné.
    Retourne un DataFrame Pandas.
    """
    fichier = Path(dossier_cible) / "Metropolis_Hastings" / "lpm_dist_calibrated.txt"
    
    if not fichier.exists():
        raise FileNotFoundError(f"⚠️ Fichier introuvable : {fichier}")
    
    # Charger en DataFrame
    df = pd.read_csv(fichier, sep="\t")  # séparateur tabulation
    return df


def trouver_sauf_annees(
    df,
    base_type="suc",
    prior="prior",
    submode="double",
    afficher=False
):
    """
    Trouve les lignes du DataFrame correspondant à des critères donnés,
    en ignorant les valeurs de 'annee_debut' et 'annee_fin'.
    
    Paramètres
    ----------
    df : DataFrame
        Le DataFrame contenant les chemins et caractéristiques.
    base_type, prior, submode : str
        Critères de filtrage (ex: 'suc', 'prior', 'double').
    afficher : bool, optionnel
        Si True, affiche les résultats avec afficher_dataframe_aligne().
    
    Retour
    ------
    DataFrame
        Sous-ensemble de df contenant les lignes correspondant aux critères
        (quel que soit annee_debut et annee_fin).
    """
    masque = (
        (df["base_type"] == base_type) &
        (df["prior"] == prior) &
        (df["mode"] == submode)
    )

    result = df[masque]

    if afficher:
        print("\n=== Répertoires correspondant aux critères (sauf années) ===")
        afficher_dataframe_aligne(result)

    return result
