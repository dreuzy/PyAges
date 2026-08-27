# Audit des diagnostics MCMC

## Verdict

`NEEDS MANUSCRIPT REVISION`

Les quatre campagnes demandées n'emploient pas une définition unique de R-hat ou de l'ESS. Aucun diagnostic n'est calculé par ArviZ, Stan ou un autre paquet MCMC. Les fonctions sont internes aux scripts PyAge; NumPy et SciPy ne fournissent ici que les primitives numériques. Les sorties canoniques ont été produites avec Python 3.12.4, NumPy 2.1.2 et SciPy 1.14.1.

## Définitions par campagne

| Campagne | R-hat réel | ESS réel | Regroupement et `Min ESS` |
|---|---|---|---|
| `s3_2_shifted_exponential` | `scripts.run_final_shifted_exponential._split_rhat`: split-R-hat classique, non rank-normalized et non folded. Chaque chaîne retenue est coupée en deux; les dix demi-chaînes sont comparées. | `_iact_ess`: ESS d'autocorrélation calculé séparément sur chaque chaîne avec l'initial positive sequence de Geyer et une séquence de paires rendue monotone par `minimum.accumulate`; les cinq ESS sont additionnés. | Cinq chaînes. `Min ESS` = minimum des ESS additionnés de `mu`, `t0` et `mtt=mu+t0`. |
| `s4_1_holten` | Réutilise exactement `_split_rhat` ci-dessus. | Réutilise exactement `_iact_ess`; somme des cinq ESS mono-chaîne. | Cinq chaînes par puits. `Min ESS` = minimum sur `z0`, `z1`, `z2`, `f_0_20`, `f_20_40`, `f_40_60`, `f_old`. L'objectif n'entre pas dans ce minimum. |
| `s4_2_ploemeur` | `scripts.common.mcmc_diagnostics.split_rhat`: transformation par rangs de Blom, folding autour de la médiane, maximum des deux R-hat. Attention: `split_rhat` coupe d'abord les chaînes, puis `_basic_rhat` les coupe une deuxième fois. Le résultat est donc calculé sur vingt quarts de chaînes, et n'est pas l'algorithme standard «une seule coupure» de Vehtari et al. (2021). | Le script applique `rank_normalize` aux cinq chaînes, puis `ess`. `ess` coupe une fois les chaînes et calcule conjointement un ESS d'autocorrélation multi-chaînes par initial positive sequence de Geyer, avec correction inter-chaînes. Ce n'est ni un tail ESS ni, malgré la transformation par rangs, une implémentation package du bulk ESS de Vehtari. | `Min ESS` = minimum sur `mu`, `t0` et `t50=t0+mu*ln(2)`; il ne s'agit pas du MTT `mu+t0`. |
| `holten_prior_dirichlet1` | Réutilise le split-R-hat classique de `run_final_shifted_exponential`. | Réutilise l'ESS d'autorrélation mono-chaîne, puis somme sur cinq chaînes. | Même minimum que Holten H4: trois latents et quatre fractions physiques. |

## Détail de l'implémentation commune rank-normalized

Dans `scripts/common/mcmc_diagnostics.py`:

- `split_chains(values)` conserve les `floor(n/2)` premiers et derniers tirages de chaque chaîne; si `n` est impair, le tirage central est supprimé.
- `rank_normalize(values)` agrège tous les rangs, attribue le rang moyen aux ex æquo, utilise la formule de Blom `(rank-0.375)/(N+0.25)`, puis `scipy.special.ndtri`.
- `split_rhat(values)` calcule le maximum du R-hat sur les rangs normalisés et du R-hat sur les écarts absolus à la médiane, eux aussi normalisés. Du fait de la seconde coupure dans `_basic_rhat`, ce n'est pas exactement le rank-normalized folded split-R-hat canonique à une coupure.
- `ess(values)` utilise des autocovariances FFT, une estimation combinant variances intra- et inter-chaînes, puis l'initial positive sequence et une séquence monotone de Geyer.

Le module IG ciblé de Ploemeur, hors des quatre identifiants demandés mais présent dans le paquet d'article, utilise cette même base pour construire explicitement un `bulk_ess = ess(rank_normalize(values))` et un `tail_ess = min(ess(I[x<=q05]), ess(I[x>=q95]))`. Son minimum est le minimum bulk/tail sur tous les paramètres. Cette convention ne doit pas être attribuée à la campagne shifted-exponential `s4_2_ploemeur`.

## Burn-in

Tous les diagnostics sont calculés après burn-in et sans thinning diagnostique (`1`). Deux conventions de stockage coexistent:

- le sampler générique utilisé par les campagnes shifted-exponential conserve un état lorsque l'indice zéro-based vérifie `i > burn_in*nstep`; avec 10 000 pas et 20 %, cela donne 7 999 états par chaîne;
- les samplers Holten conservent `step >= int(steps*0.20)`, soit exactement 8 000 états pour 10 000 pas et 16 000 pour 20 000 pas.

Le burn-in n'est donc pas retiré une seconde fois au moment du diagnostic: les fichiers de chaînes contiennent déjà uniquement les états retenus.

## Phrase prête pour le manuscrit

> Convergence was assessed after a 20% burn-in without diagnostic thinning. The synthetic shifted-exponential and Holten analyses used an in-house classical split-R-hat and a Geyer autocorrelation ESS computed per chain and summed across five chains, whereas the Ploemeur shifted-exponential analysis used an in-house rank-normalized folded R-hat (with the code's two-stage chain splitting) and a joint rank-normalized autocorrelation ESS; the reported minimum ESS is the minimum over the parameters listed for each analysis.

Cette formulation décrit fidèlement le code, mais la mention explicite de la double coupure est nécessaire tant que les diagnostics ne sont pas recalculés avec une définition standard.
