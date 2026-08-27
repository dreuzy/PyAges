# Audit du benchmark PyAge–TracerLPM (`s3_1_tracerlpm`)

## Verdict

`NEEDS MANUSCRIPT REVISION`

La campagne stabilisée contient bien 480 inversions appariées et les médianes communes annoncées sont exactes, mais six effectifs demandés ne correspondent pas à ses sorties canoniques.

## Métriques communes

Pour les quatre traceurs et pour chaque logiciel, le post-traitement recalcule:

\[
r_i=\frac{|C_{calc,i}-C_{obs,i}|}{\max(|C_{obs,i}|,10^{-300})},
\qquad L_1=\sum_{i=1}^{4} r_i,
\qquad L_2=\sum_{i=1}^{4} r_i^2.
\]

`L2` est une somme de carrés: ce n'est ni une moyenne, ni une racine, ni un RMSE. Ces métriques sont recalculées à partir des concentrations appariées; elles sont distinctes de l'objectif L2 pondéré natif de PyAge et de l'objectif L1 natif de TracerLPM.

| Élément | Manuscrit demandé | Campagne stabilisée | Verdict |
|---|---:|---:|---|
| cas appariés | 480 | 480 | `CONFIRMED` |
| médiane L1 PyAge / TracerLPM | 0.179 / 0.181 | 0.179228 / 0.180859 | `CONFIRMED` |
| médiane L2 PyAge / TracerLPM | 0.0135 / 0.0164 | 0.0134959 / 0.0163958 | `CONFIRMED` |
| L2 plus faible pour PyAge | 463/480 | 461/480 | `NEEDS MANUSCRIPT REVISION` |
| L1 plus faible pour PyAge | 121/480 | 111/480 | `NEEDS MANUSCRIPT REVISION` |
| erreur `tau` plus faible: PyAge / TracerLPM | 217 / 263 | 208 / 272 | `NEEDS MANUSCRIPT REVISION` |
| erreur paramètre secondaire plus faible: PyAge / TracerLPM / ties | 241 / 233 / 6 | 204 / 233 / 43 | `NEEDS MANUSCRIPT REVISION` |

Les comparaisons d'erreur paramétrique utilisent les erreurs absolues et une tolérance d'égalité de `1e-12`. Les 480 succès sont présents pour chacun des deux outils.

## Conversions de paramètres

Les fonctions réversibles sont dans `validation/tracerlpm/benchmark/scripts/mappings.py`.

Pour EPM, TracerLPM expose `r` et PyAge `eta`:

\[
\eta=1+r,\qquad \mu=\tau/\eta,\qquad t_0=\tau(1-1/\eta).
\]

L'inverse est `tau=mu+t0`, `eta=1+t0/mu`. Pour DM:

\[
\mu=\tau,\qquad \sigma=\tau\sqrt{2DP},
\]

et `DP=sigma^2/(2mu^2)`. Les formules demandées sont donc `CONFIRMED`.

## Convention «0% added noise»

Les campagnes no-noise `inversion-campaign.yaml` et `inversion-final-four-tracer.yaml` utilisent `noise.kind: none`. Le générateur fixe alors la réalisation de bruit à zéro et écrit `observed=true`; aucun générateur aléatoire n'est appelé. TracerLPM reçoit ces mêmes pseudo-observations (les appariements sont contrôlés à `1e-12`).

L'absence de bruit ajouté ne met pas l'incertitude PyAge à zéro. Pour chaque traceur:

\[
\sigma_i=\max(0.01\,C_{obs,i},\;10^{-6}C_{max,i}).
\]

PyAge minimise donc un chi-square pondéré bien défini. Le plancher évite une division par zéro. TracerLPM conserve son objectif natif de somme de résidus relatifs absolus. La campagne de robustesse de 480 cas n'inclut pas 0%: elle utilise 1, 5, 10 et 20% et PyAge fait correspondre `sigma_i` au niveau de bruit injecté, avec le même plancher `10^-6`.

## Bornes effectives

| Modèle | Paramètre logique | PyAge | TracerLPM | Conversion côté PyAge |
|---|---|---:|---:|---|
| EMM | `tau` | [0.1, 200] yr | [0.1, 200] yr | `mu=tau` |
| EPM | `tau` | [0.1, 200] yr | [0.1, 200] yr | voir ci-dessus |
| EPM | `eta` / `r` | `eta` [1.01, 11] | `r` [0.01, 10] | `eta=1+r` |
| DM | `tau` / `mu` | `tau` [0.1, 200] yr | `tau` [0.1, 200] yr | `mu=tau` |
| DM | `DP` | [0.001, 3] | [0.001, 3] | `sigma=tau*sqrt(2DP)`; il n'existe pas de borne rectangulaire indépendante sur `sigma` |

Les valeurs d'initialisation sont multiples mais ne changent pas ces bornes. Le classeur qualifié est `TracerLPM_V_1_0_FourTracers_v17.xlsm` et l'add-in est `TracerLPMfunctions_64_v_1.xll`; leurs SHA-256 figurent dans `validation/tracerlpm/config/runner-config.robustness.local.yaml`.

## Sources

- `validation/tracerlpm/benchmark/scripts/summarize_robustness_study.py`
- `validation/tracerlpm/benchmark/scripts/build_qualification_report.py`
- `validation/tracerlpm/benchmark/scripts/mappings.py`
- `validation/tracerlpm/benchmark/scripts/generate_inversion_pilot.py`
- `validation/tracerlpm/benchmark/scripts/invert_pyage_pilot.py`
- `C:\pyage-runs\article-v1\article_package\tables\table3_pyage_tracerlpm_summary.json`
