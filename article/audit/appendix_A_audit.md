# Audit de l'Appendix A — `s3_forward_verification`

## Verdict

`NEEDS MANUSCRIPT REVISION` pour la formule publiée; `NEEDS RERUN` seulement pour obtenir des temps de calcul comparables.

La matrice historique de 133 comparaisons est documentée et ses statistiques compactes sont versionnées. Le dossier brut annoncé par le rapport (`results/article_non_ploemeur_final/supplement_s1/`) n'est plus présent dans le dépôt.

## 1. Relative discrepancy réellement calculée

Le code au commit source archivé `17b38579a616f899944441f73d52f9780655648a`, comme le code actuel dans `scripts/article/run_article_non_ploemeur.py::_validation_matrix`, calcule:

\[
e_i = \frac{|C_{\mathrm{PyAge},i}-C_{\mathrm{ref},i}|}{|C_{\mathrm{ref},i}|}
\quad\text{si }C_{\mathrm{ref},i}\ne0,
\]

et stocke `NaN` si la référence vaut exactement zéro. Le numérateur et le dénominateur sont donc absolus; il n'existe aucun seuil pour une référence proche de zéro.

Le rapport `docs/reports/convolution_grid_sensitivity_2026-08-26.md` affirme au contraire un dénominateur `max(abs(Cref),1e-14)`. Cette affirmation ne correspond pas au code source du commit cité par ce même rapport. C'est une divergence documentaire à corriger dans le manuscrit/Appendix A. Les statistiques sauvegardées proviennent du calcul sans plancher. La matrice brute absente ne permet pas de recompter directement les références nulles, mais les 133 valeurs finies ont été résumées par le code.

## 2. Contrôles de grille par défaut

Tous sont définis dans `pyage/convolution/settings.py::ConvolutionSettings`.

| Nom | Défaut | Unité | Rôle |
|---|---:|---|---|
| `absolute_tolerance_factor` | `5e-4` | sans dimension | Terme global d'acceptation d'un bin: `fa*max(global_scale, eps)` dans le seuil sur l'étendue de la réponse du traceur. |
| `relative_tolerance` | `2e-2` | sans dimension | Terme local `fr*local_scale` du même seuil. |
| `linear_curvature_factor` | `0.1` | sans dimension | Si l'écart du point milieu à l'interpolation affine dépasse cette fraction du seuil précédent, l'intégration du bin repasse à une contribution au point milieu. |
| `max_subdivisions` | `20` | nombre de bissections | Limite dure par intervalle initial; son atteinte lève `ConvolutionError`, elle n'accepte pas silencieusement le bin. |
| `max_bins` | `20000` | nombre de bins | Limite dure de mémoire/temps; son dépassement lève `ConvolutionError`. |
| `floating_weight_epsilon_factor` | `64` | multiplicateur de l'epsilon machine | Ne raffine pas la grille. Il ne sert qu'à clipper des poids CDF/moments négatifs compatibles avec l'arrondi; les incohérences plus grandes restent des erreurs. |

Le critère d'acceptation documenté et implémenté est `K_range <= fa*max(global_scale, eps) + fr*local_scale`. L'âge et la largeur des bins sont en années décimales; la réponse `K` est dans l'unité déclarée du traceur. Dans l'expérience 0.5×/1×/2×, seuls les trois premiers facteurs sont multipliés ensemble; les limites de sécurité restent inchangées.

## 3. Référence indépendante des 133 comparaisons

La fonction `independent_reference` de `scripts/article/run_article_non_ploemeur.py` procède comme suit:

1. elle construit directement les lois SciPy à partir des paramètres physiques, sans appeler le moteur de convolution PyAge;
2. elle intègre en espace des probabilités entre `F(0)` et `F(tmax)`;
3. elle crée 32 segments uniformes (33 arêtes), puis ajoute les probabilités correspondant aux nœuds de la chronique du traceur;
4. chaque segment est intégré par une règle de Gauss–Legendre d'ordre 48 (`numpy.polynomial.legendre.leggauss`);
5. les intervalles de probabilité de largeur au plus `1e-13*max(1,F(tmax)-F(0))` sont ignorés. Ce seuil est un filtre de segments, pas une boucle de convergence adaptative.

Les distributions étroites sont stabilisées par l'intégration en espace quantile et le découpage aux ruptures de la chronique. Les Dirac simples et doubles sont évalués directement à leurs âges si ceux-ci sont dans `[0,tmax]`; le mélange Dirac–exponentielle combine un lookup direct et la quadrature de la composante continue. Le shape-free est intégré bin par bin avec découpage aux nœuds de chronique.

Cette référence est indépendante du calcul de production parce qu'elle n'utilise ni les masses de bins par différence de CDF, ni les partial first moments, ni la grille adaptative du moteur de production. Elle partage nécessairement les mêmes historiques de traceurs et paramètres physiques.

## 4. Sensibilité 0.5× / 1× / 2×

Les valeurs exactes sont dans `article/audit/appendix_A_values.csv`. Au réglage par défaut, le 95e percentile vaut `3.595558353699866e-05`, le maximum `1.413462328021509e-04` et la médiane 308 bins.

Les temps totaux et relatifs ne sont pas sauvegardés dans le CSV compact. Le rapport précise que les temps observés sur l'hôte partagé étaient anormaux et n'ont pas été retenus. Ils ne peuvent pas être reconstruits par post-traitement du CSV; il faut retrouver les sorties/logs bruts historiques ou relancer l'expérience sur un hôte contrôlé. Aucun rerun n'a été lancé pendant cet audit.

## 5. Covered-window mass

Pour une loi continue et `tmax=max(0,date-datemin)`:

\[
m_{\mathrm{window}}=F(t_{\max})-F(0).
\]

Pour un Dirac, la masse vaut l'indicatrice de l'appartenance de son âge à l'intervalle fermé `[0,tmax]`; pour deux Dirac, c'est la somme pondérée des deux indicatrices. Pour le mélange, elle vaut `rate*I(mu1 in window) + (1-rate)*(Fcont(tmax)-Fcont(0))`.

L'utilisateur peut appeler `Convolution.window_mass(lpm)`. Après une convolution continue ou mixte, la même grandeur est exposée par `Convolution.diagnostics.window_mass`. Toute masse plus ancienne que l'historique est omise de la convolution et n'est jamais renormalisée; une valeur inférieure à un quantifie donc la troncature physique par la fenêtre disponible.

## Sources canoniques

- `docs/reports/convolution_grid_sensitivity_2026-08-26.md`
- `docs/reports/data/convolution_grid_sensitivity_2026-08-26.csv`
- commit source `17b38579a616f899944441f73d52f9780655648a`
- `scripts/article/run_article_non_ploemeur.py`
- `pyage/convolution/settings.py`, `continuous_integration.py`, `convolution.py`

La campagne externe actuelle `C:\pyage-runs\article-v1\forward` contient une autre matrice de 270 cas. Elle ne remplace pas la preuve historique des 133 comparaisons de l'Appendix A.
