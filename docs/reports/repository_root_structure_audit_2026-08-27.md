# Audit de la structure des répertoires à la racine — 27 août 2026

## Verdict exécutif

Avant la consolidation, la copie de travail contenait 22 répertoires en
comptant `.git`, soit 21 hors `.git`, mais seulement 13 étaient versionnés. Les
8 autres étaient des réglages locaux, des caches, des sorties ou des artefacts
de construction déjà ignorés par Git.

Ces 13 racines versionnées ne révélaient pas une mauvaise séparation du code :
la bibliothèque, les données partagées, les exemples, les études de site, la
validation, l'article et les tests ont des responsabilités distinctes. Le
recouvrement évitable concerne surtout `audit/`, `docs/reports/` et
`submission_candidate/audit/`. Les racines `audit/` et
`submission_candidate/` ont été ajoutées avec les travaux de clôture
éditoriale et ne constituent pas de nouveaux domaines logiciels.

La consolidation a ramené la structure à 11 racines versionnées : `audit/` a
été déplacé sous `article/audit/` et `submission_candidate/` a été archivé sous
`article/archive/submission-candidate-2026-08-26/`. Aucun déplacement de
`data_core/`, `install/`, `examples/`, `sites/` ou `validation/` n'a été fait
uniquement pour réduire le nombre de dossiers affichés.

Cet audit documente la décision et son implémentation. Aucun code scientifique,
résultat de calcul ou réglage local n'a été déplacé avec les preuves
éditoriales.

## Audit antérieur retrouvé

Deux documents historiques correspondent au précédent travail d'architecture :

- `docs/ARCHITECTURE_COMPLETE.md`, ajouté par `1c5b488` le 18 janvier 2026,
  puis supprimé par `57198ce` le 20 août après consolidation de la
  documentation ;
- `docs/PLAN_REFACTORING.md`, ajouté par `63a0af9` le 18 janvier 2026, puis
  supprimé par `482871f` le 19 août après exécution de l'essentiel du plan.

Ils restent consultables dans Git :

```console
git show 57198ce^:docs/ARCHITECTURE_COMPLETE.md
git show 482871f^:docs/PLAN_REFACTORING.md
```

Leur proposition structurante était de séparer le paquet Python, les
applications, les données et les tests. Le commit `829e499` du 21 janvier 2026
(`Reorganize data and site structure`) a notamment séparé données partagées et
données de site, déplacé les scripts maintenus et retiré les résultats générés
du suivi. L'état actuel traduit largement ce plan :

| Objectif historique | État au 27 août 2026 | Emplacement actuel |
|---|---|---|
| Isoler la bibliothèque installable | Réalisé | `pyages/` |
| Séparer les applications ou études spécifiques | Réalisé | `sites/` et `article/` |
| Séparer les données partagées des observations | Réalisé | `data_core/`, `sites/*/data/`, `examples/*/data/` |
| Constituer une vraie suite de tests | Réalisé | `tests/` |
| Ne pas versionner les résultats calculés | Réalisé | `results/` est ignoré ; la sortie par défaut est hors dépôt |
| Documenter l'architecture maintenue | Réalisé et consolidé | `docs/architecture.md` |

Le présent audit n'annule donc pas l'ancien : il l'actualise après la migration
PyAges et l'ajout des preuves de publication.

## Méthode et périmètre

Le relevé repose sur la copie de travail et `HEAD` de la branche `main` :

- inventaire des répertoires réels avec PowerShell ;
- inventaire des racines versionnées avec `git ls-tree` et `git ls-files` ;
- contrôle des exclusions dans `.gitignore` ;
- contrôle du paquet distribué dans `pyproject.toml` et `MANIFEST.in` ;
- recherche des chemins utilisés dans le code, les tests, les exemples et la
  documentation ;
- examen de tout l'historique Git accessible pour retrouver l'audit précédent.

Les nombres de fichiers ci-dessous sont ceux suivis par Git. Des modifications
de travail étaient déjà présentes dans d'autres fichiers lors du relevé ; elles
n'affectent ni le nombre ni la fonction des racines et n'ont pas été modifiées
par cet audit.

