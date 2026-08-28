# Rapport de correction — unité `mu2`, politique SciPy et métrique forward

**Projet :** PyAge  
**Date de l'intervention :** 27 août 2026  
**Périmètre :** métadonnées du double Dirac, dépendance SciPy, documentation de
la métrique de vérification forward  
**Nature de l'intervention :** correction de métadonnées, packaging, tests et
documentation ; aucun changement des calculs scientifiques

## 1. Résumé exécutif

L'intervention a résolu trois incohérences distinctes :

1. la classe Python du double Dirac déclarait une unité vide pour `mu2`, alors
   que le YAML et le calcul l'interprétaient déjà comme un délai additionnel en
   années ;
2. trois déclarations SciPy se contredisaient : version scientifique 1.14.1,
   `install/environment.yml` à 1.18.0 et `install/constraints.txt` à 1.18.1 ;
3. une documentation active devait préciser que la campagne forward historique
   avait calculé l'écart relatif sans plancher `1e-14`, sans réécrire le rapport
   historique protégé par checksum.

Les corrections ont été effectuées sans modifier de formule, de valeur par
défaut, de résultat scientifique, de manifeste historique, de checksum ou
d'ancienne sortie.

Les chemins scientifiques dépendant de SciPy ont été testés avec la pile
historique SciPy 1.14.1 et avec la pile utilisateur SciPy 1.18.1. Les deux
exécutions ont réussi les 315 tests ciblés.

## 2. Double Dirac : correction de l'unité de `mu2`

### 2.1 Constat

Le modèle implémente déjà les deux positions physiques suivantes :

\[
t_1 = \mu_1,
\qquad
t_2 = \mu_1 + \mu_2.
\]

Dans `pyage/lpm/models/dirac_double.py`, la méthode
`get_dirac_double_time()` retournait déjà exactement ces deux positions. Les
méthodes CDF, quantile, moyenne, écart-type et visualisation utilisaient elles
aussi `mu2` comme délai additionnel.

Le fichier `data_core/data_lpm/dirac_double/params.yaml` déclarait déjà les
unités de `mu1` et `mu2` comme `year`. La seule incohérence identifiée était la
métadonnée runtime de la classe Python :

```python
parameter_units = {"mu1": "year", "mu2": "", "rate": ""}
```

### 2.2 Correction

La déclaration est maintenant :

```python
parameter_units = {"mu1": "year", "mu2": "year", "rate": ""}
```

Fichier concerné : `pyage/lpm/models/dirac_double.py`.

### 2.3 Garantie de non-modification scientifique

Aucune des parties suivantes n'a été changée :

- valeurs par défaut `mu1=10`, `mu2=5`, `rate=0.2` ;
- position du premier Dirac ;
- position du second Dirac ;
- pondérations des deux masses ;
- CDF ou quantile ;
- moyenne ou écart-type ;
- convolution ou résultats de référence.

Le changement est donc uniquement une correction de métadonnées.

### 2.4 Test ajouté

`tests/lpm/test_discrete_lpm_analytics.py` vérifie maintenant explicitement :

- `model.parameter_units["mu1"] == "year"` ;
- `model.parameter_units["mu2"] == "year"` ;
- les positions sont `[mu1, mu1 + mu2]` ;
- la CDF conserve les masses attendues aux deux positions.

## 3. Politique SciPy

### 3.1 Vérification des versions publiées

Les métadonnées officielles de PyPI ont été interrogées pour les versions
retenues :

| SciPy | `Requires-Python` | Roues CPython observées utiles à PyAge |
| --- | --- | --- |
| 1.14.1 | `>=3.10` | 3.12 et 3.13 ; aucune roue 3.14 |
| 1.16.1 | `>=3.11` | 3.12, 3.13 et 3.14 |
| 1.18.1 | `>=3.12` | 3.12, 3.13 et 3.14 |

Sources officielles :

- <https://pypi.org/project/scipy/1.14.1/>
- <https://pypi.org/project/scipy/1.16.1/>
- <https://pypi.org/project/scipy/1.18.1/>

L'API Anaconda a également confirmé la présence de SciPy 1.14.1 dans le canal
conda-forge, notamment avec des paquets Windows CPython 3.12 :
<https://api.anaconda.org/release/conda-forge/scipy/1.14.1>.

### 3.2 Appels SciPy recensés et chemins testés

L'inventaire du code et le corpus de tests ciblé portent notamment sur :

- `scipy.stats.invgauss`, `expon`, `gamma`, `uniform`, `weibull_min` et
  `rv_continuous` ;
- CDF, PPF/quantiles, densités et moments ;
- `scipy.special.ndtr`, `log_ndtr`, `gammainc`, `gamma` et `expit` ;
- `scipy.integrate.quad` pour les références indépendantes ;
- interpolation linéaire ;
- `scipy.optimize.brentq` et `minimize` ;
- convolution continue et discrète ;
- paramétrisation inverse-gaussienne et optimisation/calibration.

### 3.3 Séparation des deux environnements

Deux environnements sont désormais explicitement distingués.

#### Environnement de reproduction scientifique

`install/environment.yml` conserve la pile scientifique enregistrée pour la
campagne historique :

- Python 3.12 ;
- NumPy 2.1.2 ;
- SciPy 1.14.1 ;
- pandas 2.2.3 ;
- Matplotlib 3.10.8.

L'environnement Conda porte désormais le nom
`pyage-article-reproduction`. Il ne doit pas être présenté comme
l'environnement utilisateur PyAge 1.0 ni comme une qualification rétroactive
de l'archive sur des dépendances plus récentes.

#### Environnement utilisateur PyAge 1.0

