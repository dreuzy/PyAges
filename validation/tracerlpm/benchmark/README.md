# Benchmark PyAge–TracerLPM

Ce répertoire contient toute la validation scientifique ciblée. Il est isolé du
cœur de PyAge et du code COM du runner. La Phase 1 prépare les cas et les
références sans ouvrir Excel.

## Générer les entrées communes

Depuis la racine du dépôt :

```powershell
python -m validation.tracerlpm.benchmark.scripts.generate_inputs
python -m validation.tracerlpm.benchmark.scripts.generate_references
python -m validation.tracerlpm.benchmark.scripts.generate_observations
python -m validation.tracerlpm.benchmark.scripts.compare_pyage
python -m validation.tracerlpm.benchmark.scripts.study_pyage_convergence
```

Le générateur lit `configs/campaign.yaml`, écrit les CSV dans
`inputs/synthetic/` et crée `inputs/manifest.yaml`. Les fichiers sont
déterministes : une exécution répétée produit les mêmes octets et les mêmes
SHA-256. La seconde commande produit les 270 résultats forward de référence
(5 entrées × 18 paramétrisations × 3 dates) sans ouvrir Excel. La troisième
produit les observations d’inversion sans bruit et avec les graines déclarées.
La dernière commande exécute le chemin de convolution de production PyAge et
écrit le rapport dans `generated/pyage_comparison/`. Elle n’ouvre pas Excel.
La commande suivante répète cette mesure aux résolutions déclarées dans le YAML
et écrit `generated/pyage_convergence/`.

## Vérifier la Phase 1

```powershell
python -m pytest validation/tracerlpm/benchmark/tests -q
```

La campagne Excel ne doit pas être lancée avant la revue des entrées, mappings
et références de cette phase.

## Pilote TracerLPM de Phase 2

Après compilation du runner, le pilote isolé s’appelle depuis la racine avec :

```powershell
validation\tracerlpm\src\TracerLpmRunner\bin\x64\Release\net8.0-windows\TracerLpmRunner.exe `
  --config validation\tracerlpm\config\runner-config.local.yaml `
  --cases validation\tracerlpm\benchmark\configs\tracerlpm-pilot.yaml
```

Il importe `constant.csv` dans les colonnes SF6 et NO3-N d’une copie de travail,
neutralise décroissance et temps non saturé, exécute deux courbes PFM identiques
et exporte les 61 âges et couples calculés. Le classeur source reste inchangé.

Après exécution, le rapport brut retenu est archivé et comparé avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.compare_tracerlpm_pilot `
  --run-json validation/tracerlpm/output/<run-id>.json
```

Le même comparateur traite `configs/tracerlpm-pfm-ramp.yaml`; ses rapports sont
séparés par `case_id` sous `generated/tracerlpm_pilot/`.

Les cas continus EMM utilisent le même contrat avec une date effective
TracerLPM explicitement consignée. Ils sont définis dans
`configs/tracerlpm-emm-constant.yaml` et `configs/tracerlpm-emm-step.yaml`.
Le dernier cas de la famille est `configs/tracerlpm-emm-multi-peak.yaml`.

La famille EPM est définie dans `configs/tracerlpm-epm-multi-peak.yaml`. Le
champ YAML `model_parameter` est la valeur saisie dans TracerLPM, soit le ratio
physique `r=x*/x`. Le comparateur applique explicitement `eta=1+r` avant
d’appeler l’exponentielle décalée de PyAge. Les deux cellules de paramètre
Excel sont relues avant calcul ; le cas est interrompu si Excel a restauré une
valeur par défaut.

La famille DM est définie dans `configs/tracerlpm-dm-multi-peak.yaml`, avec
`DP=0.02`, `0.2` et `1`. Ici `model_parameter` est directement le paramètre de
dispersion TracerLPM. Le comparateur construit la loi inverse gaussienne PyAge
avec `mu=tau` et `sigma=tau*sqrt(2*DP)`. Les rapports retiennent séparément les
écarts à la date demandée et à la date semestrielle effectivement utilisée par
TracerLPM.

