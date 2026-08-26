# Qualification finale des proposals Metropolis–Hastings

> **Statut : qualification pilote historique.** La campagne de production
> demandée à la fin de ce rapport a ensuite été exécutée sur les 19 cas : cinq
> chaînes par cas, split-Rhat final inférieur à 1,01 et ESS agrégé minimal de
> 756. Le protocole et l’interprétation actuels sont résumés dans
> {doc}`../science/inference` et {doc}`../science/validation`. Les réponses
> ci-dessous sont conservées dans leur contexte décisionnel initial.

## Décision

Sur les quatre cas pilotes et cinq seeds, la configuration classée première est **`correlated_1p68`**. Son split-Rhat maximal vaut **1.0035**, son ESS minimal observé **360.4**, et son ESS/s médian **12.72**, contre respectivement **1.0143**, **36.2** et **1.43** pour `(1.5,1.5)`. Le gain médian d'ESS/s est **×8.89**.

Cette qualification ne recalcule volontairement ni les 19 cas de Table 3, ni Figure 2 finale, ni le manuscrit. Elle fournit d'abord les résultats pilotes demandés pour validation.

## Traçabilité et invariants

- Commit au début de la tâche : `a0cf3b95e0327ad16069cb57b37e87522416d481`. Un commit concurrent a ensuite fait avancer `HEAD`; le détail au démarrage de la campagne est dans `preflight.json`.
- Environnement : Python 3.12.4, NumPy 2.1.2, SciPy 1.14.1.
- Données : concentrations synthétiques non bruitées, CFC-11/CFC-12/CFC-113/SF6, 2010, erreur relative 8 %.
- Cible inchangée : même shifted exponential, likelihood, absence de prior, bounds `[0.1,70] × [0,70]`, forward CDF–partial-first-moment et initialisation `(10,10)`.
- Production : 10 000 itérations, burn-in 20 %, chaque état post-burn-in stocké, aucun thinning diagnostique, seeds 31001, 31002, 31003, 31004, 31005.
- Covariance : pilote historique de 4000 itérations, seed 27001, burn-in 20 %, covariance empirique en `(mu,t0)`, ridge relatif `1e-06`, puis covariance figée en production.
- Transformation : `m=mu+t0`, `d=mu-t0`; inverse `mu=(m+d)/2`, `t0=(m-d)/2`; `|d(mu,t0)/d(m,d)|=1/2`, constant. Il s'annule dans le rapport MH et les bounds restent testés en coordonnées physiques.
- Empreintes exactes des scripts/configurations : `results/mh_proposal_qualification/preflight.json`.

## Proposals comparés

| configuration | strategy | scale | acceptance_mean | max_split_rhat | min_ess | median_ess | median_ess_per_second | max_median_interseed_sd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| correlated_1p68 | pilot_covariance | s=2.38/sqrt(2) | 0.3166 | 1.0035 | 360.3555 | 814.0493 | 12.721 | 0.2665 |
| correlated_2p4 | pilot_covariance | s=2.4 | 0.2047 | 1.0028 | 342.6632 | 715.3957 | 11.8054 | 0.4067 |
| correlated_1 | pilot_covariance | s=1 | 0.5059 | 1.0034 | 290.8161 | 627.0071 | 8.0068 | 0.308 |
| correlated_0p75 | pilot_covariance | s=0.75 | 0.6058 | 1.0021 | 163.6394 | 499.7213 | 6.2634 | 0.257 |
| md_2_4 | sum_difference | m=2,d=4 | 0.359 | 1.0092 | 57.5893 | 233.4369 | 3.5696 | 0.2614 |
| md_3_6 | sum_difference | m=3,d=6 | 0.2397 | 1.0098 | 62.8896 | 269.1928 | 3.2207 | 0.5907 |
| diagonal_4 | diagonal | (4,4) | 0.1529 | 1.0072 | 59.5322 | 203.5699 | 3.0913 | 0.5241 |
| md_4_8 | sum_difference | m=4,d=8 | 0.1707 | 1.011 | 66.4697 | 238.3334 | 3.1058 | 0.713 |
| diagonal_3 | diagonal | (3,3) | 0.2136 | 1.0212 | 54.5932 | 161.8232 | 2.4989 | 1.3983 |
| diagonal_2 | diagonal | (2,2) | 0.3204 | 1.0222 | 39.7672 | 112.2389 | 1.6438 | 0.712 |
| historical_1p5 | historical | (1.5,1.5) | 0.4086 | 1.0143 | 36.1856 | 89.8048 | 1.4303 | 0.4276 |

