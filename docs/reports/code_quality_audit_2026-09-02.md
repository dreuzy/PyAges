# Audit complet du code, de la documentation et de la dette technique — 2 septembre 2026

> Mise à jour du 4 septembre 2026 : la couche de migration décrite dans cet
> audit a depuis été retirée. Les alias `bounds`, le journal manifeste en place,
> la configuration aplatie et le drapeau CLI historique ne font plus partie du
> code courant.

## Conclusion générale

PyAges est dans un état globalement robuste. L'organisation par domaines est
compréhensible, les responsabilités scientifiques sont identifiables et les
contrats à risque sont fortement testés. Aucun nouveau défaut scientifique ou
changement numérique involontaire n'a été identifié pendant ce réaudit.

Le principal problème restant n'était pas une complexité algorithmique hors de
contrôle, mais la concentration de plusieurs responsabilités dans quelques
fichiers. Trois découpages ciblés ont donc été réalisés sans ajouter de couche
générique :

- le chargement des paramètres LPM est séparé de la validation de leur schéma ;
- les objets de résultat MH sont séparés de leurs validations croisées ;
- le manifeste de workflow est séparé de la provenance, de l'inventaire des
  artefacts et de l'inspection des exécutions interrompues.

Les façades existantes restent les points d'entrée. Les modules extraits sont
privés et nommés d'après leur responsabilité. Le refactoring ne change donc ni
les formules, ni la cible statistique, ni le protocole d'échantillonnage, ni les
fichiers de résultats documentés.

| Axe | Verdict | Commentaire |
|---|---|---|
| Exactitude scientifique | Bon | Les suites standard, extensive et de validation indépendante sont exécutées ; aucune régression n'est observée. |
| Organisation | Bonne | Les domaines sont nets ; les trois principaux fichiers à responsabilités multiples ont été découpés. |
| Lisibilité | Bonne | Les façades restent simples à trouver ; les détails sont dans des modules privés ciblés. |
| Complexité | Maîtrisée | Aucune fonction ne dépasse la complexité cyclomatique autorisée de 10. |
| Couverture | Bonne, non exhaustive | 85,87 % de couverture avec branches ; les lacunes restantes sont identifiées ci-dessous. |
| Documentation | Bonne | La documentation stricte et les liens passent ; plusieurs incohérences de navigation et de version ont été corrigées. |
| Dette technique | Modérée et localisée | Elle concerne surtout les défenses rares des résultats/manifests, quelques grandes fonctions de tracé et l'extension progressive du typage. |

## 1. Périmètre et méthode

L'audit porte sur le paquet installable `pyages`, ses tests, sa documentation,
ses métadonnées de distribution et les contrôles CI associés. Les exemples et
les données ont été contrôlés lorsqu'ils constituent un contrat d'exécution ou
de paquet, mais leur volume n'est pas compté dans les lignes Python du cœur.

Le dépôt contenait déjà un grand ensemble de modifications non validées avant
ce réaudit. Elles ont été conservées. Le présent rapport décrit donc l'état du
répertoire de travail au moment des vérifications, et non un diff isolé par un
commit.

Les indicateurs utilisés sont :

- inventaire physique des fichiers et lignes ;
- complexité McCabe contrôlée par Ruff ;
- lecture des dépendances, façades, héritages et alias ;
- tests standard, tests scientifiques extensifs et validation TracerLPM ;
- couverture de lignes et de branches ;
- Pyright sur un périmètre progressif explicite ;
- construction Sphinx stricte et vérification des liens ;
- cohérence des métadonnées, licences, dépendances et distributions.

## 2. Taille du code

### 2.1 Mesure actuelle

| Ensemble | Fichiers Python | Lignes physiques | Lignes non vides et hors commentaires |
|---|---:|---:|---:|
| Paquet `pyages` | 149 | 26 760 | 21 820 |
| Tests du cœur | 122 | 21 776 | non mesuré |

Les tests représentent environ 81 % du volume physique du paquet. Ce ratio est
cohérent avec une bibliothèque scientifique qui doit protéger des formules,
des cas limites, des formats de résultats et des scénarios de reproduction.

### 2.2 Répartition du paquet