## Conventions principales

- temps en années décimales ;
- grille mensuelle positionnée au milieu du mois ;
- concentrations synthétiques en unité arbitraire `au` ;
- PFM/EMM : `tau` est l’âge moyen ;
- EPM : `eta=1+r_TracerLPM`, puis `mu=tau/eta` et
  `shift=tau*(1-1/eta)` ;
- DM : `mu=tau`, `sigma=tau*sqrt(2*DP)` ;
- graines aléatoires toujours déclarées dans le YAML et le manifeste.

## Pilotes d’inversion EMM, EPM et DM

`configs/inversion-campaign.yaml` définit le cas sans bruit à `tau=20 ans` et
les trois initialisations `5`, `20`, `80 ans`. Les observations CFC sont créées
par la quadrature indépendante puis inversées par PyAge avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.generate_inversion_pilot
python -m validation.tracerlpm.benchmark.scripts.invert_pyage_pilot
```

Le pilote TracerLPM est défini par
`configs/tracerlpm-inversion-emm-pilot.yaml`. Les mêmes CFC-11, CFC-12 et
CFC-113 que dans PyAge sont aliasés dans les canaux SF6, 3H et NO3-N du classeur
Example 1. Le canal 3H est rendu stable en imposant son taux de décroissance à
zéro. Le runner vérifie les trois imports, sélectionne les trois traceurs, évalue les
trois départs, puis appelle Solver une seule fois depuis le meilleur. La formule
d’objectif réellement utilisée (`=$F$25+$J$25+$K$25`) et son libellé
`3H,SF6,NO3-N` sont exportés.

Résultat symétrique actuel : PyAge estime `19.9982589 ans` et TracerLPM
`19.9338202 ans`. Les erreurs respectives de `0.00174113` et `0.0661798 an`
satisfont le seuil pilote de `0.5 an`. Le rapport contient une table explicite
du paramètre vrai et des deux paramètres estimés.

Le fichier central CFC-12 sans en-tête n’est pas modifié : le pilote utilise
`observations/normalized-cfc12.csv`, copie normalisée et hashée.

Les cas à deux paramètres utilisent exactement les mêmes trois observations :

```powershell
python -m validation.tracerlpm.benchmark.scripts.study_inversion_surface --model EPM
python -m validation.tracerlpm.benchmark.scripts.study_inversion_surface --model DM
python -m validation.tracerlpm.benchmark.scripts.compare_two_parameter_inversion --model EPM --run-json validation/tracerlpm/output/<run-epm>.json
python -m validation.tracerlpm.benchmark.scripts.compare_two_parameter_inversion --model DM --run-json validation/tracerlpm/output/<run-dm>.json
```

| Modèle | Paramètre | Vrai | PyAge | TracerLPM | Seuil relatif | Verdict |
|---|---:|---:|---:|---:|---:|---|
| EPM | `tau` | 20 | 20.0000005 | 19.7464101 | 5 % | conforme |
| EPM | `r` | 2 | 2.0000001 | 1.9624315 | 10 % | conforme |
| DM | `tau` | 20 | 19.9995879 | 19.7303094 | 5 % | conforme |
| DM | `DP` | 0.2 | 0.2000672 | 0.2057685 | 10 % | conforme |

PyAge optimise `eta` pour EPM ; le rapport le convertit en `r=eta-1` avant la
comparaison. Les surfaces indépendantes 32 × 32 ont leur minimum exactement
sur les paramètres vrais pour EPM et DM. Les CSV complets et leurs résumés sont
écrits sous `generated/inversion/<case_id>/`.

## Première campagne bruitée

`configs/inversion-noisy-campaign.yaml` ajoute un bruit gaussien multiplicatif
de 1 %, avec les graines 101 à 105, aux trois CFC. Les observations, inversions
PyAge, cas Excel et agrégats se régénèrent avec :

```powershell
python -c "from pathlib import Path; from validation.tracerlpm.benchmark.scripts.generate_inversion_pilot import generate; generate(config_path=Path('validation/tracerlpm/benchmark/configs/inversion-noisy-campaign.yaml'))"
python -c "from pathlib import Path; from validation.tracerlpm.benchmark.scripts.invert_pyage_pilot import invert; invert(config_path=Path('validation/tracerlpm/benchmark/configs/inversion-noisy-campaign.yaml'))"
python -m validation.tracerlpm.benchmark.scripts.prepare_noisy_tracerlpm_campaign
python -m validation.tracerlpm.benchmark.scripts.summarize_noisy_campaign
```

Les dix inversions PyAge convergent. Sur cinq réalisations, EPM donne une
moyenne `tau=20.1302` (RMSE 1.9763 ans) et `r=2.3213` (RMSE 0.4211) ; DM donne
`tau=19.7749` (RMSE 2.2814 ans) et `DP=0.19854` (RMSE 0.05446). Cet effectif est
un diagnostic initial et non une estimation robuste de l'incertitude.

Le lot TracerLPM correspondant est défini dans
`configs/tracerlpm-inversion-noisy-campaign.yaml`. Le diagnostic a montré que
Solver terminait correctement : l'attente provenait de la fermeture du processus
Excel après le calcul. Le runner limite désormais cette attente puis termine
uniquement le PID Excel qu'il possède. Les dix cas TracerLPM ont été exécutés.

Sur les cinq réalisations, TracerLPM donne pour EPM `tau=19.6756` (RMSE 1.8360)
et `r=2.2812` (RMSE 0.4453), puis pour DM `tau=19.3394` (RMSE 2.2378) et
`DP=0.21032` (RMSE 0.05282). La dispersion est donc du même ordre que PyAge.
Les valeurs individuelles ne sont toutefois pas identiques, ce qui confirme la
sensibilité des inversions à deux paramètres au bruit et aux détails numériques.

## Monte-Carlo PyAge à 30 réalisations

`configs/inversion-monte-carlo-01.yaml` décrit de façon compacte 30 graines par
modèle à 1 % de bruit. Les 60 inversions parallèles et leur agrégation s'exécutent
avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.run_monte_carlo_pyage
python -m validation.tracerlpm.benchmark.scripts.summarize_monte_carlo
```

