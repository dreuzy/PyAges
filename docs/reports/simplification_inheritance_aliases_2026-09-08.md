# Audit de simplification : reliquats des versions passées — 8 septembre 2026

## Conclusion

Ici, « héritage » désigne le **code ancien encore conservé pour continuer à
accepter d'anciens noms, formats ou chemins d'exécution**. Il ne désigne pas
l'héritage entre classes Python.

Cette itération retire ces couches de compatibilité actives. Le code exécutable
n'accepte désormais qu'un vocabulaire de configuration, et une exécution
Metropolis-Hastings (MH) d'une seule chaîne est exactement le cas `chains: 1`
du moteur commun.

Ces ruptures justifient une version **2.0**, et non 1.3. Elles retirent des noms,
des commandes et des classes que du code externe pouvait encore appeler.

## Ce qui a été supprimé

### Compatibilité de configuration

- suppression de `pyages/config/migration.py` et de la commande
  `pyages config migrate` ;
- suppression des conversions implicites d'anciens noms et des heuristiques de
  chemins dépendant de la racine du dépôt ;
- un seul contrat exécutable : `schema_version: 3`, avec tous les chemins
  relatifs résolus depuis le répertoire du YAML ;
- conversion des exemples, profils Ploemeur et profils archivés encore testés
  vers ce contrat.

Un ancien fichier échoue donc clairement au chargement. Cette erreur est plus
sûre qu'une traduction silencieuse dont le résultat scientifique pourrait être
mal compris.

### Une ou plusieurs chaînes MH

Les classes `MHCalibrationCfg`, `SingleDateMetropolisCfg` et
`TemporalMetropolisCfg` ont été remplacées par une seule classe
`MetropolisHastingsCfg`. Les workflows single-date, temporel et Ploemeur
composent tous cette même configuration.

Le nombre de chaînes est un entier :

```yaml
calibration:
  metropolis_hastings:
    chains: 1  # une chaîne
```

Passer à 4 ne change ni de modèle de configuration ni de moteur. Cela ajoute
des chaînes indépendantes et rend applicables les diagnostics inter-chaînes.

Les options qui ne décrivent pas MH sont sorties de son bloc :

- `exploration_resolution` prépare le problème temporel ;
- `posterior_draw_count` choisit le nombre de tirages utilisés dans les sorties ;
- `prior_option` exprime maintenant explicitement le choix scientifique du
  prior, y compris dans un workflow temporel.

### Algorithmes de calibration

`CalibrationMethod` était une classe abstraite mêlant quatre responsabilités :
liaison au problème, calcul, affichage et écriture. Elle a été supprimée.
`Simplex` et `MetropolisHastings` sont maintenant des classes indépendantes :

- elles reçoivent un `CalibrationProblem` par composition ;
- elles satisfont le `CalibrationAlgorithm` de façon structurelle ;
- l'affichage et l'écriture restent des services de `calibration.outputs` ;
- les méthodes relais `write_calibrated_lpm()`, `display_lpms()` et
  `write_results_spec()` n'existent plus.

Un `Protocol` sert uniquement à expliquer au vérificateur de types quelles
opérations sont attendues. Il n'ajoute aucun comportement et ne crée pas de
classe parent à l'exécution.

### Modèles inverse-gaussiens et alias locaux

La classe privée `_InverseGaussianLpmBase` ne partageait qu'un calcul de
quantile. Elle est remplacée par la fonction `inverse_gaussian_quantiles()`.
Les deux modèles héritent directement de `LpmScipy`, comme les autres lois
continues basées sur SciPy.

Les doubles noms locaux sans sémantique propre ont aussi été retirés :
`ROOT = REPO_ROOT`, `REPO_ROOT = SOURCE_REPOSITORY_ROOT` et
`FRACTION_COLUMNS = BIN_ORDER`. L'inventaire syntaxique ne trouve plus
d'affectation de ce type au niveau module dans le paquet `pyages`.

Le post-traitement HYP-26-0172 n'écrit plus simultanément `success_rate` et
`mean_acceptance_rate`, et ne traduit plus les anciens résumés mono-chaîne. Il
exige le schéma de résultat courant et échoue en nommant les champs manquants.

### Derniers adaptateurs de compatibilité actifs

La dernière passe a également supprimé les reliquats suivants :

