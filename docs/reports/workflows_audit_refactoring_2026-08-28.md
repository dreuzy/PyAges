# Audit et durcissement de `pyages.workflows` — 2026-08-28

## Périmètre

L'audit couvre les workflows installés `single_date` et `temporal`, l'expérience
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
| faible | Les valeurs par défaut de l'expérience synthétique conduisaient à des erreurs d'attribut, `ncase=0` à une variable non initialisée et une cible d'un autre type modifiait silencieusement l'expérience. | La stratégie, le répertoire, les comptes, l'erreur, le modèle et les traceurs sont validés avant allocation. Une cible absente ou d'une autre famille est rejetée sans mutation. |
| élevée | Les noms de jeu de données, de modèle et d'étude devenaient des composants de répertoire sans garde commune ; `..`, un chemin absolu ou un séparateur pouvait faire sortir une écriture de l'arborescence de résultats attendue. | Les composants issus du YAML sont validés avant toute création de répertoire. Les règles communes résident dans `pyages.config.paths`, tandis que la convention de sortie propre au workflow single-date réside dans `pyages.workflows.single_date.paths`. |
| moyenne | Une erreur du workflow single-date après l'initialisation de Matplotlib pouvait laisser des figures ouvertes et une session graphique partiellement active. | La préparation et l'orchestration ferment désormais toutes les figures en cas d'échec, sans écrire de manifeste de succès. |
| moyenne | `results.use_default: false` sans `results.directory` n'était rejeté qu'après le chargement des observations, car le validateur de champ Pydantic ne s'exécutait pas pour une valeur omise. | Un validateur de modèle rejette maintenant ce cas dès le chargement YAML, y compris pour une chaîne vide ou composée d'espaces. |
| élevée | Une relance dont le YAML était valide mais dont une entrée scientifique avait disparu pouvait échouer pendant la préparation avant l'invalidation de l'ancien manifeste `complete`. | Le répertoire cible est maintenant résolu et son manifeste invalidé avant le chargement des observations et la validation des ressources scientifiques. Un YAML invalide ne touche à aucun résultat existant. |
| élevée | L'export single-date recalculait les chroniques avec les données de traceurs intégrées, même lorsque la calibration utilisait un répertoire `tracer_data_dir` personnalisé. | Le répertoire sélectionné est propagé jusqu'à `ConvolutionTracers` pendant l'export. Un test vérifie explicitement cette continuité entre calibration et chroniques exportées. |
| moyenne | Deux ressources externes portant le même nom produisaient des chemins identiques dans le manifeste, ce qui rendait leur provenance ambiguë malgré des empreintes distinctes. Le déplacement du manifeste sous `workflows.runtime` avait en outre décalé d'un niveau le calcul de la racine du dépôt. | Les ressources hors dépôt sont indexées sous `external/<racine>/<chemin relatif>`. Les chemins internes restent relatifs à la racine corrigée du dépôt et les doublons physiques restent dédupliqués. Les deux cas disposent de tests de non-régression. |
| faible | Cinq modules plats ne contenaient plus que des réexports vers les nouveaux emplacements et entretenaient deux chemins pour une même responsabilité. | `concentration_exports`, `result_manifest`, `plotting_runtime`, `single_date_config` et `single_date_paths` sont supprimés. Les imports canoniques sont documentés et leur absence est protégée par le contrat d'API publique. |
| faible | Des tests conservaient les noms historiques `concentration_exports`, `plotting_runtime` et `synthetic_recovery` comme alias locaux ou noms de fichiers après le déplacement des responsabilités. | Les tests et leur inventaire suivent désormais les noms canoniques `reporting.chronicles`, `runtime.plotting` et `qualification`. |

## Organisation et nomenclature

Le nom `workflows` est conservé : il décrit correctement les deux façades
publiques qui enchaînent configuration, calculs et sorties. Le paquet initial
mélangeait toutefois quatre responsabilités. Elles sont maintenant séparées :

| Emplacement canonique | Responsabilité |
| --- | --- |
| `pyages.workflows.single_date` | configuration, contexte, calibration, chemins propres au cas et orchestration single-date |
| `pyages.workflows.temporal` | contexte, découpage des cas, calibration d'un modèle et orchestration temporelle |
| `pyages.workflows.runtime` | session Matplotlib et manifeste de provenance |
| `pyages.reporting` | chroniques, exports et figures réutilisables |
| `pyages.qualification` | expérience de récupération synthétique, hors workflows utilisateur |

