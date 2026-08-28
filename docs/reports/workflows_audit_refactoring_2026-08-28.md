# Audit et durcissement de `pyages.workflows` — 2026-08-28

## Périmètre

L'audit couvre les workflows installés `single_date` et `temporal`, le workflow
interne de qualification synthétique, l'exécution Matplotlib, le manifeste de
résultats, les modèles de configuration associés, leurs tests ciblés et leur
documentation active. Il s'appuie sur l'API de calibration stabilisée avant les
modifications.

La référence précédant les corrections comptait 50 tests réussis sur les
workflows, les chemins, la configuration et le manifeste.

## Constats et corrections

| Gravité | Constat | Correction |
| --- | --- | --- |
| élevée | Les observations étaient écrites et parfois tracées avant que les erreurs nulles soient remplacées par les incertitudes réellement utilisées en calibration. L'analyse d'objectif seule dépendait ainsi d'un effet de bord d'une calibration préalable. | La résolution des erreurs et la validation des unités forment maintenant une frontière partagée avec `CalibrationProblem`. Elles sont exécutées avant tout export, tracé ou exploration. Les deux workflows écrivent une table normalisée contenant les erreurs effectives. |
| élevée | Le facteur historique de 1 % utilisé pour remplacer une erreur nulle restait implicite et sa transformation n'était pas identifiable dans les sorties. | Les deux workflows exposent `missing_error_rel` (défaut explicite `0.01`). Le manifeste enregistre la politique, la méthode, la fraction et les lignes transformées, tandis que `concentrations.txt` conserve les valeurs effectives. |
| élevée | Une relance échouée dans un répertoire existant pouvait laisser le manifeste `complete` de l'exécution précédente. | Le précédent manifeste est supprimé au début de l'écriture d'une nouvelle exécution. Le nouveau manifeste n'est publié qu'après succès, par remplacement atomique. |
| moyenne | `seed_enabled: false` réutilisait implicitement la graine fixe par défaut de `MHConfig`. Une graine activée mais absente échouait tardivement. | Chaque chaîne temporelle sans graine fixe reçoit une graine aléatoire explicite enregistrée dans ses paramètres. Une graine fixe activée est exigée et validée comme entier non négatif dès le chargement YAML. |
| moyenne | Le manifeste ne référençait explicitement que le jeu d'observations et échouait si l'exécutable Git était absent. | Les répertoires scientifiques sélectionnés sont développés en fichiers LPM et traceurs, dédupliqués et hachés. L'absence de Git produit des champs de dépôt vides sans interrompre le workflow. |
| moyenne | Le runtime imposait `TkAgg` hors IPython, ce qui rendait l'exécution fragile sur serveur sans interface graphique. | Hors demande `inline` ou variable `MPLBACKEND`, Matplotlib conserve désormais son backend automatiquement choisi. Une demande `inline` impossible produit une erreur explicite. |
| moyenne | Une liste temporelle explicitement vide sélectionnait silencieusement les modèles par défaut ; des modèles vides ou dupliqués pouvaient réutiliser les mêmes sorties. | Seul `null` sélectionne les modèles par défaut. Les listes explicites doivent être non vides, sans nom vide et sans doublon. Les chemins de données et de modèles sont contrôlés comme fichier et répertoire respectivement. |
| faible | Les libellés de dates successives arrondis à six décimales pouvaient fusionner deux dates distinctes dans le même dossier. | Les libellés utilisent la représentation décimale flottante la plus courte garantissant l'aller-retour, avec un contrôle défensif des collisions. |
| faible | Les valeurs par défaut du workflow synthétique conduisaient à des erreurs d'attribut, `ncase=0` à une variable non initialisée et une cible d'un autre type modifiait silencieusement l'expérience. | La stratégie, le répertoire, les comptes, l'erreur, le modèle et les traceurs sont validés avant allocation. Une cible absente ou d'une autre famille est rejetée sans mutation. |

## Contrats conservés

- Les objectifs scientifiques, méthodes de calibration et schémas des tables de
  distributions calibrées ne changent pas.
- `error_rel` temporel conserve son rôle d'écrasement relatif lorsque des
  erreurs nulles sont présentes ; il doit désormais être strictement positif.
- `missing_error_rel` remplit uniquement les erreurs encore nulles à partir de
  la moyenne du traceur ; il est strictement positif et inférieur à un.
- Les répertoires déterministes restent réutilisés et les anciens artefacts
  autres que le manifeste ne sont pas supprimés automatiquement.
- Le workflow synthétique accepte encore une erreur nulle pour les
  qualifications sans vraisemblance ; la frontière de calibration remplace les
  zéros avant tout objectif qui exige une incertitude positive.

## Risques résiduels

- Une publication doit toujours partir d'un répertoire vide ou archiver le
  résultat précédent : un nouveau manifeste réussi hache aussi les artefacts
  historiques conservés dans le répertoire.
- Le manifeste capture les ressources directes et les versions principales,
  mais ne remplace ni un verrou complet d'environnement ni les diagnostics
  scientifiques de convergence.
- Le workflow synthétique reste un outil de qualification interne et non une
  troisième commande publique.

## Vérification

Les tests ajoutés couvrent la résolution précoce des erreurs, l'absence d'index
parasite dans les observations exportées, l'invalidation du manifeste, son
écriture sans Git, le développement des répertoires d'entrée, les deux modes de
graine, les dates très proches, les validations YAML, le choix de backend et les
gardes du workflow synthétique.

Vérification locale finale :

- suite complète : **1 047 tests réussis, 5 ignorés** ;
- Ruff global : réussi ;
- formatage Ruff du périmètre modifié : réussi ; le contrôle global identifie
  uniquement `tests/convolution/test_batch.py`, fichier déjà modifié hors de ce
  périmètre et volontairement préservé ;
- compilation de `pyages` avec `compileall` : réussie ;
- construction Sphinx HTML complète avec `-E -a -W --keep-going` : réussie ;
- contrôle des différences et espaces du périmètre : réussi.