- le sampler et Simplex utilisent uniquement `acceptance_rate` et
  `runtime_seconds` ; `success_rate` et `time_perform` ne sont ni écrits ni
  exposés par des propriétés de transition ;
- l'enregistrement détaillé d'une trajectoire bas niveau s'appelle
  `record_trajectory`. Le workflow décide séparément d'afficher ou non une
  figure avec `display_traj` ;
- les scripts scientifiques importent directement les diagnostics MCMC du
  cœur. La façade `scripts/common/mcmc_diagnostics.py`, qui réexportait ces
  fonctions sous un second chemin, est supprimée ;
- `posterior_draw_count` est maintenant le seul nom utilisé depuis le YAML
  jusqu'aux fonctions de sélection et de tracé ; l'ancien nom interne
  `lpm_number` n'est pas conservé ;
- une table de concentrations de référence doit contenir `observation_key`.
  L'appariement implicite par position, qui pouvait devenir faux après un tri,
  est supprimé ; un objet `Concentrations` reste accepté parce qu'il produit
  lui-même ces identifiants ;
- le générateur de l'audit final exige les champs courants `nsteps` et `chains`
  dans les manifestes et écrit `nsteps`. Il ne devine plus `mh_nsteps` et ne
  suppose plus silencieusement une chaîne ;
- le lanceur de matrice HYP-26-0172 accepte seulement `--nsteps` ; son alias
  `--mh-nsteps` est supprimé ;
- les trois expériences désactivées décrites comme des alias de `main_F09` ou
  `main_F11` ont été retirées de la matrice HYP-26-0172, avec leurs fichiers de
  configuration non référencés. Les exemples utilisent maintenant une
  expérience principale active.

## Ce qui n'est pas un reliquat de compatibilité

Les relations entre classes Python ne sont plus un objectif de suppression en
elles-mêmes. Elles restent seulement lorsqu'elles portent un contrat actuel :

| Famille | Pourquoi elle reste |
|---|---|
| modèles Pydantic vers `BaseConfigModel` | Pydantic utilise cette classe de base pour appliquer validation stricte et refus des champs inconnus ; les petites bases dupliquées des configurations Ploemeur et Holten ont été supprimées au profit de cette base unique |
| modèles LPM vers `LpmBase` ou `LpmScipy` | il s'agit d'une vraie famille substituable utilisée par le registre et la convolution ; `LpmScipy` mutualise effectivement PDF, CDF, quantile, moyenne et écart-type |
| `Protocol` | contrat de typage structurel, sans héritage de comportement |
| exceptions vers `Exception`, `ValueError` ou `RuntimeError` | nécessaire pour permettre aux appelants d'intercepter une catégorie d'échec précise |
| `Enum`, `TypedDict`, `NamedTuple` | mécanismes standards de données et de typage, pas couches de compatibilité |
| `FrozenMapping` vers `Mapping` | fournit réellement le protocole complet d'une table immuable sérialisable |

Supprimer ces relations remplacerait un contrat explicite par des tests de type
manuels ou du code dupliqué. Ce serait une complication, pas une simplification.

Deux autres catégories restent volontairement présentes :

- les répertoires `archive/`, `docs/archive/`, les rapports datés et les scripts
  dont la finalité explicite est de comparer une campagne actuelle à une
  campagne passée constituent des **preuves scientifiques**. Ils ne sont pas
  chargés comme solutions de repli par le cœur ;
- les noms de canaux TracerLPM correspondent aux emplacements réellement
  imposés par le classeur externe. Ce sont des correspondances à la frontière
  d'un autre logiciel, pas des alias de l'API PyAges.

## Suite de l'audit de simplification

### Priorité 1 — achevée : unifier le dernier orchestrateur MH Ploemeur

`execute_mh_run()` est maintenant l'unique service qui construit les
répertoires de phases, appelle `MetropolisHastingsRunner`, écrit le résultat et
transforme un refus de qualification en erreur après conservation des preuves.
Le constructeur commun `build_mh_config()` accepte aussi la source de prior
empirique nécessaire à Ploemeur.

`PloemeurSingleRun` ne reproduit plus aucune de ces étapes. Il prépare le
problème scientifique, délègue l'exécution commune, puis produit seulement les
chroniques, histogrammes et comparaisons de prior propres au site.