Les fichiers génériques `single_date.py` et `temporal.py` deviennent des
paquets dont `runner.py` constitue le point d'orchestration explicite. Les
contextes se nomment `SingleDateContext` et `TemporalContext`. Le volumineux
module de graphiques d'objectif est séparé entre synthèse et carte de solution.
Les anciens imports utilitaires plats sous `pyages.workflows`, ainsi que les
chemins internes `pyages.workflows.plots` et
`pyages.workflows.synthetic_recovery`, sont supprimés avant 1.0. Le code actif
et les contrats documentaires utilisent uniquement les nouveaux chemins
descriptifs.

Le passage de nettoyage ne conserve aucun alias historique dans cette zone et
aucun workflow n'hérite d'un objet de calibration ou de reporting. L'unique
héritage applicatif adjacent, `HoltenFileConfig(LauncherConfig)`, est remplacé
par une composition Pydantic qui conserve le YAML plat existant. L'outil
interne devient `SyntheticRecoveryExperiment`, sans alias
`SyntheticRecoveryWorkflow`. Les héritages restants sont les bases Pydantic
communes qui portent la politique de validation stricte, et non un partage de
comportement métier.

## Contrats conservés

- Les objectifs scientifiques, méthodes de calibration et schémas des tables de
  distributions calibrées ne changent pas.
- `error_rel` temporel conserve son rôle d'écrasement relatif lorsque des
  erreurs nulles sont présentes ; il doit désormais être strictement positif.
- `missing_error_rel` remplit uniquement les erreurs encore nulles à partir de
  la moyenne du traceur ; il est strictement positif et inférieur à un.
- Les répertoires déterministes restent réutilisés et les anciens artefacts
  autres que le manifeste ne sont pas supprimés automatiquement.
- L'expérience synthétique accepte encore une erreur nulle pour les
  qualifications sans vraisemblance ; la frontière de calibration remplace les
  zéros avant tout objectif qui exige une incertitude positive.

## Risques résiduels

- Une publication doit toujours partir d'un répertoire vide ou archiver le
  résultat précédent : un nouveau manifeste réussi hache aussi les artefacts
  historiques conservés dans le répertoire.
- Le manifeste capture les ressources directes et les versions principales,
  mais ne remplace ni un verrou complet d'environnement ni les diagnostics
  scientifiques de convergence.
- L'expérience synthétique reste un outil de qualification interne et non une
  troisième commande publique.

## Vérification

Les tests ajoutés couvrent la résolution précoce des erreurs, l'absence d'index
parasite dans les observations exportées, l'invalidation du manifeste, son
écriture sans Git, le développement des répertoires d'entrée, les deux modes de
graine, les dates très proches, les validations YAML, le choix de backend et les
gardes de l'expérience synthétique.

Le second passage couvre en plus les tentatives de traversée de chemin par les
champs de configuration, la validation précoce du répertoire temporel et le
nettoyage des figures après une exception d'orchestration.

Le premier passage intégré au commit de référence avait validé **1 047 tests
réussis et 5 ignorés**, Ruff global, la compilation et une construction Sphinx
stricte complète.

Vérification finale du second passage sur l'état intégré :

- suite standard : **1 079 tests réussis et 5 ignorés**, avec **85,77 %** de
  couverture de branches pour un seuil bloquant de 75 % ;
- sélection scientifique extensive : **5 tests réussis**, dont le workflow
  Ploemeur F09 multiprocessing et son golden régénéré après le passage des
  priors empiriques à l'interpolation linéaire ;
- Ruff lint et format sur 467 fichiers, `compileall`, inventaire de tests,
  `pip check`, `pip-audit`, métadonnées CeCILL 2.1 et `git diff --check` :
  réussis ;
- constructions Sphinx HTML et `linkcheck` strictes sur 107 sources : réussies
  sans avertissement ;
- sdist et wheel `pyages-1.0` construits ; contrôle `twine check` réussi sur les
  deux artefacts.