| Domaine | Fichiers | Lignes physiques | Part approximative |
|---|---:|---:|---:|
| `calibration` | 37 | 7 613 | 28,5 % |
| `lpm` | 30 | 4 549 | 17,0 % |
| `workflows` | 22 | 3 789 | 14,2 % |
| `reporting` | 10 | 2 296 | 8,6 % |
| `convolution` | 7 | 1 648 | 6,2 % |
| `data_io` | 7 | 1 437 | 5,4 % |
| `cli` | 11 | 1 381 | 5,2 % |
| `concentrations` | 6 | 1 246 | 4,7 % |
| `config` | 7 | 1 120 | 4,2 % |
| `tracer` | 7 | 1 036 | 3,9 % |

La taille est principalement portée par les missions centrales : calibration,
modèles de temps de transit et exécution reproductible. Elle n'est pas dominée
par une infrastructure périphérique sans rapport avec le produit.

### 2.3 Pourquoi le code prend de la taille

La croissance vient de cinq besoins légitimes :

1. **Diversité scientifique.** Douze familles LPM distribuées, plusieurs types
   de traceurs, la convolution adaptative et des objectifs de calibration ne
   peuvent pas être réduits à une seule formule générique sans rendre le code
   moins lisible ou masquer des cas numériques différents.
2. **Deux niveaux d'inférence.** PyAges maintient Simplex, MH à une chaîne et MH
   multichaîne. Le multichaîne ajoute initialisation dispersée, pilote,
   covariance commune, diagnostics, qualification et pooling conditionnel.
3. **Validation explicite.** Une part importante du code refuse les états non
   finis, schémas ambigus, supports vides, incohérences entre chaînes et
   résultats mutés. Supprimer ces branches raccourcirait le code au prix de
   défaillances scientifiques tardives.
4. **Reproductibilité.** Les manifests vérifient source, entrées, environnement,
   artefacts, journaux, verrous, promotion atomique et reprise après incident.
   Cette mission explique la taille de `workflows.runtime`.
5. **Produit complet.** Configuration YAML, CLI, tableaux, graphiques,
   documentation et paquet installable font partie du livrable ; le code ne se
   limite pas au noyau numérique.

La taille totale est donc légitime au regard des missions. En revanche, elle ne
justifie pas des fichiers qui mélangent plusieurs raisons de changer. C'est ce
point précis que les extractions de cet audit corrigent.

## 3. Refactorings réalisés

### 3.1 Paramètres LPM : séparer fichier et schéma

Avant le découpage, `data_io/lpm_params.py` gérait à la fois le système de
fichiers, le cache, les dataclasses du schéma et toute la validation de
`domain`, `calibration_range` et `prior`.

La nouvelle organisation est :

```text
lpm_params.py                   190 lignes
  chargement, cache, accesseurs et réexports
        |
        `-> _lpm_parameter_schema.py   514 lignes
            records immuables et validation pure du schéma
```

Le fichier public est désormais un point d'accès court. La validation pure peut
être testée sans accès au disque. Les imports historiques depuis
`pyages.data_io.lpm_params` restent disponibles.

### 3.2 Résultats MH : séparer données et cohérence croisée

`calibration/methods/mh/results.py` est passé d'environ 924 à 604 lignes. Il
conserve les dataclasses, constantes et opérations publiques sur les résultats.
Les 383 lignes de `_result_validation.py` contrôlent désormais séparément :

- l'identité et l'ordre des chaînes ;
- les graines et états d'initialisation ;
- la correspondance entre configuration et diagnostics ;
- les statuts de qualification et les règles de pooling ;
- l'intégrité des snapshots et des métriques.

Cette extraction ne crée pas une seconde représentation du résultat. Elle évite
au contraire que les types et leurs validations croisées soient entremêlés dans
un seul fichier.

### 3.3 Manifests : isoler les responsabilités sans casser la façade

`workflows/runtime/manifest.py` est passé d'environ 1 783 à 1 003 lignes. Il
reste volumineux, mais son contenu restant est cohérent : cycle de vie,
écriture terminale, promotion atomique, rollback et quarantaine.

```text
manifest.py
  façade et cycle de publication
  |
  +-- _manifest_types.py        handles et records immuables
  +-- _manifest_fs.py           primitives sûres du système de fichiers
  +-- _manifest_provenance.py   source, entrées, distributions, environnement
  +-- _manifest_artifacts.py    inventaire et empreintes des artefacts
  `-- _manifest_inspection.py   journaux et stages interrompus
```

