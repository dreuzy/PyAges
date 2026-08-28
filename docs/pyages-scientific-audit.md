# Audit scientifique de PyAges — clôture du 28 août 2026

## Statut

L'audit intrinsèque du paquet PyAges est clos sur le code et les données
distribuées. Le diagnostic historique qui occupait précédemment ce fichier est
conservé dans l'historique Git ; les contrats normatifs actuels sont décrits
dans {doc}`scientific-methods`, {doc}`science/forward-model`,
{doc}`science/lpm-reference` et {doc}`science/validation`.

Cette clôture ne vaut pas validation hydrogeologique universelle. Elle signifie
que chaque anomalie démontrée par l'audit possède désormais une décision
explicite, une implémentation et une preuve automatisée adaptée.

## Périmètre et méthode

L'audit couvre :

- les paramètres, supports, moments et quantiles des LPM ;
- les chroniques, unités, constantes de décroissance et politiques hors
  domaine des traceurs ;
- la troncature, la masse couverte et la précision de la convolution ;
- les erreurs d'observation, objectifs et frontières de calibration ;
- la provenance des entrées et transformations des workflows publics ;
- les tests analytiques, calculs indépendants, golden tests et validations
  croisées qui protègent ces contrats.

Les golden tests servent à la non-régression après les invariants analytiques ;
ils ne constituent jamais seuls une preuve de justesse scientifique.

## Matrice de clôture

| Priorité | Anomalie ou action | Décision appliquée | Preuve principale | Statut |
| --- | --- | --- | --- | --- |
| P0 | Tests scientifiques indépendants | Identités analytiques, quadratures indépendantes et contrats de frontières ajoutés | `tests/lpm/`, `tests/tracer/`, `tests/convolution/test_convolution_scientific.py` | Clos |
| P0 | CSV sans en-tête et chroniques ambiguës | Schéma `date,concentration`, validation, tri et politiques hors domaine explicites | `tests/tracer/test_distributed_tracer_contracts.py`, `tests/tracer/test_tracer_root.py` | Clos |
| P0 | Constantes radioactives ambiguës | Champs exclusifs `half_life`/`decay_mean_lifetime`, conversion unique en taux, demi-vies publiées dans les YAML | `pyages/tracer/decay.py`, `tests/tracer/test_decay_contract.py` | Clos |
| P0 | Paramétrisation inverse Gaussian | `mu` et `sigma` sont les moyenne et écart-type physiques ; conversion SciPy interne et testée | `tests/lpm/test_inverse_gaussian_analytics.py` | Clos |
| P1 | Quantile `dirac_double` | Deuxième atome à `mu1 + mu2`, quantile généralisé droit et unités corrigées | `tests/lpm/test_discrete_lpm_analytics.py` | Clos |
| P1 | Contrat `mix_exp_shifted` | Masse de Dirac, composante exponentielle, moments, CDF, quantile et unité du poids unifiés | `tests/lpm/test_discrete_lpm_analytics.py`, `tests/convolution/test_convolution_scientific.py` | Clos |
| P1 | Unités et erreurs avant calibration | Unités canoniques vérifiées une fois ; erreurs effectives strictement positives avant le noyau objectif | `tests/concentrations/test_concentration_contracts.py`, `tests/calibration/test_calibration_problem.py` | Clos |
| P1 | Imputation d'erreurs invisible | `missing_error_rel` configuré explicitement ; transformations et lignes touchées consignées dans le manifeste | `tests/workflows/test_single_date_workflow.py`, `tests/workflows/test_temporal_components.py` | Clos |
| P1 | Troncature et précision de convolution | Masse de fenêtre, diagnostics, grille adaptative et quadratures de référence disponibles sans renormalisation cachée | `pyages/convolution/`, `tests/convolution/test_convolution_scientific.py` | Clos |
| P1 | Moments numériques génériques | Moments requis par contrat ; implémentations analytiques ou moments partiels exacts pour les modèles distribués | `tests/lpm/test_lpm_moments_golden.py`, `tests/convolution/test_convolution_scientific.py` | Clos |
| P2 | `print`/`sys.exit` dans les chemins scientifiques | Les erreurs du cœur lèvent des exceptions ; le résumé MH retourne des données et utilise le journal. Les sorties restantes sont limitées aux couches CLI, affichage et reporting | `pyages/calibration/methods/mh/trajectory.py`, `tests/cli/test_cli_diagnostics.py` | Clos |
| P2 | Variantes ¹⁴C | Trois identifiants intentionnels : recharge constante `14C`, chroniques zonales `14C_NH` et `14C_SH`; un seul YAML canonique par répertoire et demi-vie 5730 ans | `data_core/README.md`, `tests/tracer/test_distributed_tracer_contracts.py` | Clos |

## Contrats scientifiques résultants

### LPM

Chaque modèle expose des paramètres finis et bornés, leurs unités, une CDF
cohérente, un quantile généralisé et des moments compatibles avec sa nature
continue, discrète ou mixte. L'inverse Gaussian utilise des moments physiques,
pas les paramètres bruts de `scipy.stats.invgauss`.

### Traceurs et ¹⁴C

La décroissance utilise un taux dérivé une seule fois de la demi-vie ou du
temps de vie moyen, jamais des deux. `14C` modélise une recharge constante à
100 pmC pour les cas qui font cette hypothèse ; `14C_NH` et `14C_SH` conservent
les chroniques zonales et leur provenance. Ces identifiants ne sont pas des
alias interchangeables.

### Convolution

La masse plus ancienne que l'historique disponible est omise sans
renormalisation silencieuse. `window_mass` et les diagnostics exposent la masse
représentée, tandis que les tests comparent les chemins rapides à des solutions
analytiques ou des quadratures indépendantes.

### Erreurs d'observation

Les erreurs saisies restent inchangées lorsqu'elles sont positives. Le
workflow temporel peut appliquer `error_rel` à toutes les observations si une
erreur manque. Toute erreur encore nulle est remplie par
`missing_error_rel * moyenne_du_traceur`; la valeur par défaut explicite est
0,01. Les erreurs effectives sont écrites dans `concentrations.txt` et chaque
transformation figure dans `details.observation_error_policy` du manifeste.

## Portes de validation

La clôture opérationnelle exige, sur un même état Git stabilisé :

1. Ruff lint et format ;
2. inventaire de tests régénéré et vérifié ;
3. suite standard et couverture de branches au-dessus de 75 % ;
4. cinq tests scientifiques `extensive` ;
5. construction Sphinx stricte ;
6. audit de dépendances, métadonnées de licence et paquet construit ;
7. matrice CI Python 3.12–3.14 et bornes basses après publication du commit.

L'exécution locale de clôture du 28 août 2026 a validé les six premières
portes : Ruff sur 467 fichiers, inventaire courant, 1 078 tests standard
réussis et 5 ignorés, couverture de branches à 85,77 %, 5 tests extensifs
réussis, Sphinx HTML et `linkcheck` stricts, absence de vulnérabilité connue,
licences cohérentes, puis sdist et wheel acceptés par `twine check`. La matrice
multi-version reste volontairement une preuve CI post-commit.

Les validations externes de l'article, l'archive immuable et le DOI restent des
portes de publication distinctes ; elles ne rouvrent pas l'audit intrinsèque du
code.
