# Rapport principal — audit des questions de code PyAge

## Périmètre et hiérarchie des preuves

Audit en lecture seule réalisé le 27 août 2026. Aucun manuscrit Word, résultat, figure, chaîne MCMC, tag, release, dépôt distant ou archive n'a été modifié ou créé.

Trois ensembles de preuve ont été distingués:

1. le code actuellement présent dans le dépôt;
2. les preuves historiques versionnées de la matrice forward 133 cas;
3. la campagne stabilisée existante `C:\pyage-runs\article-v1` et son paquet d'article.

Les manifests historiques sous `article/` pointent vers d'anciens commits et des résultats bruts absents du dépôt. Les six commandes légères `python -m scripts.article.run_case check <case_id>` ne valident donc pas l'état local actuel (artefacts historiques manquants et/ou checksums divergents). La campagne externe stabilisée fournit les résultats utilisés dans le présent audit, mais elle ne transforme pas les anciens manifests en preuve de release v1.0. Le futur fichier `article/audit/reproducibility_release_check.md` n'a volontairement pas été créé.

## 1. Diagnostics MCMC — `NEEDS MANUSCRIPT REVISION`

Les campagnes n'utilisent pas une définition commune. Shifted synthétique et Holten emploient un split-R-hat classique et une somme d'ESS d'autocorrélation mono-chaîne. Ploemeur shifted emploie une implémentation interne rank-normalized/folded et un ESS d'autocorrélation multi-chaînes rank-normalized.

Point critique: le R-hat commun de Ploemeur coupe les chaînes deux fois (quarts de chaîne), ce qui n'est pas exactement le rank-normalized folded split-R-hat canonique à une coupure de Vehtari et al. Aucune attribution à ArviZ/Stan ne serait correcte. Voir `mcmc_diagnostics_definition.md`.

## 2. Appendix A — `NEEDS MANUSCRIPT REVISION`

Les 133 cas et statistiques 0.5×/1×/2× sont confirmés. La formule réellement exécutée est `abs(Pyage-reference)/abs(reference)` pour une référence non nulle, sinon `NaN`. Le rapport historique indique à tort un plancher `1e-14`. Les temps comparables ne sont pas disponibles; les récupérer nécessite les logs bruts historiques ou un rerun contrôlé (`NEEDS RERUN`). Voir `appendix_A_audit.md` et `appendix_A_values.csv`.

## 3. Limite des historiques — `CONFIRMED`

Pour une chronique finie, l'entrée est nulle avant la première date et après la dernière; elle n'est pas extrapolée. La masse LPM hors fenêtre est omise sans renormalisation. Les entrées constantes/synthétiques et la production in situ sont explicitement distinguées. Voir `input_history_boundary_audit.md`.

## 4. Production d'ordre zéro — `CONFIRMED`

Les deux équations demandées sont celles du code. `production_rate` est un scalaire constant en unité de concentration par an, sans variable spatiale. L'absence de décroissance sélectionne exactement la branche linéaire. Il n'existe pas de traitement spécialisé de `beta` positif extrêmement petit. Voir `tracer_transformation_audit.md`.

## 5. Équations LPM — `BLOCKER`

Les conventions scientifiques ciblées sont confirmées: IG en moments physiques, shifted IG, `mu2` comme délai additionnel du double Dirac, mélange Dirac + exponentielle normalisé et shape-free par stick breaking.

`BLOCKER`: la classe `DiracDoubleLpm` déclare une unité vide pour `mu2`, tandis que son YAML déclare `year` et que le calcul l'utilise comme un délai en années. L'équation est sans ambiguïté, mais les métadonnées code ne le sont pas. Par ailleurs, le manuscrit/Table 1 n'a pas été fourni: les sept modèles non explicitement décrits dans la demande restent `NOT_ASSESSABLE`, sans faux `match=true`. Voir `lpm_equation_audit.csv`.

## 6. Benchmark PyAge–TracerLPM — `NEEDS MANUSCRIPT REVISION`

Les métriques, conversions, bornes, 480 cas et médianes L1/L2 sont confirmés. Les effectifs stabilisés sont toutefois 461 (L2 PyAge), 111 (L1 PyAge), 208/272 (tau) et 204/233/43 (paramètre secondaire/ties), et non 463, 121, 217/263 et 241/233/6. Voir `cross_software_metric_audit.md`.

## 7. Pilot / production MCMC — `CONFIRMED`

Les longueurs, burn-ins, graines, covariances fixes et extensions sont vérifiés contre le code et les manifests. Deux précisions doivent rester dans le texte: le ridge `1e-6` est relatif à la variance typique, et les cinq chaînes synthétiques commencent toutes à `(10,10)`, donc les états initiaux ne sont pas distincts. Le refresh Holten est symétrique et ne modifie pas la cible. Voir `mcmc_configuration_audit.md`.

## 8. Runtime, matériel, manuel, licence — `BLOCKER`

Python 3.12–3.14 est déclaré; les analyses ont utilisé Python 3.12.4. Aucun GPU n'est requis et aucune mémoire typique n'est enregistrée. La licence est CeCILL 2.1. Le manuel est la documentation Sphinx/MyST sous `docs/user-guide/`.

