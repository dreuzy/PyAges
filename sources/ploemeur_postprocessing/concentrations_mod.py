import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def tracer_enveloppe(ax, df, gaz, color="#606060", alpha=0.3):
    """
    Ajoute l'enveloppe (min/max) des simulations d'un gaz comme fond coloré.
    
    Paramètres
    ----------
    ax : matplotlib axis
        Axe sur lequel tracer.
    df : DataFrame
        Simulations (index = dates, colonnes gaz_num).
    gaz : str
        Nom du gaz, ex. "cfc11".
    color : str ou tuple
        Couleur de l’enveloppe (par défaut gris neutre "#606060").
    alpha : float
        Transparence (0 = invisible, 1 = opaque, par défaut 0.3).
    """
    # Colonnes du gaz ciblé
    cols = [col for col in df.columns if col.startswith(f"{gaz}_")]
    if not cols:
        return  # rien à tracer

    sub = df[cols]
    env_min = sub.min(axis=1)
    env_max = sub.max(axis=1)

    # Remplissage derrière les autres courbes
    ax.fill_between(
        df.index,
        env_min,
        env_max,
        color=color,
        alpha=alpha,
        zorder=0
    )


    
def charger_concentrations(chemin_dossier: str):
    """
    Charge un fichier de concentrations de type tabulé.
    
    Paramètres
    ----------
    nom_fichier : str
        Nom du fichier texte (par ex. "concentrations.txt").
    
    Retour
    ------
    df : pd.DataFrame
        DataFrame contenant les données, indexé par la colonne 'date'.
    gaz_dict : dict
        Dictionnaire optionnel contenant un DataFrame par gaz (cfc11, cfc12, cfc113).
    """
    
    # Lecture du fichier avec séparateur tabulation
    nom_fichier = Path(chemin_dossier) / "Metropolis_Hastings/concentrations_all_models.txt"

    df = pd.read_csv(nom_fichier, sep="\t")
    
    # On met la date en index
    if "date" in df.columns:
        df.set_index("date", inplace=True)
    
    # Organisation par gaz avec correspondance exacte
    gaz_dict = {}
    for gaz in ["cfc11", "cfc12", "cfc113"]:
        cols = [col for col in df.columns if col.startswith(f"{gaz}_")]
        if cols:  # seulement si des colonnes existent
            gaz_dict[gaz] = df[cols]
    
    return df, gaz_dict