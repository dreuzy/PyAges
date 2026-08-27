# Audit final v28 — manuscrit, code courant et campagne canonique

Date de l'audit : 27 août 2026. Périmètre strictement en lecture seule pour le code, le manuscrit et la campagne. Seuls les quatre livrables sous `audit/` ont été créés.

## Verdict exécutif

Le contrôle final ne peut pas approuver le gel du manuscrit : `PyAge_v1.0_revised_v28_code_audit_sync.docx` est absent des emplacements locaux inspectés. La dernière version PyAge trouvée dans Downloads est la v23 ; elle n'a pas été utilisée comme substitut, conformément au cahier d'audit.

La campagne canonique est disponible sous `C:\pyage-runs\article-v1`, avec `article_package/` directement sous cette racine — et non sous l'intermédiaire `campaign/` indiqué dans la demande. Son manifest déclare la campagne terminée le 27 août 2026 à 09:16:58 et toutes les étapes `success`. Les fichiers machine-readable demandés sont présents et ont été lus directement.

Réponses obligatoires :

1. **Is Table 1 scientifically consistent with the current code? `NO — NOT ASSESSABLE`.** Aucun mismatch scientifique n'est démontré, mais aucune ligne de la v28 n'a pu être vérifiée et `YES` exige que tous les contrôles soient `MATCH`.
2. **Do all audited numerical values in manuscript v28 match the canonical article-v1 campaign? `NO — NOT ASSESSABLE`.** Les valeurs canoniques sont disponibles et cohérentes ; les cellules v28 ne sont pas accessibles, donc aucun contrôle complet ne peut recevoir `MATCH` ou `ROUNDING MATCH`.

## 1. Table 1

### Modèles vérifiés côté code

Les implémentations courantes ont été inspectées pour :

- Dirac / piston flow ↔ `DiracLpm` ;
- exponential ↔ `ExponentialLpm` ;
- inverse Gaussian ↔ `InverseGaussianLpm` ;
- shifted exponential ↔ `ExponentialShiftedLpm` ;
- uniform / linear piston flow ↔ `UniformLpm` ;
- gamma ↔ `GammaLpm` ;
- double Dirac ↔ `DiracDoubleLpm` ;
- shifted inverse Gaussian ↔ `InverseGaussianShiftedLpm` ;
- Dirac + shifted exponential ↔ `MixExponentialShiftedLpm` ;
- Weibull ↔ `WeibullLpm` ;
- shape-free ↔ `ShapeFreeNOldBinLpm`.

Le registre contient en outre `DiracDouble1SetLpm`. Sans Table 1 v28, son inclusion ou son omission intentionnelle ne peut pas être décidée.

### Matches

Aucun `MATCH` manuscrit ↔ code ne peut être attribué sans lire la v28. Les points suivants sont toutefois confirmés **côté code uniquement** :

- inverse Gaussian : `mu` est la moyenne physique, `sigma` l'écart-type physique, avec `shape=(sigma/mu)^2`, `scale=mu^3/sigma^2`, `loc=0` ;
- shifted inverse Gaussian : support `(shift,∞)`, moyenne totale `shift+mu`, déplacement cohérent du PDF/CDF/PPF et moment partiel `shift*F_X+M1_X` ;
- double Dirac : positions `mu1` et `mu1+mu2`, avec `mu2` en années dans la classe et le YAML courants ;
- Dirac + shifted exponential : Dirac en `mu1`, exponentielle à partir de `mu1+shift`, échelle `mu2`, masses `rate` et `1-rate`, normalisées ;
- uniform : support `[tmin,tmin+delta]`, où `delta` est une largeur ;
- gamma : shape `k`, scale `scale`, moyenne `k*scale` ;
- Weibull : shape `k`, scale `lambda`, moyenne `lambda*Gamma(1+1/k)` ;
- shape-free : bins piecewise-uniform configurables, stick breaking logistic normalisé, dernier intervalle fermé à droite et support fini dans les deux modes actuels.

Les tests analytiques trouvés couvrent les moments physiques IG, normalisation/CDF/PPF, masses discrètes, moments partiels continus et shape-free. Aucun test n'a été relancé.

### Metadata issues

1. `data_core/data_lpm/mix_exp_shifted/params.yaml` omet l'unité du paramètre `rate` et donne à son prior l'unité `year`. Le runtime déclare correctement `rate` dimensionless. Statut : `METADATA ISSUE`.
2. `dirac_double/params.yaml` omet l'unité au niveau du paramètre `rate`, tandis que le runtime emploie une chaîne vide et le prior `-`. Statut : `METADATA ISSUE` de représentation, sans effet sur la loi.