Les 60 cas convergent. EPM donne `tau=20.401 ± 1.493` et `r=2.158 ± 0.340` ;
DM donne `tau=20.509 ± 1.990` et `DP=0.1885 ± 0.0589` (moyenne ± écart type).
Les quantiles empiriques 2,5–97,5 % sont respectivement `[17.33, 22.59]` et
`[1.57, 2.76]` pour EPM, puis `[16.19, 23.95]` et `[0.101, 0.301]` pour DM.

Un contrôle important a été ajouté au pilote : un optimiseur ne peut plus
remplacer une initialisation par une solution dont l'objectif est moins bon.
Les premières apparences de minima DM extrêmes provenaient de cette dégradation
numérique, et non d'une meilleure équifinalité. DM utilise désormais L-BFGS-B,
EPM Powell, sans modification du cœur de PyAge.

## Gain d'information du SF6

La variante `configs/inversion-monte-carlo-01-sf6.yaml` répète les mêmes 30
graines et les mêmes perturbations CFC en ajoutant un quatrième résidu SF6. Elle
s'exécute et se compare avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.run_monte_carlo_pyage `
  --config validation/tracerlpm/benchmark/configs/inversion-monte-carlo-01-sf6.yaml
python -m validation.tracerlpm.benchmark.scripts.compare_sf6_information
```

Le gain est important. En EPM, le SF6 réduit la RMSE de `tau` de 85,1 % et celle
de `r` de 36,6 %. En DM, les réductions atteignent 87,4 % pour `tau` et 76,1 %
pour `DP`. La corrélation `tau–DP` passe de `-0.959` à `0.248`, ce qui démontre
une forte réduction de l'équifinalité locale. Le rapport complet est sous
`generated/sf6-information-gain/`.

TracerLPM connaît nativement les quatre noms CFC-11, CFC-12, CFC-113 et SF6,
mais le classeur Example 1 qualifié n'expose que trois canaux neutres. Les
canaux hélium ne doivent pas être détournés car leurs appels XLL portent des
options physiques spéciales. La comparaison à quatre traceurs nécessite donc
une copie de classeur reconfigurée avec un emplacement `EMPTY`, puis un nouveau
hash et un nouveau mapping ; le classeur qualifié actuel reste inchangé.

## Étude de robustesse : largeurs, âges et bruit jusqu'à 20 %

L'étude conserve systématiquement les quatre traceurs `CFC-11`, `CFC-12`,
`CFC-113` et `SF6`. Elle ne compare pas de sous-ensembles de traceurs.

`configs/robustness-width-noise.yaml` décrit 320 cas à `tau=20` : quatre
largeurs EPM (`r=0.05, 0.5, 2, 9`), quatre largeurs DM
(`DP=0.02, 0.2, 0.5, 1`), quatre niveaux de bruit (`1, 5, 10, 20 %`) et dix
graines appariées. `configs/robustness-age-noise.yaml` ajoute 160 cas à
`tau=5` et `tau=50`, pour les largeurs intermédiaire et très large et les
bruits `10` et `20 %`. Les cas `tau=20` de la première phase sont réutilisés :
la synthèse couvre ainsi `tau=5, 20, 50` sans recalcul redondant.

Les observations et inversions PyAge se génèrent avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.run_monte_carlo_pyage `
  --config validation/tracerlpm/benchmark/configs/robustness-width-noise.yaml