## Inventaire avant consolidation

| Racine | Fichiers suivis | Responsabilité | Décision |
|---|---:|---|---|
| `.github/` | 10 | CI, modèles de contribution et gouvernance GitHub | Conserver |
| `article/` | 19 | Reproduction exacte des cas et figures de l'article | Conserver et en faire le propriétaire des audits éditoriaux |
| `audit/` | 17 | Audits du manuscrit, des figures et des calculs associés | Déplacé vers `article/audit/` |
| `data_core/` | 44 | Données scientifiques partagées livrées avec le paquet | Conserver à court terme |
| `docs/` | 80 | Documentation normative, rapports et archives documentaires | Conserver |
| `examples/` | 73 | Exemples réutilisables, naturels et synthétiques | Conserver |
| `install/` | 3 | Contraintes et environnement scientifique reproductible | Conserver |
| `pyages/` | 108 | Bibliothèque et ligne de commande installables | Conserver |
| `scripts/` | 39 | Outils maintenus de qualification, reproduction et release | Conserver |
| `sites/` | 118 | Données et workflows propres aux sites d'étude | Conserver |
| `submission_candidate/` | 11 | Instantané d'un audit de soumission arrêté le 26 août | Archivé sous `article/archive/` |
| `tests/` | 141 | Tests unitaires, d'intégration, de contrat et golden | Conserver |
| `validation/` | 81 | Comparaisons indépendantes, notamment avec TracerLPM | Conserver |

### Pourquoi les autres regroupements sont déconseillés

- `examples/` et `sites/` se ressemblent dans leur forme, mais pas dans leur
  contrat : les premiers servent de scénarios réutilisables, les seconds
  conservent des données, paramètres et provenances propres à une étude.
- `article/` et `validation/` produisent tous deux des preuves, mais la
  validation indépendante ne doit pas devenir une dépendance de la
  reproduction éditoriale.
- `install/` ne contient que trois fichiers, mais ceux-ci sont cités par de
  nombreux guides et enregistrent deux environnements qualifiés distincts.
- `data_core/` est un paquet de données explicite chargé par
  `importlib.resources`. Son chemin intervient dans le code, les YAML, les
  tests et la documentation. Un déplacement vers `pyages/data/` serait une
  migration de contrat et de packaging, pas un simple rangement.
- `scripts/` est volumineux, mais il possède un catalogue et regroupe des
  commandes transversales qui ne relèvent ni d'un site unique ni de l'API
  installée.

## Répertoires locaux non versionnés

| Racine locale | Nature | Action recommandée |
|---|---|---|
| `.pytest_cache/`, `.ruff_cache/`, `__pycache__/` | Caches recréables | Supprimer périodiquement ou via une option de nettoyage dédiée |
| `dist/`, `pyages.egg-info/` | Artefacts de construction du paquet | Nettoyer avec `python -m scripts.clean_release_artifacts` avant une nouvelle construction |
| `results/` | Sorties de calcul ignorées | Ne jamais supprimer automatiquement ; retirer seulement si les résultats ont été archivés ou si le dossier est vide |
| `.claude/`, `.vscode/` | Réglages propres au poste | Conserver localement s'ils sont utiles ; ils ne font pas partie du dépôt |

Le dossier `docs/` illustre l'écart entre structure logique et copie locale :
environ 1 Mio est versionné, tandis que la copie observée dépasse 47 Mio à
cause de `docs/_build/` et de l'API générée, toutes deux ignorées. Le même
phénomène explique une partie de l'encombrement visible dans les autres
racines.

Le nettoyeur traite par défaut les artefacts de release. Son doublon
`pyages.egg-info` a été retiré et l'option explicite `--include-caches` couvre
désormais les caches Python des racines maintenues, la couverture, les
constructions documentaires et les sorties `bin/`/`obj/` de TracerLPM. Ce mode
exclut volontairement `results/`, `.claude/` et `.vscode/`.

## Structure appliquée

