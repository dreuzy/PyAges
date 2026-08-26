# Statut final des simulations d'article PyAge

Période consolidée : **2026-08-20 22:50:23 — 2026-08-22 00:25 CEST**.
Commit `HEAD` : `e77691e5c957b2ac650642e89cb9dd3c9d030c57`.
Aucun commit, reset, revert, golden ou manuscrit Word n'a été modifié.

## Shifted exponential

**Statut : 19/19 cas terminés et convergés.** Chaque cas utilise un pilote historique de 4 000 pas, la covariance empirique `(mu, t0)` avec ridge relatif `1e-6`, puis cinq chaînes indépendantes de 10 000 pas avec le scale figé `2.38/sqrt(2)`, burn-in 20 % et aucun thinning diagnostique. La règle de seeds est consignée dans le manifest. Les 95 NPZ contiennent 759 905 états post-burn-in lisibles et finis.

Aucun cas n'a nécessité la prolongation ciblée à 20 000 pas. Sur les trois quantités `mu`, `t0` et `MTT`, le **split-Rhat maximal est 1,00978** (cas 10) et l'**ESS agrégé minimal est 755,79** (cas 10). Les acceptations par chaîne vont de 0,1201 à 0,3685, médiane 0,3328. Les runtimes muraux par chaîne sont conservés dans le CSV diagnostique; leur médiane vaut 51,98 s, mais ils reflètent la forte concurrence de la campagne Ploemeur active et ne constituent pas un benchmark de performance.

| cas | Rhat max | ESS min |
| ---: | ---: | ---: |
| 1 | 1,00150 | 2 356,96 |
| 2 | 1,00242 | 4 420,51 |
| 3 | 1,00100 | 3 977,68 |
| 4 | 1,00266 | 3 806,54 |
| 5 | 1,00421 | 1 570,84 |
| 6 | 1,00132 | 3 692,24 |
| 7 | 1,00131 | 4 732,61 |
| 8 | 1,00028 | 3 320,91 |
| 9 | 1,00202 | 2 512,58 |
| 10 | 1,00978 | 755,79 |
| 11 | 1,00117 | 3 257,58 |
| 12 | 1,00082 | 4 531,02 |
| 13 | 1,00082 | 4 284,48 |
| 14 | 1,00217 | 1 115,85 |
| 15 | 1,00083 | 4 305,34 |
| 16 | 1,00225 | 4 774,50 |
| 17 | 1,00029 | 4 438,61 |
| 18 | 1,00169 | 3 799,11 |
| 19 | 1,00083 | 4 784,05 |

La Table 3 finale, ses concentrations synthétiques sans bruit, les résumés complets et les diagnostics sont dans `results/final_article_simulations/shifted_exponential`. La Figure 2 finale utilise bien `x=mu`, `y=t0`, la cible `(10,30)`, les quatre traceurs à 8 %, les échantillons du cas convergé et une grille recalculée en `sqrt(J_data/4)`; elle ne lit aucun ancien fichier `0.5 ln(J)`.

Comparaison à l'ancienne production mono-chaîne : sur les 57 couples cas/paramètre, la médiane de `|delta median|` vaut 0,188 an et celle de `|delta SD|` 0,164 an. Les différences maximales concernent les posteriors de bord les plus asymétriques : `|delta median| = 2,613` ans (cas 5, `mu`), `|delta mean| = 2,741` ans (cas 10, `mu`) et `|delta q90| = 6,689` ans (cas 10, `mu`). Le CSV old/new conserve toutes les différences de mean, median, SD et quantiles.

## Holten H4

**Statut : 7/7 puits terminés et convergés.** Les observables sont exactement ³H, ³He tritiogénique déjà corrigé, ⁸⁵Kr et ³⁹Ar. Le sigma ³He est 0,5 TU pour les six valeurs publiées et 0,5 TU imputé pour 59-05. Le forward utilise `lambda = ln(2)/12.32 yr^-1`; aucune correction gaz noble supplémentaire n'est appliquée.

Les puits 59-05, 67-19 et 72-22 passent à 10 000 pas. Seuls 73-29, 85-33, 85-34 et 85-35 ont été prolongés à 20 000 pas. Le posterior borné dans l'espace latent canonique `[-8,8]` élimine la dérive impropre des logits associés aux fractions nulles. Pour 73-29 et 85-34, l'échec du proposal pur à 20 000 pas a motivé un ajustement numérique documenté et réversible : mélange du random walk corrélé figé avec des rafraîchissements uniformes symétriques de `z1` ou `z2` (20 % ou 10 % par coordonnée). Les chaînes initiales en échec sont conservées sous leurs noms d'origine.

| puits | pas/chaîne | Rhat max | ESS min |
| --- | ---: | ---: | ---: |
| 59-05 | 10 000 | 1,00397 | 1 244,52 |
| 67-19 | 10 000 | 1,00699 | 936,58 |
| 72-22 | 10 000 | 1,00704 | 1 373,32 |
| 73-29 | 20 000 | 1,00907 | 313,10 |
| 85-33 | 20 000 | 1,00633 | 749,54 |
| 85-34 | 20 000 | 1,00561 | 728,42 |
| 85-35 | 20 000 | 1,00785 | 434,80 |