### Priorité 2 — achevée : nettoyer la matrice d'étude courante

La matrice HYP-26-0172 ne contient plus les trois expériences désactivées qui
étaient qualifiées d'alias redondants. Les dix expériences restantes ont une
fonction scientifique distincte et une configuration directement référencée.

### Priorité 3 — en cours : découper les gros modules par responsabilité

- l'exécution d'un cas a été extraite de
  `sites/ploemeur/workflows/ploemeur_workflow.py` vers `single_run.py`. Le
  premier module est passé de 893 à 673 lignes et se concentre davantage sur
  la sélection et l'enchaînement des cas ;
- `pyages/config/models.py` dépasse 500 lignes et peut devenir trois modules :
  champs MH communs, schéma single-date et schéma temporel ;
- les plus grandes fonctions de production sont actuellement les trois tracés
  `plot_observations_overview`, `plot_objective_solution_map` et
  `plot_single_date_model_space` (environ 120 lignes chacune).

Le découpage doit suivre les responsabilités et conserver les calculs
scientifiques visibles. Découper seulement pour réduire un compteur de lignes
créerait davantage de navigation sans rendre le code plus simple.

### Priorité 4 — en cours : traiter séparément les reproductions historiques

Les diagnostics figés de la Figure 4 se trouvent maintenant sous
`examples/natural/ploemeur_temporal/article_reproduction/diagnostics.py`.
L'ancien chemin n'est pas réexporté. Le nom du répertoire rend visible que ces
formules servent à retrouver un article et ne doivent pas être choisies pour un
nouveau workflow, qui utilise `pyages.calibration.methods.mh.diagnostics`.

Plusieurs générateurs de rapports scientifiques font entre 150 et 500 lignes
par fonction. Ils passent les contrôles de complexité actuels, car leur longueur
vient surtout d'étapes séquentielles. On peut extraire les lectures, calculs et
écritures répétées, mais il faut préserver la traçabilité d'une campagne. Cette
priorité vient après l'unification du code de production.

## Critères pour la prochaine itération

Une simplification sera retenue si elle enlève une source de vérité, une branche
d'exécution ou un vocabulaire concurrent. Elle ne sera pas retenue si elle ne
fait que déplacer le même état dans davantage de fichiers. Les tests devront
continuer à démontrer : validation stricte, problème frais par chaîne,
qualification avant regroupement et publication atomique des résultats.

## Validation

Les contrôles ciblés de configuration, calibration, modèles IG, workflows et
profils Ploemeur passent. La validation finale donne aussi :

- Ruff : lint et format sans écart ;
- Pyright : 0 erreur et 0 avertissement ;
- inventaire des tests à jour ;
- suite standard complète : 1 665 tests réussis et 22 ignorés ;
- après le retrait final des trois entrées de matrice, les 47 tests ciblant
  l'étude Ploemeur, les scripts d'article et leurs contrats documentaires
  réussissent ;
- après l'unification finale de l'orchestrateur, 88 tests ciblés réussissent et
  2 tests extensifs sont ignorés dans le profil standard ;
- le smoke test extensif du workflow Ploemeur exécute réellement quatre chaînes
  puis publie leur résultat regroupé : 1 test réussi ;
- documentation Sphinx reconstruite en mode strict, sans avertissement.

La passe avec les cas extensifs activés a d'abord donné 1 678 réussites,
6 tests ignorés et 2 échecs. Les deux échecs provenaient exclusivement de
cellules de notebooks restées sur `write_calibrated_lpm` et `explo_res`. Après
leur migration vers `write_calibrated_result` et `exploration_resolution`, la
réexécution isolée des deux notebooks passe : 4 tests réussis, dont les deux
exécutions scientifiques complètes.

Le lanceur agrégé `check_dev full` s'arrête néanmoins à `pip check` dans
l'environnement utilisateur employé pour cet audit : un paquet global non
déclaré par PyAges, `sphinx-design 0.6.1`, est incompatible avec Sphinx 9.1.
Les dépendances directes déclarées par le projet passent leur contrôle de
métadonnées, et la documentation se construit effectivement avec Sphinx 9.1.
Le paquet global n'a pas été désinstallé, car il peut appartenir à un autre
projet ; un environnement virtuel neuf installé avec les contraintes PyAges ne
contient pas cette dépendance étrangère.
