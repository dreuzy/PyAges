# Audit des limites des historiques d'entrée

## Verdict

`CONFIRMED`, avec la portée explicite «finite tracer input histories».

## Comportement réel

La classe `pyage.tracer.tracer_root.Tracer` lit `recharge.csv` puis crée `scipy.interpolate.interp1d(..., kind="linear")`. L'interpolateur lui-même n'est jamais appelé hors domaine: `Tracer.get_concentration` vérifie d'abord l'intervalle fermé `[datemin, datemax]`.

- avant la première date: composante de recharge égale à zéro;
- après la dernière date: composante de recharge égale à zéro;
- aux deux dates extrêmes: interpolation linéaire, extrémités incluses;
- pour un tableau mélangeant dates valides et invalides: tableau initialisé à zéro, puis interpolation uniquement sur le masque valide;
- aucune exception spécifique n'est codée pour les traceurs distribués qui utilisent une chronique finie.

Une éventuelle production in situ est ajoutée ensuite: la sortie totale peut donc être non nulle hors domaine même lorsque la composante d'entrée est nulle. La phrase du manuscrit est correcte parce qu'elle parle des valeurs de l'input history, non de la concentration totale transformée.

## Entrées constantes et synthétiques

Une configuration `recharge_constant` est intentionnellement constante pour toute date et ne suit pas la règle zéro hors domaine. Elle n'est pas une «finite supplied time history». De même, `ConstantTracer` et `SyntheticTracer` suivent leur callable programmatique. Cette distinction doit être conservée dans la formulation.

## Masse LPM hors fenêtre

La convolution n'intègre que les âges dans `[0,date-datemin]`. `Convolution.window_mass(lpm)` calcule la masse présente dans cette fenêtre pour les lois continues, discrètes et mixtes. La masse plus ancienne est exclue sans division par la masse couverte: il n'y a aucune renormalisation. Le diagnostic de la dernière convolution continue/mixte est également exposé comme `Convolution.diagnostics.window_mass`.

## Tests et exemple minimal

Les contrats existants incluent:

- `tests/tracer/test_distributed_tracer_contracts.py::test_tritium_distributed_metadata_and_decay`;
- `tests/convolution/test_convolution_scientific.py::test_continuous_path_keeps_physical_truncation_without_renormalizing`;
- les tests des chemins Dirac, double Dirac et mixture hors fenêtre dans le même module.

Exemple existant: la chronique `3H` commence à `1957.5`; le test vérifie que `tracer.get_concentration(date=1900.0, time=100.0) == 0.0`. Autre exemple: avec un traceur constant de `datemin=2000`, une observation en 2010 et une loi gamma, la convolution d'une concentration unité est exactement `F(10)-F(0)`, grandeur strictement comprise entre zéro et un, sans renormalisation à un.

## MANUSCRIPT STATEMENT CONFIRMED

> For finite tracer input histories, values outside the supplied time domain are set to zero rather than extrapolated, and LPM probability mass beyond the available history is not renormalized.

La phrase est exacte pour les chroniques finies. Les entrées constantes/synthétiques et une production in situ sont des cas conceptuellement distincts, pas des exceptions cachées à une chronique finie.