La provenance et l'inspection sont en lecture seule. Les opérations mutantes
restent groupées dans la façade, ce qui rend les garanties d'atomicité plus
faciles à suivre. Extraire maintenant la promotion elle-même obligerait à faire
circuler de nombreux détails de verrouillage entre modules ; le gain de taille
ne compenserait pas encore ce couplage.

### 3.4 Publication : ne plus créer de résultat vide avant le commit

La suite extensive a mis en évidence deux problèmes Windows successifs. Le nom
temporaire du test temporel répétait inutilement un long identifiant et pouvait
dépasser la limite historique de chemin. Après son raccourcissement, une défense
du manifest a révélé qu'un workflow créait aussi sa feuille publique vide avant
de commencer son stage.

Si cette feuille vide disparaissait pendant les quatre minutes du calcul, la
protection compare-and-swap refusait légitimement la promotion, car l'état
public n'était plus celui du départ. Le vrai problème était en amont : un
résultat non terminal n'aurait jamais dû être visible, même sous forme de
dossier vide.

Les workflows single-date et temporel construisent maintenant le chemin sans
créer sa feuille finale. `begin_staged_result_run()` crée seulement le stage
frère privé ; la feuille publique apparaît au commit atomique. Un résultat
public préexistant reste inchangé et protégé par la même empreinte. Deux tests
rapides vérifient ce contrat, et le scénario temporel extensif repasse avec la
racine temporaire Windows normale.

### 3.5 Découpages volontairement non réalisés

`config/models.py` compte 633 lignes, mais il est déclaratif, couvert à 97 % et
déjà appuyé par `_models_base.py` et `_models_cli.py`. Le diviser par simple
seuil de lignes disperserait les modèles Pydantic et leurs validations sans
réduire la complexité. Il est conservé en l'état.

De même, aucun paquet `common`, `helpers` ou `utils` supplémentaire n'a été
créé. Les nouveaux modules ont une responsabilité métier précise. Cette règle
évite une architecture plus abstraite que le problème traité.

## 4. Complexité : mesure et justification

L'analyse syntaxique compte 937 fonctions ou méthodes et 115 classes. Ruff
impose une complexité McCabe maximale de 10 sur tout le dépôt : aucun dépassement
n'est présent. Avec un seuil exploratoire plus strict de 5, 118 fonctions sont
signalées, soit environ 12,6 % des fonctions ; elles restent toutes entre 6 et
10.

La complexité ne se confond pas avec la longueur. Les plus longues fonctions
sont principalement des compositions de figures :

| Fonction | Lignes | Nature |
|---|---:|---|
| `plot_objective_solution_map` | 137 | assemblage de panneaux et annotations |
| `plot_observations_overview` | 125 | normalisation puis composition graphique |
| `plot_temporal_fit_summary` | 121 | disposition de plusieurs résumés |
| `plot_single_date_model_space` | 115 | construction d'une figure composite |
| `_refine_adaptive_grid` | 114 | raffinement numérique avec critères d'arrêt |
| `MultiChainMetropolisHastings.run` | 101 | séquence explicite des phases d'inférence |

### 4.1 Complexité justifiée

- Les validations de schéma et de résultats ont plusieurs branches parce que
  chaque message correspond à un invariant scientifique ou de sérialisation.
- Le sampler et l'ensemble MH exposent explicitement préparation, proposition,
  acceptation, stockage, pilote et production. Cette séquence est préférable à
  une machine générique implicite.
- La promotion d'un résultat couvre concurrence, verrouillage, comparaison
  d'état, rollback et liens de fichiers. Ce sont des garanties de sûreté, pas
  des variantes fonctionnelles accidentelles.
- Le raffinement adaptatif de la convolution porte de vraies conditions
  numériques de convergence.

