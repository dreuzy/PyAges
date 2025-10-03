import os
from pathlib import Path
import re
import pandas as pd


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
    m_annees = re.search(r"F\d+_(\d{4})_(\d{4})", chemin)
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
    return pd.DataFrame(data)


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


# ================== MAIN ==================
if __name__ == "__main__":
    dossier = Path(r"C:\results\pyage\2025, février, v2")

    print("=== Racine commune des sous-répertoires immédiats ===")
    racine, suffixes = racine_et_suffixes(dossier)
    print("Chaîne racine commune :", repr(racine))
    print("Suffixes :", suffixes)

    print("\n=== Recherche récursive (motifs F11 + exp_shifted) ===")
    puits = "F11"
    distribution = "exp_shifted"
    motifs = [puits, distribution]
    matches = trouver_repertoires(dossier, motifs)

    for rep in matches:
        print(" ", rep)

    df = construire_dataframe(matches)

    print("\n=== Tableau structuré ===")
    afficher_dataframe_aligne(df)
