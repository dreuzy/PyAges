# Audit des transformations de traceur et de la production d'ordre zéro

## Verdict

`CONFIRMED`

L'implémentation se trouve dans `pyage/tracer/tracer_root.py::Tracer.get_concentration`.

## Équations implémentées

La composante de recharge `c1` est obtenue par la chronique ou l'entrée constante, puis, si la décroissance est configurée, multipliée par `exp(-beta*time)`. La composante de production vaut:

\[
c_2=\alpha\frac{1-e^{-\beta\tau}}{\beta}
\]

si la décroissance est active, et `alpha*time` sinon. La somme est donc exactement:

\[
C(t_s,\tau)=C_{in}(t_s-\tau)e^{-\beta\tau}+\frac{\alpha}{\beta}(1-e^{-\beta\tau})
\]

pour `beta>0`, et:

\[
C(t_s,\tau)=C_{in}(t_s-\tau)+\alpha\tau
\]

lorsqu'aucune décroissance n'est configurée. Si aucune recharge n'est configurée, le premier terme est simplement absent.

## Signification de `alpha`

`alpha` est la valeur scalaire `production_rate` du YAML du traceur. Elle représente une production effective constante d'ordre zéro, en unité de concentration du traceur par an. Elle est constante pour l'instance/configuration entière. Aucun indice de position, champ spatial ou variable hydrodynamique n'intervient dans ce calcul.

## Cas `beta=0` et proximité de zéro

Les configurations `half_life` et `decay_mean_lifetime` doivent être strictement positives. Le code ne représente pas l'absence de décroissance par un taux numérique zéro: il utilise la branche «decay disabled», qui calcule exactement `alpha*time`. Il n'existe ni seuil «beta proche de zéro», ni développement limité, ni `expm1`; tout taux positif configuré utilise directement `(1-exp(-beta*time))/beta`. Une valeur extrêmement petite peut donc subir une perte de précision par annulation, même si sa limite mathématique est correcte.

## Tests

- `tests/tracer/test_decay_contract.py::test_production_with_decay_has_expected_asymptote` vérifie l'asymptote `alpha/beta`.
- Les tests `test_half_life_reduces_constant_recharge_by_half` et `test_mean_lifetime_reduces_constant_recharge_by_e` vérifient les deux conventions de décroissance.
- `test_decay_parameters_must_be_positive` exclut les valeurs nulles ou négatives.
- Les contrats de traceurs distribués vérifient également décroissance et absence de production implicite.

La formulation «effective constant zeroth-order production rate» est donc sûre. Une précision optionnelle est que l'implémentation ne comporte pas de traitement numérique spécialisé pour un taux de décroissance positif extrêmement proche de zéro.