### 4.2 Complexité encore perfectible

- Les grandes fonctions de tracé pourraient partager davantage de petites
  fonctions de préparation de panneaux. Ce travail est de priorité basse : la
  complexité McCabe reste contenue et les extractions ne doivent pas masquer le
  déroulé visuel.
- `_result_validation.py` concentre plusieurs validations rares. Son découpage
  est désormais lisible, mais ses branches défensives doivent recevoir quelques
  tests directs supplémentaires avant toute nouvelle modification.
- `manifest.py` demeure le plus grand fichier. Un nouveau découpage ne sera
  justifié que si la promotion ou la quarantaine acquiert une nouvelle mission,
  ou si le fichier recommence à mélanger lecture seule et mutation.

## 5. Héritage, composition et alias

### 5.1 Héritage

L'héritage est limité à trois usages justifiés :

```text
CalibrationMethod (ABC)
  +-- Simplex
  `-- MetropolisHastings

LpmBase (ABC)
  +-- LpmScipy
  |     `-- modèles directement représentés par une loi SciPy
  `-- modèles spécialisés : Dirac, mélange, shape-free, etc.

BaseConfigModel (Pydantic)
  `-- records de configuration validés
```

Il n'y a pas de hiérarchie multiple profonde. Le multichaîne compose un sampler
et une fabrique de problèmes au lieu d'hériter du problème scientifique. Les
traceurs consommés par la convolution sont décrits par un `Protocol`, ce qui
évite une classe de base artificielle. Aucun refactoring d'héritage
supplémentaire n'est recommandé.

### 5.2 Alias

Les anciens modules plats et les alias expérimentaux antérieurs à 1.0 ont été
supprimés. Le suivi du 4 septembre a également retiré les noms historiques
fondés sur `bounds` après migration des fichiers maintenus vers
`calibration_range`.

Le suivi du 4 septembre a supprimé `begin_result_run()` après migration des
derniers tests. Tous les workflows utilisent désormais
`begin_staged_result_run()`.

## 6. Tests et couverture

L'inventaire généré documente 1 523 cas du cœur, dont 9 scénarios scientifiques
opt-in, plus 65 cas de validation TracerLPM. Les résultats de ce réaudit sont :

| Vérification | Résultat |
|---|---|
| Suite standard | 1 508 réussis, 15 ignorés |
| Suite scientifique extensive | 1 512 réussis, 6 ignorés au point de contrôle précédant 5 nouveaux cas standard |
| Validation TracerLPM | 65 réussis |
| Couverture lignes + branches | 85,87 %, seuil requis 75 % |

Les 15 cas ignorés dans la suite standard correspondent aux 9 tests extensifs
opt-in et à 6 tests de liens/jonctions indisponibles sur cette plateforme
Windows. Le profil extensif exécute les 9 premiers ; les 6 derniers restent
qualifiés par le CI Linux.

Le point de contrôle extensif précède cinq cas standard ajoutés ensuite. Ces
cinq cas passent dans les suites standard et couverture finales ; le profil
extensif complet n'a pas été relancé après leur ajout.

### 6.1 Lacunes corrigées

Des tests directs ont été ajoutés pour :

- les probabilités ouvertes, valeurs non finies, types ambigus et bornes
  inversées de `_prior_support.py` ;
- les noms de paramètres, fichiers absents, mappings/vecteurs invalides,
  domaines et délégations historiques de `ParameterManager` ;
- les sorties humaine et vide de `pyages stages inspect`, ainsi que la
  traduction d'une erreur runtime en erreur CLI.

Effet mesuré :

| Zone | Couverture actuelle |
|---|---:|
| `_prior_support.py` | 100 % |
| `lpm/core/parameter_manager.py` | 96 % |
| `cli/commands/stages.py` | 97 % |
| `_manifest_artifacts.py` | 100 % |
| `_manifest_provenance.py` | 91 % |

### 6.2 Dette de test restante

La couverture totale ne signifie pas que chaque défense est exercée :

- `_result_validation.py` est à 74 % ; les manques sont surtout des
  incohérences impossibles à produire par les constructeurs normaux ;
