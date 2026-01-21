import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def charger_concentrations(chemin_dossier):
    """
    Charge le fichier concentrations.txt situé dans un répertoire donné.
    Retourne un DataFrame Pandas.
    """
    fichier = Path(chemin_dossier) / "concentrations.txt"
    if not fichier.exists():
        raise FileNotFoundError(f"⚠️ Fichier introuvable : {fichier}")
    
    df = pd.read_csv(fichier, sep="\t")  # séparateur tabulation
    return df



def tracer_concentrations(df_conc):
    """
    Trace les concentrations de cfc11, cfc12 et cfc113
    sur une seule figure avec 3 sous-graphiques (1 colonne).
    - Points avec barres d'erreur = 20% de la concentration
    - Pas de lignes reliant les points
    """
    elements = ["cfc11", "cfc12", "cfc113"]
    fig, axes = plt.subplots(len(elements), 1, figsize=(8, 12), sharex=True)

    for ax, elem in zip(axes, elements):
        subset = df_conc[df_conc["element"] == elem].copy()
        x = subset["date"]
        y = subset["concentration"]
        yerr = 0.2 * y  # 20% de la valeur

        ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3, label=elem)
        ax.set_ylabel("Concentration")
        ax.set_title(f"Concentration en {elem}")
        ax.grid(True)
        ax.legend()

    axes[-1].set_xlabel("Date")
    plt.tight_layout()
    plt.show()
    