`install/constraints.txt` conserve le gel utilisateur plus récent :

- NumPy 2.5.2 ;
- SciPy 1.18.1 ;
- pandas 3.0.5 ;
- Matplotlib 3.11.1 ;
- autres dépendances directes et outils épinglés dans ce fichier.

Ce gel portable n'est pas présenté comme un verrou bit à bit de toutes les
dépendances transitives.

### 3.4 Plage déclarée dans `pyproject.toml`

La compatibilité SciPy est maintenant bornée par version de Python :

```toml
"scipy>=1.14.1,<1.19; python_version < '3.14'",
"scipy>=1.16.1,<1.19; python_version >= '3.14'",
```

Cette politique permet :

- de conserver SciPy 1.14.1 sur Python 3.12 et 3.13, notamment pour la
  reproduction scientifique ;
- d'éviter de déclarer SciPy 1.14.1 comme installation binaire praticable sur
  Python 3.14, faute de roue correspondante ;
- de borner provisoirement l'environnement utilisateur à la série 1.18
  effectivement testée, plutôt que d'accepter automatiquement une future
  série mineure non qualifiée.

### 3.5 CI et archives futures

La CI conserve la matrice utilisateur sous contraintes pour Python 3.12, 3.13
et 3.14. Une matrice supplémentaire teste les bornes basses suivantes :

- Python 3.12 avec SciPy 1.14.1 ;
- Python 3.13 avec SciPy 1.14.1 ;
- Python 3.14 avec SciPy 1.16.1.

Le job Conda est renommé pour indiquer qu'il valide l'environnement historique
de l'article.

Les futurs paquets d'article incluront séparément :

- `provenance/environment/constraints.txt`, identifié comme contraintes
  utilisateur PyAge 1.0 ;
- `provenance/environment/article-reproduction-environment.yml`, identifié
  comme environnement historique de reproduction.

Cette modification ne réécrit aucun paquet ou manifeste déjà archivé.

## 4. Documentation de la métrique forward

### 4.1 Définition historique effective

Pour la campagne historique de 133 comparaisons, le calcul était :

\[
\epsilon_\mathrm{rel} =
\frac{|C_\mathrm{PyAge}-C_\mathrm{reference}|}
{|C_\mathrm{reference}|}
\]

lorsque la référence était non nulle. Lorsque la référence était exactement
nulle, la valeur enregistrée était `NaN`.

Aucun plancher `1e-14` n'était appliqué au dénominateur.

### 4.2 Correction appliquée

La définition correcte est maintenant explicitée dans la documentation active :

- `article/s3_forward_verification/README.md` ;
- `docs/science/validation.md`.

Un test documentaire vérifie la présence de la formule, du cas `NaN`, de
l'absence de plancher et de la distinction avec le rapport historique.

### 4.3 Préservation de l'historique

Le rapport historique
`docs/reports/convolution_grid_sensitivity_2026-08-26.md`, qui contient le
texte ancien, n'a pas été réécrit pendant cette intervention.

Son hash Git de contenu relevé avant et après l'opération est resté identique :

```text
60de72ec6dccf2d669f65e7ac62f7e37e8909781
```

Aucun ancien manifeste, checksum, rapport archivé ou résultat n'a été modifié
pour donner l'impression que l'ancienne archive était déjà qualifiée selon la
documentation corrigée.

## 5. Vérifications exécutées

### 5.1 Pile scientifique

Environnement local :

- Python 3.12.4 ;
- NumPy 2.1.2 ;
- SciPy 1.14.1.

Résultat :

```text
315 passed
```

### 5.2 Pile utilisateur récente

Un environnement virtuel neuf a été créé et installé avec
`install/constraints.txt` :

- Python 3.12.4 ;
- NumPy 2.5.2 ;
- SciPy 1.18.1.

Résultats :

```text
No broken requirements found.
315 passed
```

### 5.3 Tests de métadonnées, documentation et packaging

Les tests du double Dirac, des YAML LPM, des contrats documentaires et du
paquet d'article ont également été exécutés :

```text
48 passed
```

Le lint Ruff des fichiers de test concernés a réussi. Les fichiers TOML et YAML
modifiés ont été chargés sans erreur. `git diff --check` n'a signalé aucune
erreur de contenu ; les seuls messages concernaient la politique de fins de
ligne LF/CRLF du checkout Windows.

## 6. Limites et suivi

- Les exécutions locales ont été réalisées avec Python 3.12.
- La disponibilité des roues Python 3.13 et 3.14 a été vérifiée dans les
  métadonnées officielles de PyPI.
- Les exécutions Python 3.13 et 3.14 sont configurées dans la CI mais n'ont pas
  été exécutées localement lors de cette intervention.
- Le dépôt comportait déjà de nombreuses modifications non validées. Elles ont
  été conservées ; ce rapport ne les attribue pas à la présente opération.
- Toute future série SciPy 1.19 ou ultérieure devra être qualifiée avant
  élargissement de la borne `<1.19`.

## 7. Conclusion

L'incohérence `mu2` était uniquement une incohérence de métadonnées. La classe
Python et le YAML expriment maintenant la même unité, sans changement du modèle
double Dirac.

La politique SciPy distingue désormais clairement la reproduction historique
sur SciPy 1.14.1 de l'environnement utilisateur sur SciPy 1.18.1. Les plages du
paquet et la CI tiennent compte de Python 3.14 sans déclarer de version SciPy
impossible ou non testée.

Enfin, la documentation active décrit fidèlement la métrique forward
historique sans modifier les archives protégées. Les deux piles SciPy testées
produisent un résultat entièrement passant sur le corpus scientifique ciblé.