- `manifest.py` est à 75 % et `_manifest_inspection.py` à 81 % ; les branches
  restantes incluent rollback, erreurs de verrou et particularités de fichiers ;
- `_lpm_parameter_schema.py` est à 83 % ; quelques erreurs de structures YAML
  combinées restent à tester directement ;
- les modules de tracé se situent souvent entre 64 et 85 %, surtout sur les
  entrées optionnelles et les erreurs d'affichage.

La priorité suivante doit être la validation des résultats et le rollback du
manifest, pas une recherche uniforme de 100 % sur les tracés.

## 7. Typage et qualité statique

Pyright est maintenant une dépendance de développement, une commande CI et une
étape documentée. Son périmètre est volontairement explicite : petits contrats
stables de prior, calendrier d'échantillonnage, réglages de convolution,
protocoles de traceurs et types de manifest.

Le contrôle passe sans erreur, avertissement ou information. Le paquet complet
n'est pas présenté comme entièrement typé et ne publie pas de marqueur
`py.typed`. Cette progression honnête est préférable à une configuration très
permissive appliquée artificiellement à tout le dépôt.

Ruff passe en lint et en format sur les 410 fichiers Python contrôlés. Le seuil
McCabe de 10 est appliqué globalement.

## 8. Documentation et facilité d'accès

Les corrections suivantes ont été appliquées :

- une seule commande d'installation rapide reste dans le README ;
- la suite « standard » n'est plus décrite à tort comme la totalité des tests ;
- la version stable 1.0.1 est distinguée de l'archive immuable de l'article 1.0 ;
- la consigne de tag de release n'est plus figée sur une ancienne version ;
- le double enregistrement des pages API générées a été supprimé ;
- le périmètre progressif de Pyright est expliqué dans les guides contributeur
  et CI ;
- des caractères corrompus ont été corrigés dans le runner d'article non
  Ploemeur ;
- les règles de dépendances entre `config`, `data_io`, noyau scientifique,
  workflows et reporting sont maintenant écrites dans l'architecture ;
- l'inventaire de tests et les notices de licences ont été régénérés.

La construction HTML Sphinx avec avertissements bloquants réussit. Le
`linkcheck` strict réussit également ; les redirections DOI attendues et les
liens explicitement ignorés restent visibles dans son journal.

## 9. Dépendances et distribution

`pip check` ne trouve aucune dépendance incohérente. `pip-audit` ne trouve
aucune vulnérabilité connue dans l'environnement qualifié ; le paquet PyAges
éditable est normalement exclu de cet audit tiers.

Le sdist et la wheel 1.0.1 sont reconstruits dans un répertoire d'artefacts
isolé. `twine check` accepte les deux. Les nouveaux modules privés sont inclus
dans les deux distributions.

## 10. Dette technique restante et priorités

| Priorité | Sujet | Action recommandée | Critère de fin |
|---|---|---|---|
| P1 | Branches rares des résultats MH | Ajouter des tests unitaires construisant explicitement chaque incohérence | `_result_validation.py` au-dessus de 80 % sans test couplé à l'implémentation |
| P1 | Rollback et erreurs de publication | Renforcer les scénarios d'échec simulé et les exécuter aussi sous Linux | garanties de restauration couvertes sur Windows et Linux |
| P2 | Typage progressif | Ajouter un petit module stable par changement, après correction réelle de ses types | périmètre Pyright croissant sans `ignore` global |
| P2 | Fonctions de tracé longues | Extraire seulement les préparations de données répétées | réduction de duplication mesurée, sorties graphiques inchangées |
| P3 | Taille de `manifest.py` | Ne redécouper qu'à l'apparition d'une nouvelle responsabilité | pas de dépendance circulaire ni de façade supplémentaire |

Il n'est pas recommandé de :

- supprimer des validations pour réduire le nombre de lignes ;
- fragmenter `config/models.py` uniquement parce qu'il dépasse 600 lignes ;
- réintroduire des alias de migration sans calendrier de suppression ;
- introduire un framework générique de workflow ou de résultat ;
- viser 100 % de couverture de manière uniforme, notamment sur le rendu
  graphique.

## 11. Vérifications exécutées