Le classement privilégie d'abord `Rhat < 1.01`, puis ESS/s et ESS; l'acceptance n'intervient pas comme critère primaire.

## Temps de calcul

| configuration | strategy | scale | runs | runtime_median_seconds | runtime_min_seconds | runtime_max_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| correlated_2p4 | pilot_covariance | s=2.4 | 20 | 62.9617 | 56.3785 | 3472.7154 |
| historical_1p5 | historical | (1.5,1.5) | 20 | 63.9892 | 56.2559 | 91.7974 |
| correlated_1p68 | pilot_covariance | s=2.38/sqrt(2) | 20 | 64.3573 | 60.0568 | 3469.8859 |
| diagonal_4 | diagonal | (4,4) | 20 | 65.0382 | 61.6436 | 83.2191 |
| md_4_8 | sum_difference | m=4,d=8 | 20 | 65.6723 | 59.6805 | 86.6041 |
| md_3_6 | sum_difference | m=3,d=6 | 20 | 65.7112 | 58.7534 | 91.644 |
| diagonal_3 | diagonal | (3,3) | 20 | 66.227 | 62.134 | 82.682 |
| correlated_0p75 | pilot_covariance | s=0.75 | 20 | 66.9163 | 62.7576 | 124.1095 |
| correlated_1 | pilot_covariance | s=1 | 20 | 66.9909 | 61.1465 | 104.8941 |
| md_2_4 | sum_difference | m=2,d=4 | 20 | 68.0811 | 62.1262 | 90.5346 |
| diagonal_2 | diagonal | (2,2) | 20 | 70.5142 | 62.9701 | 93.0104 |

Les temps sont des temps muraux par chaîne sous charge concurrente du workspace. Quelques maxima reflètent une contention externe; le classement utilise donc la médiane d'ESS/s sur les répétitions, pas le maximum ni la moyenne brute de runtime.

## Figure 2 : `(mu,t0)=(10,30)`

| configuration | strategy | scale | iact_mtt | iact_mu | iact_t0 | ess_mtt | ess_mu | ess_t0 | ess_per_second_mtt | ess_per_second_mu | ess_per_second_t0 | acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| correlated_0p75 | pilot_covariance | s=0.75 | 24.7256 | 25.482 | 26.3509 | 323.5115 | 313.9077 | 303.5573 | 5.0075 | 4.8588 | 4.6986 | 0.579 |
| correlated_1 | pilot_covariance | s=1 | 20.4954 | 19.0041 | 21.3757 | 390.2836 | 420.9101 | 374.2102 | 6.1053 | 6.5844 | 6.0418 | 0.4779 |
| correlated_1p68 | pilot_covariance | s=2.38/sqrt(2) | 13.2334 | 13.031 | 13.0582 | 604.4539 | 613.8429 | 612.5669 | 9.8619 | 9.8092 | 9.9061 | 0.2964 |
| correlated_2p4 | pilot_covariance | s=2.4 | 14.5484 | 14.0313 | 13.1584 | 549.8217 | 570.0837 | 607.9006 | 8.6274 | 9.0482 | 9.6484 | 0.1931 |
| diagonal_2 | diagonal | (2,2) | 106.9362 | 108.4313 | 108.6423 | 74.8016 | 73.7702 | 73.6269 | 1.1578 | 1.1419 | 1.1058 | 0.1857 |
| diagonal_3 | diagonal | (3,3) | 94.0128 | 98.538 | 97.1746 | 85.0841 | 81.1768 | 82.3158 | 1.344 | 1.2823 | 1.3002 | 0.1218 |
| diagonal_4 | diagonal | (4,4) | 70.3962 | 73.0132 | 70.4269 | 113.6282 | 109.5555 | 113.5787 | 1.7763 | 1.7127 | 1.7755 | 0.0836 |
| historical_1p5 | historical | (1.5,1.5) | 181.4624 | 194.6365 | 187.692 | 44.0808 | 41.0971 | 42.6177 | 0.7485 | 0.6978 | 0.7236 | 0.2489 |
| md_2_4 | sum_difference | m=2,d=4 | 69.0869 | 71.2119 | 66.0673 | 115.7817 | 112.3267 | 121.0736 | 1.6992 | 1.7248 | 1.8365 | 0.2229 |
| md_3_6 | sum_difference | m=3,d=6 | 62.373 | 63.8075 | 61.6138 | 128.2446 | 125.3614 | 129.8248 | 1.9591 | 1.9151 | 1.9832 | 0.1397 |
| md_4_8 | sum_difference | m=4,d=8 | 56.6671 | 54.2813 | 50.767 | 141.1577 | 147.3619 | 157.5631 | 2.2334 | 2.2967 | 2.4557 | 0.0971 |

