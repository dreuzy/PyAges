import os
from pathlib import Path
import re
import pandas as pd

import ploemeur_postprocessing.folders as fold
import ploemeur_postprocessing.concentrations_obs as cobs
import ploemeur_postprocessing.concentrations_mod as cmod



if __name__ == "__main__":
    dossier = Path(r"C:\results\pyage\2025, février, v2")
    puits = "F09"
    distribution = "exp_shifted"

    folders = fold.trouver_repertoires(dossier, [puits, distribution])

    df = fold.construire_dataframe(folders)
    fold.afficher_noms_repertoires(df)
    
    # Appeler la nouvelle fonction
    df_all = fold.trouver_all_plage(df)

    # print("\n=== Répertoires avec la plage de temps maximale ===")
    # fold.afficher_dataframe_aligne(df_max)

    # Exemple : on prend le premier répertoire de df_all
    dossier_cible = df_all.iloc[0]["chemin"]
    
    all_lpm_dist = fold.charger_lpm_dist(dossier_cible)

    # Charger le fichier
    df_conc = cobs.charger_concentrations(dossier_cible)
    
    # Charger le fichier de concentrations modélisés
    df_dist = cmod.charger_distributions(dossier_cible)

    # Tracer les graphiques
    cobs.tracer_concentrations(df_conc,df_dist)
    