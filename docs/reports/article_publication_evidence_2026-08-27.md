# Éléments factuels pour la publication PyAges

Date de l'état des preuves : 27 août 2026

Campagne examinée : `C:\pyages-runs\article-v1`

Révision du paquet et de l'archive : `1d056705ca7e44d85c5522082bc4087f4c42f310`

Version candidate du logiciel : `0.1.0b1`

## Usage de ce rapport

Ce document est un dossier de résultats, de protocoles et de réserves à faire
relire par les auteurs. Il est conçu pour permettre de retrouver chaque nombre
dans les artefacts de calcul. Il ne remplace ni l'interprétation scientifique
des auteurs ni la relecture du manuscrit, des unités, des références et des
droits sur les données.

La [politique IA actuelle de GMD](https://www.geoscientific-model-development.net/policies/ai_policy.html)
autorise l'IA pour améliorer la lisibilité, mais précise que l'IA générative ne
doit pas produire le texte ou les interprétations scientifiques du manuscrit.
En conséquence, les tableaux et faits vérifiés ci-dessous peuvent servir de
matériau de travail, mais les auteurs doivent sélectionner les résultats,
construire eux-mêmes l'argumentation, reformuler le texte et vérifier chaque
affirmation dans les sources primaires.

L'inscription Zenodo, la réservation d'un DOI et la publication du dépôt sont
explicitement différées jusqu'à la fin de toutes les validations. Aucun DOI
n'est réservé à la date de ce rapport.

## Synthèse exécutive

La campagne fraîche a terminé ses huit étapes avec un code retour nul :
vérification forward, comparaison PyAges--TracerLPM, expérience synthétique
shifted exponential, reproduction Holten H4, deux analyses Ploemeur, production
du paquet éditorial et construction de l'archive. Elle fournit une base solide
pour documenter le protocole numérique et la plupart des résultats de
l'article, avec deux limites scientifiques encore ouvertes :

1. les 270 cas de vérification forward ont été mesurés, mais aucun seuil
   d'acceptation scientifique n'a encore été défini ;
2. la sensibilité Holten au prior Dirichlet n'appartient pas à cette campagne
   stabilisée et reste à intégrer ou à référencer séparément si elle figure dans
   l'article.

| Volet | Étendue | Résultat vérifié | Statut utilisable |
| --- | ---: | --- | --- |
| Forward indépendant | 270 cas | résultats présents et métriques calculées | descriptif seulement, `measured_not_yet_qualified` |
| PyAges--TracerLPM | 480 cas appariés | 480/480 succès pour chaque outil | utilisable avec réserves sur les bornes et sans classement global des outils |
| Shifted exponential synthétique | 19 cas | tous les groupes convergés | utilisable |
| Holten H4 | 7 puits, 28 fractions | tous les groupes convergés ; erreur absolue maximale 0,017993 | utilisable |
| Ploemeur shifted exponential | 4 calibrations | toutes convergées ; mauvais ajustement F11 conservé | utilisable en exposant la discordance F11 |
| Ploemeur IG physique | 6 postérieurs | tous convergés ; équivalence numérique vérifiée | utilisable |
| Paquet éditorial | 72 artefacts | empreintes vérifiées | utilisable pour lecture et rédaction |
| Archive scientifique | 2 951 fichiers inventoriés | tailles et SHA-256 vérifiés | prête pour validation finale, pas encore déposée |

Les seuils communs de convergence MCMC sont `split-Rhat < 1.01` et
`ESS >= 300`. Tous les groupes MCMC présentés dans le paquet éditorial
satisfont ces seuils.

## Ce que signifie ici « reproduction »

Deux objectifs différents doivent être distingués dans le manuscrit et dans la
réponse aux relecteurs.

### Reproduction historique

Une reproduction historique stricte demanderait de retrouver les anciennes
sorties, les chaînes, les versions de scripts et les empreintes des campagnes
des 20--22 août. Les six inventaires historiques ne trouvent actuellement
aucun de ces ensembles complet (`0/6`). Les anciens dossiers `results/`
n'étaient pas versionnés et certaines versions de scripts ont changé. Il ne
serait pas scientifiquement correct de remplacer leurs empreintes par celles du
code actuel et de prétendre avoir restauré les anciennes campagnes.

Cette absence ne signifie pas que les nouveaux calculs ont échoué. Elle signifie
seulement que l'identité octet par octet des calculs historiques ne peut pas être
revendiquée à partir de ce checkout.

### Reproduction scientifique fraîche

La campagne `article-v1` repart du code, des configurations et des observations
conservés, produit de nouvelles chaînes et de nouveaux résultats, puis archive
les entrées, les sorties, les diagnostics et la provenance. C'est cette couche
qui soutient les résultats numériques actuels. Les anciennes sorties ne sont
utilisées ni comme entrées, ni comme initialisations, ni comme critères d'arrêt
pour Ploemeur shifted exponential et Ploemeur IG.

La campagne a été achevée au fil de plusieurs correctifs. Il ne faut donc pas
écrire que toutes les simulations ont été exécutées depuis un unique commit.
Le manifeste conserve la révision exacte de chaque étape :

| Étape | Révision Git enregistrée |
| --- | --- |
| Forward et PyAges--TracerLPM | `70967a74cce309c930000e3b09e0e59675ad0fe8` |
| Shifted exponential et Holten H4 | `a9ce92fd9de24efaf5d61f9fcf8b81958749737c` |
| Ploemeur shifted exponential | `e96016f70f408863f744456ea7fc31edc91df86a` |
| Ploemeur IG physique | `1260f5fd0fa35c9e55f31b0022a50396be05b18d` |
| Paquet et archive | `1d056705ca7e44d85c5522082bc4087f4c42f310` |

Le snapshot final contient le workflow corrigé capable de relancer l'ensemble.
Le paquet conserve en plus les sources d'exécution exactes, avec leurs
empreintes, lorsque celles-ci diffèrent du snapshot final. Cette combinaison
permet de distinguer le code qui a effectivement produit chaque résultat du
code stabilisé proposé aux futurs utilisateurs.

## Environnement numérique

Les manifestes des calculs MCMC enregistrent :

| Composant | Version |
| --- | --- |
| Python | 3.12.4 |
| NumPy | 2.1.2 |
| pandas | 2.2.3 |
| SciPy | 1.14.1 |

Le fichier `source/environment-pip-freeze.txt` de l'archive conserve
l'environnement Python complet. Il enregistre toutefois `pyages==0.1.0`, alors
que le snapshot, `CITATION.cff` et les métadonnées candidates indiquent
`0.1.0b1`. Les calculs sont liés aux révisions et aux empreintes de sources,
mais cette divergence de libellé doit être résolue ou expliquée avant le dépôt
définitif.

Les durées du manifeste sont des durées opérationnelles sur la machine de
campagne, et non un benchmark de performance. En particulier, la campagne a
été reprise après corrections et certaines étapes ont réutilisé des artefacts
déjà valides. Elles ne doivent pas être présentées comme des temps de calcul
comparables entre méthodes.

## 1. Vérification indépendante du calcul forward

### Protocole vérifié

- 270 cas au total ;
- familles LPM : piston flow model (PFM), exponential mixing model (EMM),
  exponential-piston flow model (EPM) et dispersion model (DM) ;
- matrice de référence indépendante conservée avec son empreinte SHA-256 ;
- grille adaptative configurée avec une tolérance absolue de `5e-4` fois le
  facteur d'échelle, une tolérance relative de `0.02`, un facteur de courbure
  linéaire de `0.1`, au plus 20 subdivisions et 20 000 bins.

### Résultats par famille

| Famille | Cas | Biais | MAE | RMSE | Erreur absolue maximale |
| --- | ---: | ---: | ---: | ---: | ---: |
| PFM | 45 | -1,12e-14 | 1,45e-13 | 2,70e-13 | 5,12e-13 |
| EMM | 45 | 1,69e-4 | 2,78e-4 | 7,25e-4 | 2,92e-3 |
| EPM | 90 | 1,88e-4 | 2,99e-4 | 9,90e-4 | 6,12e-3 |
| DM | 90 | 2,94e-4 | 3,33e-4 | 9,71e-4 | 6,11e-3 |

Les différences relatives symétriques maximales sont respectivement 0,0328,
0,0800, 0,0444 et 0,0222. Elles peuvent être amplifiées lorsque les valeurs de
référence sont proches de zéro ; les erreurs absolues doivent donc rester
visibles.

### Limite de portée

Le statut enregistré est `measured_not_yet_qualified`. Ces métriques montrent
le niveau d'accord observé, mais pas la réussite d'un test prédéfini. Pour
qualifier formellement cette validation dans l'article, il faut définir un
seuil justifié avant de convertir les résultats en verdict réussite/échec.

Preuves : `campaign/forward/summary.json`,
`campaign/forward/case_results.csv` et
`campaign/article_package/diagnostics/supplement_s1_forward_summary.json`.

## 2. Comparaison PyAges--TracerLPM

### Plan expérimental

- année d'observation : 2020 ;
- traceurs utilisés ensemble dans chaque inversion : CFC-11, CFC-12, CFC-113
  et SF6 ;
- modèles : EPM, avec le rapport `r`, et DM, avec le paramètre de dispersion
  `DP` ;
- 10 réalisations aléatoires par combinaison, graines 401 à 410 ;
- première phase, 320 cas à `tau=20 ans` :
  `r={0.05, 0.5, 2, 9}`, `DP={0.02, 0.2, 0.5, 1}` et erreurs relatives
  `{1 %, 5 %, 10 %, 20 %}` ;
- seconde phase, 160 cas nouveaux à `tau={5, 50} ans` :
  `r={0.05, 2}`, `DP={0.2, 1}` et erreurs relatives `{10 %, 20 %}` ;
- synthèse finale : 480 cas, soit 240 EPM et 240 DM, répartis en 48 groupes.

Le plan ne teste aucune suppression de traceur et aucune combinaison partielle
de traceurs. Une affirmation sur la robustesse au retrait d'un traceur ne serait
donc pas soutenue par cette campagne.

### Résultats et précautions

- PyAges : 480/480 optimisations terminées avec succès ;
- TracerLPM : 480/480 optimisations terminées avec succès ;
- solutions sur une borne : 128 pour PyAges et 77 pour TracerLPM ;
- médiane de la différence absolue d'âge entre outils : 0,513 an ;
- RMSE de la différence d'âge entre outils : 13,786 ans.

La différence entre médiane et RMSE montre l'influence de cas difficiles ou
extrêmes. Les contacts avec les bornes sont des diagnostics d'identifiabilité
ou d'optimisation, pas des échecs d'exécution. Les agrégats mélangent deux
modèles, plusieurs âges, plusieurs largeurs et quatre niveaux de bruit ; ils ne
justifient pas un classement global de PyAges et TracerLPM. Les résultats par
groupe du tableau détaillé doivent être utilisés pour toute comparaison
scientifique ciblée.

La reproduction exacte de la partie TracerLPM requiert Windows, Microsoft Excel
64 bits, le classeur et l'add-in USGS utilisés pendant la campagne. Le bundle
les conserve avec les empreintes suivantes :

- `TracerLPM_V_1_0_FourTracers_v17.xlsm`, 2 693 289 octets,
  SHA-256 `fb9022e683d6854b329aad07ea76749c17bef242ec2c703c7b7b5a293ec8e30f` ;
- `TracerLPMfunctions_64_v_1.xll`, 132 608 octets,
  SHA-256 `17c37328d606864754a2f115fec1ca56a70a06fc05bc5123deb1a462fc91f9a7`.

Preuves : `campaign/tracerlpm/manifest.json`,
`campaign/tracerlpm/benchmark/generated/robustness-study/results.csv`,
`campaign/article_package/tables/table3_pyages_tracerlpm_cases.csv` et
`campaign/article_package/reports/00_pyages_tracerlpm.md`.

## 3. Expérience synthétique shifted exponential

### Protocole

- 19 couples vrais `(mu, t0)` : cinq valeurs à `mu=1`, cinq à `mu=10`,
  quatre à `mu=20`, trois à `mu=30` et deux à `mu=40`, avec les décalages
  `t0` disponibles parmi 1, 10, 20, 30 et 40 ans ;
- traceurs : CFC-11, CFC-12, CFC-113 et SF6 ;
- date d'observation : 2010 ;
- erreur relative utilisée dans la vraisemblance : 8 % ;
- aucune perturbation aléatoire ajoutée aux concentrations synthétiques ;
- priors uniformes dans `mu in [0.1, 70] ans` et
  `t0 in [0, 70] ans` ;
- pilote de 4 000 pas, burn-in de 20 %, ridge relatif `1e-6`, proposition
  corrélée à l'échelle `2.38/sqrt(2)` ;
- cinq chaînes de 10 000 pas par cas, burn-in de 20 %, sans thinning pour les
  diagnostics ;
- âge médian de la distribution : `t50 = t0 + mu*ln(2)` ;
- temps de transit moyen : `MTT = mu + t0`.

### Résultats

Les 19 cas satisfont les critères de convergence. Le maximum de split-Rhat est
1,009782 et le minimum d'ESS est 755,79. Environ 39 995 états post-burn-in sont
poolés par cas après validation des chaînes.

L'absence de bruit ajouté explique que les meilleurs résidus de concentration
puissent être presque nuls. Elle ne signifie pas que `mu` et `t0` soient
toujours identifiables séparément. L'examen des postérieurs, notamment pour les
petites valeurs de `mu`, suggère une compensation entre les paramètres ; le
MTT peut être mieux contraint que sa décomposition en `mu` et `t0`. Cette
interprétation doit être confirmée et formulée par les auteurs à partir de la
Figure 2 et du Tableau 4.

Preuves : `campaign/shifted_exponential/manifest.json`,
`campaign/article_package/tables/table4.csv`,
`campaign/article_package/tables/shifted_exponential_posterior_summaries.csv`,
`campaign/article_package/diagnostics/shifted_exponential_convergence.csv` et
`campaign/article_package/figures/figure2_shifted_exponential.*`.

## 4. Reproduction Holten H4

### Protocole

- sept puits : 59-05, 67-19, 72-22, 73-29, 85-33, 85-34 et 85-35 ;
- observables : tritium, hélium-3 tritiogénique, krypton-85 et argon-39 ;
- quatre fractions : 0--20 ans, 20--40 ans, 40--60 ans et fraction ancienne ;
- convention : décalage de deux ans dans la zone non saturée et décroissance
  radioactive pendant ce transit ; âge représentatif de la fraction ancienne
  fixé à 310 ans ;
- demi-vie du tritium : 12,32 ans ;
- écart-type de l'hélium-3 : 0,5 TU pour les six valeurs publiées et 0,5 TU
  imputé pour 59-05 ;
- coordonnées latentes bornées dans `[-8, 8]`, prior uniforme dans ces bornes ;
- cinq chaînes ; 10 000 pas pour 59-05, 67-19 et 72-22 ; 20 000 pas pour les
  quatre autres puits ; burn-in 20 %, sans thinning diagnostique ;
- proposition corrélée à l'échelle `2.38/sqrt(3)`.

Les puits 73-29 et 85-34 présentaient des chaînes piégées dans des régimes de
fractions presque nulles. Une proposition MH symétrique documentée a ajouté un
rafraîchissement uniforme de `z1` ou `z2`, avec une probabilité par coordonnée
de 20 % pour 73-29 et de 10 % pour 85-34. Les chaînes initiales ont été
conservées ; les chaînes de secours ne les ont pas remplacées silencieusement.

### Résultats

Les sept puits convergent. Le maximum de split-Rhat est 1,009070 et le minimum
d'ESS est 313,10, obtenu pour 73-29.

Comparaison des 28 fractions aux valeurs publiées par Visser et al. (2013) :

| Mesure | Valeur |
| --- | ---: |
| MAE | 0,005455 |
| Erreur absolue médiane | 0,003815 |
| RMSE | 0,007046 |
| Erreur absolue maximale | 0,017993 |
| Fractions avec erreur absolue <= 0,02 | 28/28 |

La sensibilité au prior Dirichlet ne fait pas partie de cette campagne. Si elle
reste mentionnée dans l'article, son paquet de preuves doit être intégré ou
cité séparément avant dépôt.

Preuves : `campaign/holten_h4/manifest.json`,
`campaign/article_package/tables/holten_visser_vs_pyages.csv`,
`campaign/article_package/diagnostics/holten_h4_convergence.csv`,
`campaign/article_package/reports/02_holten_h4.md` et
`campaign/article_package/figures/figure3_holten_h4.*`.

## 5. Ploemeur avec le modèle shifted exponential

### Protocole

- deux puits, F09 et F11 ;
- deux fenêtres par puits : série complète et fenêtre 2014--2015 calibrée
  indépendamment ;
- traceurs : CFC-11, CFC-12 et CFC-113 ;
- erreur d'observation relative : `sigma_i = 0.20*Cobs_i` ;
- fonction objectif : `J = sum(((Cmod-Cobs)/sigma)^2)` et
  `logL = -0.5*J` ;
- priors uniformes `mu in [0.1, 70] ans` et `t0 in [0, 70] ans` ;
- pilote de 4 000 pas, cinq chaînes de 10 000 pas, burn-in 20 %, ridge
  relatif `1e-6`, proposition corrélée à `2.38/sqrt(2)`, sans thinning ;
- chaque prédiction postérieure emploie une ligne complète `(mu, t0)` ; aucune
  recombinaison de marges n'est effectuée ;
- `t50 = t0 + mu*ln(2)` ; le MTT est `mu+t0` et ne doit pas être confondu avec
  l'âge `t50` présenté dans l'article.

### Résultats

| Puits | Calibration | t50 médian | q10--q90 | mu médian | t0 médian | sqrt(J/m) optimal | max Rhat | min ESS |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| F09 | série complète | 4,182 | 1,535--8,084 | 2,481 | 1,709 | 0,802 | 1,0038 | 1 741 |
| F09 | 2014--2015 indépendante | 13,293 | 6,210--20,276 | 3,621 | 10,139 | 0,344 | 1,0020 | 4 298 |
| F11 | série complète | 85,384 | 84,696--85,987 | 69,582 | 37,245 | 4,256 | 1,0040 | 2 632 |
| F11 | 2014--2015 indépendante | 57,404 | 52,565--61,453 | 62,983 | 14,727 | 1,730 | 1,0032 | 3 348 |

Les quatre postérieurs convergent. Pour F09, la série complète contraint une
solution nettement plus jeune que la fenêtre indépendante. Pour F11, la
convergence MCMC ne doit pas être confondue avec la qualité de l'ajustement :
les RMSE normalisées médianes de la série complète sont 4,073 pour CFC-11,
4,402 pour CFC-12 et 4,294 pour CFC-113. Aucun traceur et aucun résidu n'ont été
retirés pour améliorer artificiellement le résultat.

Nombre d'observations de la série complète : F09, 19 CFC-11 et 21 pour chacun
des deux autres CFC ; F11, 23 pour chacun des trois CFC. Dans la fenêtre
indépendante, F09 utilise respectivement 2, 3 et 3 observations, et F11 en
utilise 2 par traceur.

Preuves : `campaign/ploemeur_shifted_exponential/manifest.json`,
`campaign/article_package/tables/ploemeur_shifted_exponential_summary.csv`,
`campaign/article_package/diagnostics/ploemeur_tracer_fit.csv`,
`campaign/article_package/diagnostics/ploemeur_pairing_effect.csv`,
`campaign/article_package/reports/03_ploemeur_shifted_exponential.md` et
`campaign/article_package/figures/figure4_ploemeur_shifted_exponential.*`.

## 6. Ploemeur avec l'inverse Gaussian physique

### Protocole

- deux puits, F09 et F11 ;
- trois postérieurs par puits : série complète, période 2012--2024 conditionnée
  par la série complète, puis fenêtre 2014--2015 conditionnée ;
- prior d'article converti selon `a=S^2/M^2` et `s=M^3/S^2`, avec densité
  transformée proportionnelle à `2/S` ;
- même vraisemblance relative à 20 % que dans l'analyse shifted exponential ;
- grille déterministe d'états initiaux classés par objectif ;
- pilote de 1 200 pas, warm-up de 2 000 pas et production initiale de
  12 000 pas ;
- cinq chaînes, graines 12345, 24680, 54321, 97531 et 86420 ;
- extensions automatiques de 12 000 pas, six au maximum, jusqu'à 82 000 états
  retenus par chaîne ;
- aucun résultat historique utilisé.

### Résultats

| Puits | Workflow | t50 médian | q10--q90 | max Rhat | min ESS bulk | min ESS tail | États retenus/chaîne |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| F09 | série complète | 5,824 | 2,023--9,998 | 1,00987 | 863 | 365 | 82 000 |
| F09 | 2012--2024 conditionné | 5,081 | 1,660--8,872 | 1,00450 | 1 990 | 1 471 | 10 000 |
| F09 | 2014--2015 conditionné | 5,796 | 2,156--9,273 | 1,00559 | 1 395 | 978 | 10 000 |
| F11 | série complète | 97,446 | 96,289--98,290 | 1,00974 | 1 193 | 1 443 | 10 000 |
| F11 | 2012--2024 conditionné | 99,125 | 98,349--99,752 | 1,00518 | 1 366 | 1 214 | 10 000 |
| F11 | 2014--2015 conditionné | 98,667 | 97,716--99,402 | 1,00586 | 1 720 | 2 037 | 10 000 |

Les six postérieurs convergent. F09 série complète a nécessité les extensions
jusqu'à 82 000 états retenus par chaîne pour satisfaire les critères stricts ;
ce fait doit être rapporté si la stratégie adaptative est décrite.

Sur six jeux de paramètres représentatifs, les implémentations comparées de la
distribution IG ont donné des différences maximales nulles pour PDF, CDF et
`t50`, et `3.02e-13 pptv` pour les concentrations CFC. Il s'agit d'un contrôle
d'équivalence numérique des implémentations, pas d'une validation indépendante
des hypothèses physiques.

Pour F11 dans la fenêtre 2014--2015, l'âge médian IG est 98,667 ans, contre
57,404 ans avec le shifted exponential indépendant. Cette dépendance forte au
choix du LPM est un résultat à interpréter scientifiquement ; elle ne doit pas
être présentée comme une simple différence numérique sans discussion du modèle
et du conditionnement.

Preuves : `campaign/ploemeur_physical_ig/manifest.json`,
`campaign/article_package/tables/ploemeur_ig_stabilized.csv`, les six fichiers
`campaign/article_package/diagnostics/ig_*_convergence.csv`,
`campaign/article_package/diagnostics/ploemeur_ig_distribution_equivalence.csv`
et `campaign/article_package/reports/04_ploemeur_ig_stabilized.md`.

## Affirmations soutenues et affirmations à éviter

| Soutenu par la campagne | À ne pas affirmer sans analyse supplémentaire |
| --- | --- |
| Les huit étapes techniques de la campagne ont réussi. | La campagne restitue octet par octet les anciennes sorties historiques. |
| Les 19 + 7 + 4 + 6 groupes/postérieurs MCMC présentés passent les seuils annoncés. | Convergence MCMC implique bon ajustement aux observations. |
| Les 480 cas PyAges et les 480 calculs TracerLPM se terminent avec succès. | Un des deux outils est globalement supérieur à l'autre. |
| Les fractions Holten H4 sont proches des valeurs de Visser selon les métriques données. | La sensibilité Holten au prior Dirichlet a été reproduite dans cette campagne. |
| La série complète F09 contraint un t50 shifted exponential plus jeune que la fenêtre indépendante. | Les fenêtres sont directement comparables sans tenir compte du conditionnement et du nombre d'observations. |
| Le modèle shifted exponential ajuste mal la série complète F11 malgré la convergence des chaînes. | Tous les résultats Ploemeur constituent de bons ajustements. |
| Le choix IG/shifted change fortement le t50 de F11. | Cette différence suffit à valider physiquement l'un des deux modèles. |
| Les erreurs forward ont été quantifiées sur 270 cas. | La vérification forward a « passé » un test formel déjà défini. |

## Disponibilité du code et des données : état et contenu futur

La [politique code et données de GMD](https://www.geoscientific-model-development.net/policies/code_and_data_policy.html)
demande, dès la soumission du preprint, une archive publique pérenne de la
version exacte du code et des données, avec configurations, entrées, scripts de
prétraitement, contrôle des exécutions et post-traitement. GitHub peut rester le
dépôt de développement, mais ne remplace pas une archive figée avec identifiant
persistant.

Le bundle candidat existe localement mais n'est pas inscrit :

- dossier : `C:\pyages-runs\pyages-0.1.0b1-article-v1-reproduction` ;
- ZIP : `C:\pyages-runs\pyages-0.1.0b1-article-v1-reproduction.zip` ;
- taille : 176 877 762 octets, soit 168,7 MiB ;
- SHA-256 :
  `eba91da852d7bfa4ca3a7f9822ca48f041c0e451fe3406613df885d0b7c6416b` ;
- 2 951 fichiers dans le manifeste scientifique central ;
- 2 963 fichiers inventoriés dans `ZENODO_MANIFEST.json`, 2 964 fichiers
  protégés par `ZENODO_CHECKSUMS.sha256` et 2 965 entrées dans le ZIP ;
- script autonome `verify_bundle.py` pour vérifier l'intégrité après extraction.

Le bundle comprend le snapshot source, les entrées, les sorties complètes, les
chaînes MCMC retenues, les figures, les tables, les rapports, les diagnostics,
les configurations, les commandes, les logs, les versions d'exécution et les
dépendances TracerLPM exactes. Le paquet éditorial de 72 artefacts exclut les
chaînes brutes pour rester lisible ; celles-ci restent présentes dans la
campagne complète de l'archive.

Avant réservation du DOI, il reste à :

1. arrêter le titre exact de l'article et celui du dépôt ; le mot « complete »
   est trop large tant que le cas Dirichlet et la qualification forward restent
   hors périmètre ;
2. décider si ces deux éléments doivent être ajoutés, retirés du manuscrit ou
   explicitement qualifiés comme travaux séparés ;
3. résoudre ou expliquer la différence de version `0.1.0b1`/`0.1.0` dans le
   freeze d'environnement ;
4. compléter et faire valider la liste des auteurs, leur ordre, ORCID et
   affiliations ; le brouillon actuel ne contient que Jean-Raynald de Dreuzy ;
5. valider les licences et attributions fichier par fichier, notamment pour les
   données NOAA, AGAGE, IAEA, Ploemeur et Holten ;
6. vérifier une dernière fois que tous les nombres, figures et tables cités par
   le manuscrit correspondent exactement à ceux du bundle ;
7. seulement alors réserver le DOI Zenodo, reconstruire les métadonnées avec ce
   DOI, revalider le ZIP et rendre le dépôt public au plus tard lors de la
   soumission du preprint.

La future section « Code and data availability » devra contenir, dans les mots
des auteurs : le nom et la version exacte de PyAges, la licence CeCILL 2.1, le
DOI de l'archive figée, le lien vers le dépôt de développement, le fait que
l'archive contient code, entrées, configurations, scripts, sorties, diagnostics
et figures, ainsi que les conditions particulières de TracerLPM et des données
tierces. Le DOI de l'article ou du preprint devra être relié au dépôt Zenodo
lorsqu'il sera disponible.

## Carte de lecture des preuves

Dans le futur ZIP extrait :

| Besoin | Emplacement recommandé |
| --- | --- |
| Vue d'ensemble pour le lecteur | `README.md`, puis `campaign/article_package/README.md` |
| Figures finales | `campaign/article_package/figures/` |
| Tables numériques | `campaign/article_package/tables/` |
| Résumés scientifiques | `campaign/article_package/reports/` |
| Diagnostics de convergence et d'ajustement | `campaign/article_package/diagnostics/` |
| Valeurs représentées dans les figures | `campaign/article_package/supporting_data/` |
| Manifeste global et commandes | `campaign/campaign_manifest.json` |
| Sources exactes d'exécution | `campaign/article_package/provenance/execution_source/` |
| Snapshot source final | `source/pyages-source.zip` |
| Environnement complet | `source/environment-pip-freeze.txt` |
| Classeur et add-in TracerLPM | `external/tracerlpm/` |
| Licences et droits sur les données | `LICENSE` et `NOTICE-DATA.md` |
| Contrôle autonome d'intégrité | `verify_bundle.py` |

## Sources scientifiques et réglementaires à citer ou vérifier

- Visser, A., Broers, H. P., Purtschert, R., Sültenfuß, J. et de Jonge, M.
  (2013), *Water Resources Research*, 49, 7778--7796,
  <https://doi.org/10.1002/2013WR014012>.
- Jurgens, B. C., Böhlke, J. K. et Eberts, S. M. (2012), *TracerLPM*, USGS
  Techniques and Methods 4-F3, <https://doi.org/10.3133/tm4F3>.
- USGS TracerLPM : <https://www.usgs.gov/software/tracerlpm>.
- Observatoire Ploemeur-Guidel, SNO H+ / OZCAR :
  <https://hplus.ore.fr/en/ploemeur/>.
- Le Borgne et al. (2004), *Water Resources Research*,
  <https://doi.org/10.1029/2003WR002436>.
- GMD, politique code et données :
  <https://www.geoscientific-model-development.net/policies/code_and_data_policy.html>.
- GMD, politique IA :
  <https://www.geoscientific-model-development.net/policies/ai_policy.html>.

Les DOI précis des jeux de données atmosphériques et leurs attributions sont
inventoriés dans `NOTICE-DATA.md`. Ils doivent être vérifiés au moment de
finaliser la bibliographie et les droits de redistribution.

## Verdict au 27 août 2026

Le matériau principal est recalculé, traçable et suffisamment documenté pour
alimenter la révision scientifique du manuscrit. Il n'est pas encore prêt à
être inscrit définitivement comme archive « complète » : la portée du volet
forward, le statut du cas Dirichlet, l'identité de version et les métadonnées
d'auteurs doivent d'abord être arrêtés. La bonne séquence est donc celle décidée
par les auteurs : finaliser ces validations, figer le manuscrit et son périmètre,
puis seulement réserver le DOI et reconstruire une dernière fois l'archive.