Corrélation postérieure et stabilité entre seeds :

| configuration | correlation_mean | correlation_sd |
| --- | --- | --- |
| correlated_1p68 | -0.9709 | 0.001 |
| historical_1p5 | -0.9699 | 0.002 |

Figures diagnostiques :

- `figures/figure2_trace_comparison.png`
- `figures/figure2_acf_comparison.png`
- `figures/figure2_posterior_cloud_comparison.png`

## Stabilité de la distribution cible

Écarts maximaux seed-par-seed entre le meilleur proposal et le proposal historique :

| parameter | max_abs_median_delta | max_abs_mean_delta | max_abs_sd_delta | max_abs_q10_delta | max_abs_q90_delta |
| --- | --- | --- | --- | --- | --- |
| mtt | 1.3662 | 1.2679 | 0.7805 | 1.5535 | 1.6535 |
| mu | 2.1654 | 2.0294 | 0.9551 | 2.6488 | 2.564 |
| t0 | 0.7942 | 0.7616 | 0.3177 | 0.9526 | 1.0487 |

Après agrégation des cinq chaînes de chaque proposal (comparaison moins sensible à un seed isolé) :

| parameter | max_abs_median_delta | max_abs_sd_delta | max_abs_q10_delta | max_abs_q90_delta |
| --- | --- | --- | --- | --- |
| mtt | 0.8493 | 0.3074 | 1.0248 | 0.7474 |
| mu | 1.3531 | 0.3744 | 1.6575 | 1.1185 |
| t0 | 0.466 | 0.158 | 0.429 | 0.6112 |

Comparaison directe aux résumés actuellement publiés (`seed=12345`, 10 000 pas, stockage 1/5) :

| case | parameter | median_published | median_best | delta_median | q10_published | q10_best | q90_published | q90_best | sd_published | sd_best | abs_median_delta_over_published_sd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| very_sharp | mu | 1.6218 | 1.6744 | 0.0526 | 0.3802 | 0.3687 | 4.2795 | 4.1609 | 1.6243 | 1.518 | 0.0324 |
| very_sharp | t0 | 1.5427 | 1.387 | -0.1557 | 0.2757 | 0.2346 | 3.8461 | 3.5697 | 1.4458 | 1.3279 | 0.1077 |
| very_sharp | mtt | 3.6494 | 3.5442 | -0.1052 | 1.7318 | 1.6146 | 6.3855 | 5.9136 | 1.7725 | 1.6691 | 0.0594 |
| young_intermediate | mu | 10.1988 | 10.4327 | 0.2338 | 6.3321 | 6.51 | 15.3759 | 14.796 | 3.4127 | 3.226 | 0.0685 |
| young_intermediate | t0 | 9.7617 | 9.6346 | -0.1271 | 5.4179 | 5.9135 | 13.6333 | 13.4194 | 3.0973 | 2.9368 | 0.041 |
| young_intermediate | mtt | 20.152 | 20.1861 | 0.0341 | 18.7155 | 18.7664 | 21.7639 | 21.756 | 1.2086 | 1.1866 | 0.0282 |
| figure2 | mu | 10.4254 | 10.5035 | 0.078 | 3.5849 | 5.3094 | 16.5039 | 16.2099 | 4.9008 | 4.2821 | 0.0159 |
| figure2 | t0 | 29.8329 | 29.7636 | -0.0694 | 27.3403 | 27.4225 | 33.7678 | 32.7216 | 2.4799 | 2.0906 | 0.028 |
| figure2 | mtt | 40.2996 | 40.2653 | -0.0343 | 37.4191 | 37.9355 | 43.8608 | 43.7129 | 2.5478 | 2.3078 | 0.0135 |
| long | mu | 41.3067 | 41.4176 | 0.1109 | 32.4507 | 32.6543 | 52.1779 | 51.3422 | 7.6527 | 7.2509 | 0.0145 |
| long | t0 | 9.527 | 9.5625 | 0.0355 | 5.7885 | 6.1339 | 12.9714 | 12.8595 | 2.6986 | 2.6083 | 0.0132 |
| long | mtt | 50.704 | 50.9345 | 0.2305 | 45.1516 | 45.2585 | 58.4976 | 57.7083 | 5.1473 | 4.841 | 0.0448 |