python -m validation.tracerlpm.benchmark.scripts.run_monte_carlo_pyage `
  --config validation/tracerlpm/benchmark/configs/robustness-age-noise.yaml
python -m validation.tracerlpm.benchmark.scripts.prepare_robustness_study
```

La dernière commande crée deux files indépendantes de 240 cas :
`tracerlpm-robustness-epm.yaml` et `tracerlpm-robustness-dm.yaml`. Elles sont
exécutées avec `config/runner-config.robustness.local.yaml`. Les rapports Excel
bruts restent isolés sous `output/robustness-study/` et la synthèse se génère
avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.summarize_robustness_study
```

Les livrables consolidés sont `generated/robustness-study/summary.md`,
`summary.json` et `results.csv`. Ils donnent, pour chaque groupe de dix cas, le
taux de succès, les solutions sur les bornes, le biais, l'écart type, la RMSE,
les quantiles et l'erreur de concentration recalculée.

Le rapport transversal destiné à préparer la section de qualification d'un
article se régénère ensuite avec :

```powershell
python -m validation.tracerlpm.benchmark.scripts.build_qualification_report
```

Il est écrit sous `generated/qualification-report/` avec trois livrables :
`report.md` pour l'analyse scientifique, `metrics.json` pour les indicateurs
auditables et `diagnostic-overview.png` pour la figure de synthèse. Le rapport
distingue les preuves forward, les inversions sans bruit, le gain de SF6, la
robustesse au bruit et les limites de la comparaison L2 PyAge / L1 TracerLPM.

Une campagne interrompue se reprend sans recalculer les rapports déjà valides.
Depuis une session Windows interactive où Excel est disponible, exécuter :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  validation/tracerlpm/tools/resume-robustness-campaign.ps1
```

Le script vérifie d'abord l'accès COM à Excel, relit les rapports de
`output/robustness-study/`, recrée six files équilibrées contenant uniquement
les identifiants absents, puis lance les runners et le moniteur final. Il refuse
de démarrer si un runner TracerLPM est déjà actif. Les identifiants de processus
et le manifeste exact sont enregistrés sous
`output/robustness-study/campaign/missing-launch.json`.