```text
.
├── .github/
├── article/
│   ├── audit/                         # ancien audit/
│   ├── archive/
│   │   └── submission-candidate-2026-08-26/
│   ├── common/
│   ├── reports/
│   └── s*/
├── data_core/
├── docs/
├── examples/
├── install/
├── pyages/
├── scripts/
├── sites/
├── tests/
└── validation/
```

Cette structure fait passer le nombre de racines versionnées de 13 à 11 sans
mélanger des responsabilités stables ni modifier le contrat de données du
paquet.

## Mise en œuvre

### P0 — clarification et nettoyage local : réalisé

1. Le nettoyeur de release reste limité par défaut à `build/`, `dist/` et
   `pyages.egg-info/`.
2. L'option `--include-caches` supprime uniquement les caches, couvertures,
   sorties documentaires et constructions TracerLPM explicitement listés.
3. La section « Repository layout » du `README.md` décrit les 11 racines
   durables et leurs frontières.

### P1 — consolidation à faible risque : réalisée

1. Les rapports et leurs CSV associés sont regroupés sous `article/audit/`.
2. Le candidat arrêté est conservé sous une archive datée avec une notice de
   statut explicite.
3. Les chemins actifs et la documentation d'orientation ont été actualisés.
4. Les contrôles de références, de packaging, de documentation et de tests
   sont consignés dans le bilan de ce refactoring.

### Clarification interne de `data_core` : réalisée

La frontière a été rendue explicite sans changer les chemins des ressources
d'exécution :

- `data_lpm/` et `data_tracer/` restent les seules données scientifiques
  utilisées à l'exécution ;
- les trois classeurs de provenance sont regroupés sous `sources/tracer/` et
  restent exclus du wheel ;
- l'ancien prior `MHapriori-normal.txt`, sans référence active, est supprimé ;
  sa provenance reste accessible dans l'historique Git ;
- `data_core/README.md` documente le contrat et est livré dans le wheel ;
- `tests/data_io/` reflète désormais le nom du paquet `pyages.data_io` ;
- le catalogue de `scripts/` classe les 25 commandes maintenues par fonction,
  sans casser leurs chemins de module avant la version 1.0.

### P2 — décision de packaging, sans urgence

Évaluer seulement avant une future rupture de compatibilité l'intégration de
`data_core/` sous `pyages/`. La décision doit couvrir les ressources du wheel,
la résolution des chemins dans un checkout et après installation, les modèles
créés par la CLI, les configurations d'exemple et la provenance des données.
Le gain d'une seule racine ne justifie pas cette migration aujourd'hui.

## Vérifications après refactoring

| Contrôle | Résultat |
|---|---|
| Racines déplacées | 28 fichiers présents sous `article/` ; anciennes racines absentes |
| Références actives | aucune référence aux deux anciens chemins hors notices historiques |
| Contrats ciblés | 92 tests réussis, incluant article, documentation, métadonnées, nettoyage et validation TracerLPM |
| Suite standard | 944 tests réussis, 5 ignorés après la clarification de `data_core` et `tests/data_io` |
| Qualité du nettoyeur | Ruff réussi ; 3 tests de sécurité réussis |
| Documentation | construction Sphinx stricte `-W` réussie sur 94 pages |
| Packaging | wheel et sdist `pyages-1.0` construits ; `twine check` réussi |
| Contenu distribué | aucun chemin `article/`, `audit/`, `submission_candidate/` ou `data_core/sources/` dans le wheel ou le sdist ; `data_core/README.md` et les ressources d'exécution sont présents |
| Nettoyage final | 9 artefacts recréables supprimés ; `results/`, `.claude/` et `.vscode/` conservés |
| Racine locale finale | 14 répertoires hors `.git` : 11 domaines durables et 3 répertoires locaux conservés |

## Critères d'acceptation de la réorganisation

- 11 racines versionnées, sans perte de fichiers ni de provenance ;
- aucune référence active vers les deux anciens chemins ;
- wheel et sdist inchangés hors métadonnées attendues ;
- documentation Sphinx construite avec `-W` ;
- tests de contrats documentaires, de packaging, des scripts d'article et de
  validation réussis ;
- `git status --ignored` ne révèle à la racine que les réglages locaux ou les
  artefacts explicitement acceptés.