Comparaison aux 28 fractions Visser : **MAE 0,005455**, **median absolute error 0,003815**, **RMSE 0,007046**, **maximum 0,017993**; les 28/28 erreurs sont ≤0,02, donc aussi ≤0,05 et ≤0,10. Le plus grand résidu standardisé des concentrations vaut 1,800. Par rapport à l'ancien H4, la médiane de `|delta median|` vaut 0,000577 et son maximum 0,01029 : aucune modification anormale des médianes. La Figure 3 finale montre uniquement Visser versus PyAge H4, avec médianes et q10–q90.

## Ploemeur

**État initial détecté : ACTIVE. État final au 2026-08-22 : TERMINÉ ET
EXPLOITABLE.** Le superviseur `HYP-26-0172/v2` a terminé ses dix expériences
avec un code retour nul et le finaliseur a terminé avec le code 0.

La campagne shifted-exponential finale couvre quatre calibrations F09/F11,
série complète et fenêtre indépendante 2014–2015, avec cinq chaînes par cas.
Les quatre cas convergent : split-Rhat maximal 1,00404 et ESS minimal 1741,12.
La Figure 4 finale, ses prédictions row-wise, le rapport et le manifest vérifié
sont disponibles sous
`results/final_article_simulations/ploemeur_shifted_exponential_final/`.

La reproduction IG physique ciblée couvre les posteriors full-series, spans
2012–2024 conditionnés et fenêtres 2014–2015 conditionnées. Les six ensembles
passent `split-Rhat < 1.01` et `ESS >= 300`. Le benchmark article est reproduit;
les résultats détaillés sont dans
`results/ploemeur_targeted_ig_reproduction/PLOEMEUR_TARGETED_IG_REPRODUCTION.md`
et
`results/ploemeur_targeted_ig_reproduction/ploemeur_targeted_nonregression_results.csv`.

## Tests ciblés

| volet | passed | skipped | failed | errors | durée pytest |
| --- | ---: | ---: | ---: | ---: | ---: |
| shifted exponential (MH, proposal corrélé, partial moments/modèle, diagnostics) | 69 | 4 | 0 | 0 | 120,25 s |
| Holten (stick-breaking, ³H/³He, fractions, reproduction) | 23 | 0 | 0 | 0 | 101,22 s |
| Ploemeur (dates dupliquées, prior IG, proposals, observations, pairing) | 22 | 0 | 0 | 0 | passes ciblées |

État cumulé documenté : **92 passed, 4 skipped** lors de la campagne initiale,
puis **22 tests Ploemeur ciblés passés**, sans échec ni erreur. Aucun golden n'a
été modifié.

## État de préparation du manuscrit

| article_component | simulation_status | final_artifact | manuscript_ready |
| --- | --- | --- | --- |
| Table 3 | 19/19 convergés, aucune extension | `results/final_article_simulations/shifted_exponential/table3_final.csv` et `.md` | **oui** |
| Figure 2 | régénérée depuis les chaînes finales et `sqrt(J_data/4)` | `figure2_shifted_exponential_final.{png,pdf,tiff}` | **oui** |
| Holten Figure 3 | 7/7 convergés, Visser vs H4 uniquement | `figure3_holten_h4_final.{png,pdf}` | **oui** |
| Ploemeur Figure 4 | 4/4 calibrations convergées, non-régression satisfaite | `figure4_ploemeur_shiftedexp_final.{png,pdf}` | **oui** |
| shifted-exponential posterior text | diagnostics et old/new complets | `results/final_article_simulations/shifted_exponential/shifted_exponential_final.md`, `posterior_summaries.csv` | **oui** |
| Holten text | diagnostics, résidus, métriques et old/new complets | `results/final_article_simulations/holten_h4_final/holten_h4_final_multichain.md` | **oui** |
| Ploemeur text | shifted exponential final et IG ciblée reproduite | `results/final_article_simulations/ploemeur_shifted_exponential_final/PLOEMEUR_SHIFTED_EXPONENTIAL_FINAL.md`, `results/ploemeur_targeted_ig_reproduction/PLOEMEUR_TARGETED_IG_REPRODUCTION.md` | **oui** |

Le manuscrit Word n'a pas été modifié; les artefacts validés sont prêts à être
insérés.

## Paquet article encapsulé

Le point d'entrée éditorial unique est `results/article_package/README.md`.
Le paquet regroupe Table 3, Figures 2–4, rapports, diagnostics, données tracées,
environnement et sources exactes d'exécution. Ses 67 artefacts sont référencés
par `provenance/article_package_manifest.json` et vérifiables avec
`CHECKSUMS.sha256`. Les chaînes MCMC brutes restent dans leurs répertoires de
calcul afin de ne pas alourdir le paquet éditorial.