Deux décisions restent nécessaires: le code s'identifie encore comme `0.1.0b1`, pas `v1.0`, et `install/environment.yml` épingle SciPy 1.18.0 alors que `install/constraints.txt` épingle 1.18.1 tout en prétendant être aligné. Voir `runtime_requirements.md`.

## 9. Cross-check numérique — `NEEDS MANUSCRIPT REVISION`

Les nombres forward, shifted-exponential, Holten et Ploemeur explicitement fournis sont confirmés aux arrondis demandés. Les six effectifs TracerLPM signalés ci-dessus sont des mismatches. Le contrôle cellule par cellule des Tables 3/4 et Appendices B–D nécessite la version figée du manuscrit; il n'est pas remplacé par une comparaison contre les seuls fichiers canoniques. Voir `manuscript_numerical_crosscheck.csv`.

## 10. Reproductibilité de release — `NEEDS AUTHOR INPUT`

La procédure finale n'a pas été exécutée comme validation de release: aucun tag v1.0 ni DOI n'est établi par cet audit. Les checks locaux actuels échouent faute de l'ancienne preuve interne complète. Une archive candidate existe hors dépôt, mais son statut final, son tag, son commit propre et tout DOI doivent être confirmés ultérieurement. Le livrable futur demandé n'a pas été créé.

## Synthèse des blockers

| Élément | Statut | Action nécessaire |
|---|---|---|
| Unité runtime `mu2` du double Dirac vide vs YAML `year` | `BLOCKER` | Décision/correction explicite avant gel de Table 1; aucun changement automatique effectué. |
| SciPy 1.18.0 dans `environment.yml` vs 1.18.1 dans `constraints.txt` | `BLOCKER` | Choisir et qualifier un gel unique. |
| Effectifs TracerLPM du texte vs campagne stabilisée | `NEEDS MANUSCRIPT REVISION` | Remplacer par les effectifs canoniques ou identifier formellement une autre campagne source. |
| Formule forward avec plancher `1e-14` | `NEEDS MANUSCRIPT REVISION` | Décrire la formule réellement exécutée sans plancher, ou autoriser un rerun après changement scientifique séparé. |
| Double coupure du R-hat Ploemeur | `NEEDS MANUSCRIPT REVISION` | Décrire le comportement réel; toute standardisation/recalcul serait une autre tâche. |
| Version `0.1.0b1` vs appellation v1.0 | `NEEDS AUTHOR INPUT` | Fixer la nomenclature de release au moment autorisé. |

## Manuscript wording now safe to finalize

- Pour les chroniques finies, les valeurs d'entrée hors domaine sont mises à zéro et la masse LPM hors historique n'est pas renormalisée.
- `production_rate` est une production effective constante d'ordre zéro; les deux équations auditées sont exactes, sans variable spatiale.
- Pour l'IG, `mu` est la moyenne physique et `sigma` l'écart-type physique; SciPy reçoit `shape=(sigma/mu)^2`, `scale=mu^3/sigma^2`, `loc=0`.
- Pour l'IG shifted, `t0/shift` est ajouté au support, aux quantiles, à la moyenne et au partial first moment; la moyenne totale est `t0+mu`.
- Pour le double Dirac, les positions sont `mu1` et `mu1+mu2`; `mu2` est un délai additionnel.
- Pour le mélange, le Dirac est à `mu1`, l'exponentielle commence à `mu1+t0`, a pour échelle `mu2`, et reçoit la masse `1-r` une seule fois.
- Le shape-free générique est piecewise-uniform sur des bins finis configurés; ses fractions par stick breaking sont normalisées et le dernier intervalle est fermé à droite.
- Les métriques communes sont `sum(abs(calc-obs)/abs(obs))` et la somme des carrés de ces résidus, avec plancher `1e-300` au dénominateur.
- EPM utilise `eta=1+r`, `mu=tau/eta`, `t0=tau(1-1/eta)`; DM utilise `mu=tau`, `sigma=tau*sqrt(2DP)`.
- «0% added noise» signifie aucune perturbation aléatoire; l'objectif PyAge garde une échelle relative de 1% et un plancher de `10^-6` du maximum du traceur.
- Les résultats explicitement confirmés dans `manuscript_numerical_crosscheck.csv`, à l'exclusion des lignes `FALSE` et `NOT_ASSESSABLE`, peuvent être figés.
- La licence exacte est CeCILL 2.1; PyAge est CPU-only et ne requiert pas de GPU.

## Information still unavailable

- Les temps totaux/relatifs fiables de l'expérience de sensibilité 133 cas: logs bruts historiques ou rerun contrôlé requis.
- Le contrôle cellule par cellule des Tables 1, 3, 4 et Appendices B, C, D1–D2: manuscrit figé requis.
- La décision d'auteur sur les effectifs TracerLPM divergents et la source à citer.
- La décision d'auteur sur l'unité runtime incohérente de `mu2`.
- Le gel SciPy unique de l'environnement de reproduction.
- L'identité finale de la release v1.0 (version, commit propre, tag), l'archive finale et son DOI; aucun DOI ne peut être inféré.
- Les caractéristiques CPU/RAM et performances matérielles typiques, non enregistrées par les manifests.