### Scientific mismatches

Aucun `SCIENTIFIC MISMATCH` n'est prouvé avec les sources disponibles. Cela ne constitue pas un match : la comparaison v28 manque entièrement.

### Corrections proposées

- Fournir le DOCX v28 exact et reprendre toutes les cellules de Table 1, y compris le texte immédiatement sous la table.
- Dans une tâche d'édition de code séparée et autorisée, remplacer l'unité de prior `year` de `mix_exp_shifted.rate` par `-` et ajouter explicitement l'unité dimensionless au paramètre.
- Uniformiser la représentation dimensionless de `dirac_double.rate`.

Le détail ligne par ligne se trouve dans `audit/table1_manuscript_code_audit.csv`. Les seuls écarts nécessitant une décision sont résumés dans `audit/table1_code_audit.md`.

## 2. Numerical cross-check

Toutes les valeurs ci-dessous sont confirmées comme **références canoniques**. Elles ne sont pas qualifiées de `MATCH` avec la v28, car le manuscrit n'a pas pu être lu.

### Table 3

Le fichier canonique contient 480 cas appariés. Il couvre les niveaux de bruit ajouté 1 %, 5 %, 10 % et 20 %. La présence, la formulation et les éventuelles lignes 0 % de la Table 3 v28 ne sont pas vérifiables. Les 480 lignes et leurs colonnes d'erreur existent dans `table3_pyage_tracerlpm_cases.csv` ; la comparaison cellule par cellule reste `NOT ASSESSABLE`.

### Appendix D

Recalcul direct sur les 480 lignes, tolérance de tie `1e-12` :

| Mesure | PyAge | TracerLPM | Ties |
|---|---:|---:|---:|
| Common L2 plus faible | 461 | 19 | 0 |
| Common L1 plus faible | 111 | 369 | 0 |
| Erreur absolue MTT plus faible | 208 | 272 | 0 |
| Erreur absolue du second paramètre plus faible | 204 | 233 | 43 |

Médianes canoniques : L1 `0.179228060342258 / 0.180858783466857` et L2 `0.0134959450681502 / 0.0163958229341983` pour PyAge / TracerLPM.

Ces effectifs coïncident avec ceux annoncés dans le cahier d'audit, mais leur présence réelle dans la v28 ne peut pas être confirmée.

### Table 4

`table4.csv` contient 19 lignes complètes. Les agrégats canoniques recalculés sont : `32.0634 %`, `26.5636 %`, `8.64992 %`, `40.8456 %`, `34.1908 %` et `10.9750 %`, qui s'arrondissent respectivement à `32.1 %`, `26.6 %`, `8.6 %`, `40.8 %`, `34.2 %` et `11.0 %`.

La médiane des 19 corrélations `mu–t0`, calculées sur les cinq chaînes retenues et en conservant les paires de lignes, vaut `-0.950562376829497`.

Le cas 9 cible `(mu,t0)=(10,30)` et donne un MTT postérieur `40.27493083507471 [37.89844425648734–43.74484358770655]`, soit `40.27 [37.90–43.74]` à l'arrondi demandé.

La comparaison des 19 lignes avec les cellules v28 reste `NOT ASSESSABLE`.

### Appendix B

`shifted_exponential_posterior_summaries.csv` contient 57 lignes, soit `19 cas × (mu,t0,mtt)`, avec médiane, q10/q90, q2.5/q97.5, split-Rhat et ESS. L'Appendix B v28 étant absent, toutes ses cellules restent `NOT ASSESSABLE`.

### Appendix C

Campagne Holten uniforme-z : 7 puits, 28 fractions, MAE `0.005454900679953717`, médiane absolue `0.0038147795762492505`, RMSE `0.007045820382494235`, maximum `0.017993492720799198`, `28/28` sous `0.02`, maximum de résidu standardisé `1.7995269834584595`.

Campagne Dirichlet(1) actuelle : MAE `0.007449778065057172`, médiane absolue `0.005202970729666384`, RMSE `0.009681203964532094`, maximum `0.02109854984167281`, maximum de résidu standardisé `1.8523684135855618`, RMSE standardisé `0.7918140522604604`, split-Rhat maximal `1.00868747599506`, ESS minimal `909.6698321813973`.

Ces statistiques proviennent de la nouvelle campagne canonique, mais les cellules v28 restent `NOT ASSESSABLE`.

