# Audit pilot / production MCMC

## Verdict

`CONFIRMED` pour les protocoles et manifests; `NEEDS MANUSCRIPT REVISION` si le manuscrit affirme que les états initiaux synthétiques sont distincts ou que le ridge vaut une variance absolue `1e-6`.

## Synthetic shifted exponential

Le manifest canonique `C:\pyage-runs\article-v1\shifted_exponential\manifest.json` confirme:

- pilote: 4 000 itérations, burn-in 20%;
- covariance empirique des tirages retenus, puis ridge relatif `1e-6`;
- cinq chaînes de production, 10 000 itérations chacune, burn-in 20%;
- aucune extension finale: les 19 cas sont restés à 10 000;
- covariance ensuite figée et multipliée par `(2.38/sqrt(2))^2` dans la proposition;
- aucun thinning diagnostique.

Le ridge n'est pas `1e-6` ajouté directement sur chaque variance. `regularize_empirical_covariance` ajoute `1e-6 * max(trace(cov)/dimension,1e-12) * I`: c'est un coefficient diagonal relatif et dépendant de l'échelle.

Les états initiaux ne sont pas distincts: pilote et cinq productions passent tous `{"mu":10,"shift":10}`. Les graines, elles, sont distinctes: `pilot=410000+case`; `production=420000+100*case+chain_zero_based`.

Le sampler générique conserve 7 999 tirages par chaîne de 10 000 à cause de la condition stricte `i > burn_in*nstep`.

## Holten H4

Tous les puits ont cinq chaînes, burn-in 20%, pilote 4 000, ridge relatif `1e-6`, covariance fixe et échelle `2.38/sqrt(3)`. Les cinq chaînes d'un puits partent toutes du même optimum déterministe en espace `z`; elles ont des graines distinctes selon `pilot=510000+well_one_based` et `production=520000+100*well_one_based+chain_zero_based`.

| Puits | Pas/chaîne finaux | Extension par rapport à 10 000 | Coordinate refresh final |
|---|---:|---|---|
| 59-05 | 10 000 | non | aucun |
| 67-19 | 10 000 | non | aucun |
| 72-22 | 10 000 | non | aucun |
| 73-29 | 20 000 | oui | probabilité 0.20 pour `z1` et 0.20 pour `z2` |
| 85-33 | 20 000 | oui | aucun |
| 85-34 | 20 000 | oui | probabilité 0.10 pour `z1` et 0.10 pour `z2` |
| 85-35 | 20 000 | oui | aucun |

Le refresh est un mélange entre un random walk gaussien corrélé et le remplacement uniforme symétrique d'une coordonnée dans `[-8,8]`. Chaque composante de proposition est symétrique; les propositions hors bornes sont rejetées. Le ratio MH utilise donc uniquement la différence de log-target et la densité cible `exp(-J/2)` n'est pas modifiée. Les tests `tests/calibration/test_mh_proposals.py` couvrent les propositions symétriques fixes et leurs corrections de Hastings; le mélange Holten est en plus lisible directement dans `_sample`.

## Holten prior `Dirichlet(1,1,1,1)`

Le protocole alternatif réutilise cinq chaînes, le même burn-in, les mêmes longueurs finales, graines et refresh pour 73-29/85-34. Il ajoute à `-J/2` la densité transformée du prior Dirichlet en espace `z`; il s'agit donc d'une autre cible par choix scientifique explicite, pas d'un effet du proposal.

## Ploemeur shifted exponential

Le manifest canonique confirme quatre calibrations, cinq chaînes chacune, 10 000 pas par chaîne, burn-in 20%, pilote de 4 000 pas, covariance empirique avec ridge relatif `1e-6`, puis covariance fixe à l'échelle `2.38/sqrt(2)`. Les bornes sont `mu in [0.1,70]` yr et `t0 in [0,70]` yr; les trois traceurs ont une erreur relative de 20%.

Le pilote de chaque cas part de `(mu,t0)=(10,10)`. Les cinq états de production sont ensuite distincts: les tirages du pilote sont triés par `t50=t0+mu*ln(2)` et les quantiles de position 10%, 30%, 50%, 70% et 90% sont choisis.

Graines exactes:

- pilotes, cas one-based 1–4: `701001`, `701002`, `701003`, `701004`;
- production à 10 000 pas: `710000 + 1000*case_one_based + 10*chain_zero_based + 1`, soit `711001...711041`, `712001...712041`, `713001...713041`, `714001...714041` par pas de 10.

Comme pour le shifted synthétique, le sampler générique conserve 7 999 tirages par chaîne. Aucune chaîne Ploemeur shifted n'a été étendue dans la campagne stabilisée.

## Preuve utilisée

Les constantes et fonctions ont été vérifiées dans `scripts/run_final_shifted_exponential.py`, `scripts/run_final_holten_h4.py`, `scripts/run_holten_prior_robustness.py`, `scripts/run_ploemeur_shifted_exponential_final.py` et `pyage/calibration/mh_proposals.py`, puis confrontées aux quatre manifests sous `C:\pyage-runs\article-v1`.