Le plus grand déplacement de médiane vaut **0.108 SD posterior publiée**; le plus grand déplacement parmi médiane et quantiles vaut **0.509 SD**. Les différences seed-par-seed les plus grandes proviennent donc principalement de l'erreur Monte Carlo du proposal historique; le nouveau proposal ne modifie pas la cible mais peut modifier certaines valeurs tabulées insuffisamment convergées.

Ces écarts doivent être interprétés conjointement avec l'ESS, Rhat et la variabilité inter-seed. Un écart qui dépasse l'incertitude Monte Carlo historique ne constitue pas à lui seul une preuve de changement de cible; les tests unitaires confirment que likelihood, prior, bounds et log-posterior ne dépendent pas du proposal.

## Réponses explicites

1. **Le proposal historique est-il sous-optimal ?** Oui selon l'ESS/s médian de cette qualification.
2. **Des pas diagonaux plus grands suffisent-ils ?** **Non.** Le meilleur diagonal, `diagonal_4`, monte à 3.09 ESS/s médian mais garde un ESS minimal de 59.5, très inférieur au proposal corrélé.
3. **La paramétrisation `(m,d)` aide-t-elle ?** **Oui, mais moins.** `md_2_4` atteint 3.57 ESS/s médian et Rhat max 1.0092; le Jacobien constant garantit la même cible.
4. **Le proposal corrélé améliore-t-il davantage l'ESS ?** Oui.
5. **Stratégie générique recommandée :** `short pilot -> covariance empirique + ridge 1e-6 -> covariance fixe`, si `correlated_1p68` demeure premier après examen; sinon retenir la meilleure configuration du classement.
6. **Longueur finale :** conserver au moins 10 000 itérations par chaîne et cinq chaînes tant que les objectifs Rhat/ESS ne justifient pas une réduction. Une extension 20 000 est requise si un ESS important reste inférieur à 300.
7. **Les quantiles publiés changent-ils ?** Les médianes restent proches (maximum **0.108 SD**), donc pas de déplacement central statistiquement important sur les pilotes. Certains quantiles bougent toutefois jusqu'à **0.509 SD**, au-delà du simple arrondi; ils doivent être recalculés avec les chaînes convergées.
8. **Faut-il recalculer les 19 cas et Figure 2 ?** **Oui**, après validation de cette qualification, avec cinq chaînes de 10 000 pas et combinaison post-burn-in seulement après `Rhat < 1.01`. Cette campagne pilote ne les a pas écrasés.

## Produits complets

- `posterior_summaries.csv`: mean, median, SD, q025, q10, q25, q75, q90, q975, ACF(1), IACT, ESS et ESS/s.
- `run_diagnostics.csv`: acceptance, runtime, meilleur misfit normalisé et chemins des chaînes.
- `autocorrelation_functions.csv.gz`: ACF complète jusqu'au lag 1000.
- `split_rhat.csv` et `interseed_variability.csv`: convergence et stabilité multi-chain.
- `configuration_ranking.csv` et `posterior_target_comparison.csv`: sélection et contrôle de cible.
- `posterior_pooled_comparison.csv` et `published_reference_comparison.csv`: accord de cible agrégé et impact sur les valeurs publiées.
- `chains/*.npz`: chaque état post-burn-in réellement diagnostiqué.

## Tests logiciels

Résultat : **59 passed, 4 skipped, 0 failed, 0 errors**. Les tests ciblés couvrent symétrie/covariance, transformation aller-retour, Jacobien, reproductibilité, régularisation, rejet aux bounds et invariance de la cible. Aucun test ni golden Ploemeur n'est inclus dans la commande de validation.