| Commande ou contrôle | Résultat |
|---|---|
| `python -m ruff check .` | réussi |
| `python -m ruff format --check .` | 410 fichiers conformes |
| `python -m pyright` | 0 erreur, 0 avertissement |
| contrôle des docstrings qualifiées | réussi |
| contrôle des métadonnées projet | réussi |
| contrôle des licences et notices | réussi après ajout de Pyright |
| inventaire de tests généré | à jour |
| `python run_tests.py standard` | 1 508 réussis, 15 ignorés sur l'état final |
| `python run_tests.py coverage` | 1 508 réussis, 15 ignorés ; 85,87 % sur l'état final |
| `python run_tests.py validation` | 65 réussis |
| `python run_tests.py extensive` | 1 512 réussis, 6 ignorés au point de contrôle précédant 5 nouveaux cas standard |
| Sphinx HTML, `-W --keep-going` | réussi |
| Sphinx linkcheck, `-W --keep-going` | réussi |
| `pip check` | aucune exigence cassée |
| `pip-audit --local --skip-editable` | aucune vulnérabilité connue |
| construction wheel + sdist | réussie |
| `twine check` | deux artefacts acceptés |

## 12. Complément : exemples et études de site

L'audit complémentaire de `examples/`, `sites/` et des scripts de
qualification a conduit aux changements ciblés suivants :

- `build_multichain_archive.py` reste la façade en ligne de commande, tandis
  que les chemins d'archive, la validation des preuves et la vérification du
  ZIP sont isolés dans trois modules nommés par responsabilité ;
- le post-traitement HYP-26-0172 sépare désormais l'extraction des résultats
  natifs, les figures construites depuis les tables dérivées et l'orchestration
  de l'ensemble ;
- les diagnostics historiques de la reproduction temporelle de Ploemeur et
  les quatre tracés du benchmark local Holten ont été sortis des scripts
  scientifiques principaux sans modifier leurs formules ni leurs fichiers de
  sortie ;
- les scripts d'article, de release et de qualification partagent les mêmes
  fonctions de hachage, de requête Git, de tableau Markdown et, pour le nouveau
  code, les diagnostics MCMC canoniques du paquet ;
- les fonctions longues qui coordonnent préparation, calibration, comparaison
  et écriture dans les exemples Holten/Ploemeur disposent maintenant de
  docstrings expliquant leur rôle scientifique, pas seulement leur opération
  Python immédiate.

La documentation Sphinx contient un index court des études de site qui renvoie
vers les README locaux canoniques. Elle précise aussi que `examples/`, `sites/`
et `scripts/` nécessitent le dépôt source et ne constituent pas l'API installée
par la wheel. Le workflow extensif est déclenché par les scripts, YAML, tables,
classeurs et études de site concernés, ainsi que par les helpers qui construisent
l'archive de qualification. Ces chemins sont vérifiés par un test de contrat.

Le contrôle progressif des docstrings couvre maintenant ces nouveaux modules
maintenus. Le périmètre Pyright gagne également le helper stable de provenance,
avec un contrat typé distinct pour les sorties Git texte et binaires.

Après ces changements, Ruff, le formatage, Pyright et le contrôle de docstrings
passent. La construction Sphinx stricte des 124 sources réussit. La suite
standard donne 1 508 tests réussis et 15 ignorés ; 74 tests ciblés couvrant les
archives, les helpers d'article, Holten, Ploemeur temporel et HYP-26-0172
réussissent également.

## Verdict final

La complexité actuelle est principalement la conséquence justifiée d'un outil
scientifique complet et reproductible, et non d'une architecture inutilement
abstraite. Le code est assez grand parce qu'il porte plusieurs modèles,
plusieurs protocoles d'inférence, des validations défensives, des résultats
auditables et une interface utilisateur complète.

Le risque principal était la concentration de responsabilités. Il est réduit
par des extractions privées ciblées, tout en conservant des façades stables et
simples. La dette restante est réelle mais localisée, mesurée et sans urgence de
refonte générale. Les prochaines améliorations doivent rester petites,
motivées par un invariant ou une duplication concrète, et protégées par un test
avant tout nouveau découpage.