### Ploemeur

Aucune réinterprétation de F11 n'a été faite. Références canoniques t50 médiane `[q10–q90]` :

- F09 full record : `4.18214276748354 [1.5347973473410734–8.084426157245694]` ;
- F09 2014–2015 only : `13.293199181279455 [6.209902953217556–20.275530815577365]` ;
- F11 full record : `85.38361427202526 [84.69608000853371–85.98655860286935]` ;
- F11 2014–2015 only : `57.403466756850555 [52.564688040862734–61.45252762137039]`.

Sur ces quatre calibrations shifted-exponential : split-Rhat maximal `1.0040421643594268`, ESS minimal `1741.1246183425499`, cinq chaînes. Les effectifs d'observations sont détaillés dans le CSV d'audit. La v28 reste `NOT ASSESSABLE`.

### Appendix A

La campagne forward fraîche contient 270 cas : PFM `45`, EMM `45`, EPM `90`, DM `90`. Son statut reste exactement `measured_not_yet_qualified` ; ce rapport ne le requalifie pas.

| Famille | Bias | MAE | RMSE | Maximum absolu | Maximum symétrique relatif |
|---|---:|---:|---:|---:|---:|
| PFM | -1.1172298574254291e-14 | 1.449892049072433e-13 | 2.6976752213921954e-13 | 5.115907697472721e-13 | 0.03278688524590153 |
| EMM | 0.0001688873578763962 | 0.00027842080235354876 | 0.0007249761782995034 | 0.0029217953197715474 | 0.08003512339022457 |
| EPM | 0.0001882927543092967 | 0.00029875060170673134 | 0.000990181925941624 | 0.006123680040168722 | 0.04440892098500626 |
| DM | 0.00029412441848293764 | 0.0003325549353834 | 0.0009711236140374849 | 0.006106885850122978 | 0.02220446049250313 |

La v28 n'étant pas disponible, ni ces cellules ni la qualification ni l'éventuel libellé « expérience historique distincte » pour les 133 cas ne peuvent être vérifiés.

## 3. Blockers

Aucune vraie divergence manuscrit ↔ code ou manuscrit ↔ campagne ne peut être établie, car la source manuscrit requise manque. En conséquence, il n'existe aucun `SCIENTIFIC MISMATCH` ni `MISMATCH` prouvé dans les deux CSV.

Le blocage opérationnel avant gel est néanmoins absolu : l'audit demandé n'est pas complet sans la v28 et les deux réponses obligatoires restent `NO — NOT ASSESSABLE`.

## 4. Safe manuscript corrections

Aucune instruction sûre de type « Page/section/table X: replace `...` with `...` » ne peut être émise sans connaître le texte, la pagination et les cellules de la v28. Donner une substitution à partir de la v23 ou du seul cahier d'audit constituerait une correction non vérifiée.

Action sûre : placer `PyAge_v1.0_revised_v28_code_audit_sync.docx` dans les fichiers de travail ou l'attacher, puis exécuter la passe différentielle. Les valeurs canoniques exactes à utiliser pour cette passe sont consignées dans `audit/v28_canonical_numeric_crosscheck.csv`.

Correction de métadonnée code proposée, à ne faire que dans une tâche d'édition distincte :

> `data_core/data_lpm/mix_exp_shifted/params.yaml`, paramètre `rate`: replace prior unit `year` with `-`, and add parameter unit `-`.

## 5. No action required

Les blocs suivants sont entièrement confirmés **dans leurs sources propres** et ne nécessitent pas de recalcul de campagne :

- conversion SciPy et moments physiques de l'inverse Gaussian courante ;
- shift, moyenne totale et moment partiel de la shifted inverse Gaussian ;
- positions `mu1` et `mu1+mu2` et unité année de `mu2` dans le code courant ;
- loi et normalisation du mélange Dirac + shifted exponential ;
- stick breaking et fermeture des fractions du shape-free ;
- effectifs et agrégats canoniques TracerLPM ci-dessus ;
- 19 cas et agrégats canoniques shifted-exponential ;
- statistiques Holten uniforme-z et Dirichlet(1) ;
- quatre résumés Ploemeur, sans interprétation nouvelle de F11 ;
- campagne forward de 270 cas avec statut non requalifié.

Cette liste confirme les références techniques, pas leur transcription dans le manuscrit. Aucun bloc de la v28 ne peut être déclaré prêt à geler avant fourniture du DOCX.
