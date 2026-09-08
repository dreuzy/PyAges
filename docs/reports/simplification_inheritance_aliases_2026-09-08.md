# Audit de simplification : héritage et alias — 8 septembre 2026

## Conclusion

Cette itération supprime les couches de compatibilité et les héritages qui ne
représentaient pas une relation métier. Le code exécutable n'accepte désormais
qu'un vocabulaire de configuration, et une exécution Metropolis-Hastings (MH)
d'une seule chaîne est exactement le cas `chains: 1` du moteur commun.

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

## Héritages conservés et raison

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

## Suite de l'audit de simplification

### Priorité 1 — unifier le dernier orchestrateur MH Ploemeur

`PloemeurSingleRun` utilise le même `MetropolisHastingsRunner`, mais répète
encore la construction des répertoires de phases, l'écriture et le contrôle de
qualification déjà présents dans `pyages.workflows.runtime.mh`. La prochaine
itération devrait étendre proprement ce service pour accepter le prior empirique
Ploemeur, puis supprimer cette orchestration parallèle.

Gain attendu : une seule définition des phases `initialization`, `pilot` et
`production`, et une seule gestion de l'échec de convergence.

### Priorité 2 — terminer le vocabulaire des sorties temporelles

Le YAML dit désormais `posterior_draw_count`, mais plusieurs fonctions internes
de tracé utilisent encore le paramètre `lpm_number`. Ce n'est plus un alias
public de configuration, mais le nom reste peu explicite. Il peut être renommé
de bout en bout dans `pyages.reporting` et dans les scripts, sans conserver
l'ancien nom.

### Priorité 3 — découper les gros modules par responsabilité

- `sites/ploemeur/workflows/ploemeur_workflow.py` dépasse 900 lignes et réunit
  sélection des cas, chemins, préparation et exécution ;
- `pyages/config/models.py` dépasse 500 lignes et peut devenir trois modules :
  champs MH communs, schéma single-date et schéma temporel ;
- les plus grandes fonctions de production sont actuellement les trois tracés
  `plot_observations_overview`, `plot_objective_solution_map` et
  `plot_single_date_model_space` (environ 120 lignes chacune).

Le découpage doit suivre les responsabilités et conserver les calculs
scientifiques visibles. Découper seulement pour réduire un compteur de lignes
créerait davantage de navigation sans rendre le code plus simple.

### Priorité 4 — traiter séparément les grands scripts de reproduction

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
- suite standard : 1 664 tests réussis et 22 ignorés ;
- documentation Sphinx reconstruite en mode strict, sans avertissement.

Le lanceur agrégé `check_dev full` s'arrête néanmoins à `pip check` dans
l'environnement utilisateur employé pour cet audit : un paquet global non
déclaré par PyAges, `sphinx-design 0.6.1`, est incompatible avec Sphinx 9.1.
Les dépendances directes déclarées par le projet passent leur contrôle de
métadonnées, et la documentation se construit effectivement avec Sphinx 9.1.
Le paquet global n'a pas été désinstallé, car il peut appartenir à un autre
projet ; un environnement virtuel neuf installé avec les contraintes PyAges ne
contient pas cette dépendance étrangère.
