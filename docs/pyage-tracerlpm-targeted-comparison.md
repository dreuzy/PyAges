# Protocole et état — qualification ciblée de PyAge par TracerLPM

> Version consolidée le 19 août 2026 — protocole exécuté sur données
> synthétiques ; qualification sur données naturelles encore distincte.

La campagne synthétique est terminée. Le rapport généré le 18 août 2026 repose
sur 270 comparaisons *forward*, des inversions sans bruit, une étude SF6 et
**480 cas appariés** EPM/DM exécutés par PyAge et TracerLPM. Les sorties brutes
et le rapport détaillé sont reproductibles sous
`validation/tracerlpm/benchmark/generated/` mais restent ignorés par Git ; ce
document conserve le protocole, les conclusions versionnables et leurs limites.

## 1. Objectif et limite

Vérifier sur des cas reproductibles que PyAge et TracerLPM sont compatibles
lorsqu’ils utilisent la même distribution d’âge, la même fonction d’entrée,
les mêmes dates, unités et conventions radioactives, et des paramètres rendus
mathématiquement équivalents. La campagne ne cherche ni à reproduire toute
l’interface TracerLPM, ni à valider tous ses modèles.

La preuve comporte deux niveaux obligatoires et successifs :

1. **calcul direct (forward)** : paramètres connus vers concentrations ;
2. **inversion** : concentrations synthétiques vers paramètres identifiés.

La validation forward doit réussir avant toute interprétation des inversions.

## 2. État de départ validé

- TracerLPM fonctionne avec Excel Microsoft 365 64 bits sur la machine cible.
- Solver et le XLL TracerLPM 64 bits sont chargés.
- Le runner .NET 8 x64 pilote une copie du classeur et exporte les séries.
- Les cas USGS Example 1 PFM/EMM, EPM/PEM et DM/mélange ont été exécutés.
- Entrées YAML et sorties JSON, CSV et Markdown sont opérationnelles.
- PyAge interprète désormais `mu` comme moyenne et `sigma` comme écart type de
  la loi inverse gaussienne.
- Les frontières des modèles Dirac doubles et les conventions de décroissance
  radioactive ont été corrigées.
- Les contrôles automatisés du benchmark sont intégrés au jalon de publication.

Les hashes existants démontrent la répétabilité technique. La concordance
scientifique est qualifiée dans le périmètre synthétique décrit ci-dessous,
sans généralisation aux données naturelles.

## 3. Périmètre scientifique initial

| PyAge | TracerLPM | Fonction testée |
|---|---|---|
| `dirac` | PFM | dates et évaluation directe |
| `exp` | EMM | quadrature et longue traîne |
| `exp_shifted` | EPM | décalage et mapping de paramètres |
| `ig` | DM | dispersion et convention à deux paramètres |

PEM, mélanges binaires, `mix_exp_shifted`, `ig_shifted`, Solver et
géoproduction restent hors du premier lot.

## 4. Correspondances mathématiques à figer

### PFM ↔ Dirac

```text
PyAge mu = TracerLPM mean_age = tau
```

### EMM ↔ exponentielle

```text
g(a) = exp(-a/tau) / tau
PyAge mu = TracerLPM mean_age = tau
```

### EPM ↔ exponentielle décalée

Avec `tau` l’âge moyen total, TracerLPM saisit le ratio physique
`r = x*/x` (longueur piston / longueur exponentielle). Le paramètre mathématique
de PyAge est `eta = (x+x*)/x`, d’où la conversion indispensable :

```text
eta = 1 + r
r   = eta - 1
```

La distribution exponentielle décalée s’écrit alors :

```text
PyAge mu    = tau / eta
PyAge shift = tau * (1 - 1/eta)

tau = shift + mu
eta = 1 + shift/mu
```

Le temps de zone non saturée reste nul dans le premier lot pour éviter un
second décalage.

### DM ↔ inverse gaussienne

La formulation TracerLPM implique :

```text
moyenne   = tau
variance  = 2 * DP * tau^2
écart type = tau * sqrt(2 * DP)
```

Le mapping corrigé est donc :

```text
PyAge mu    = tau
PyAge sigma = tau * sqrt(2 * DP)

tau = mu
DP  = sigma^2 / (2 * mu^2)
```

Il remplace l’ancienne correspondance avec les paramètres internes de SciPy.

Il n’existe plus d’anomalie mathématique connue dans le DM de PyAge. Les points
à qualifier sont la convention exacte de `DP` dans le classeur, la troncature
de la traîne, la résolution temporelle et l’identifiabilité conjointe de `tau`
et `DP`. Une valeur optimale isolée ne suffira pas : la surface de la fonction
objectif et la sensibilité à l’initialisation seront également rapportées.

## 5. Données communes

### Lot synthétique obligatoire

Les deux outils recevront les mêmes séries mensuelles :

1. constante — normalisation et conservation de la masse ;
2. rampe — dates et premier moment ;
3. échelon — réponse cumulée et CDF ;
4. impulsion rectangulaire — résolution temporelle ;
5. série multi-pics — comportement proche d’une chronique atmosphérique.

Chaque fichier portera `date`, `concentration`, unité, convention mensuelle,
politiques hors chronique et SHA-256.

### Lot multi-traceurs environnementaux

Les CFC sont des traceurs environnementaux anthropiques, et non des traceurs
naturels au sens strict. Un jeu commun comprendra **CFC-11, CFC-12 et CFC-113**,
puis éventuellement **SF6**. Ces chroniques multiples sont nécessaires pour
contraindre les deux paramètres de EPM et DM à une date d’échantillonnage.

Les mêmes fonctions d’entrée, déjà converties en concentrations de recharge,
seront injectées dans les deux outils. Les chroniques internes de TracerLPM ne
serviront pas de référence implicite. Source, version, zone atmosphérique,
unités, température, pression/altitude, excès d’air, salinité, interpolation et
politique hors domaine seront enregistrés ou explicitement neutralisés.

Ce jeu sera d’abord utilisé en forward. Il alimentera ensuite les inversions
synthétiques et, dans un dernier temps, un cas environnemental observé.

## 6. Matrice minimale

| Famille | Paramètres |
|---|---|
| PFM | `tau = 1, 20, 80 ans` |
| EMM | `tau = 1, 20, 80 ans` |
| EPM | `tau = 10, 40 ans`; `eta = 1.5, 3, 10` |
| DM | `tau = 10, 40 ans`; `DP = 0.02, 0.2, 1` |

Cela représente 18 paramétrisations (`3 + 3 + 6 + 6`). Les dates candidates sont 1995.0, 2010.0
et 2020.0 ; les combinaisons redondantes seront éliminées et le nombre exact de
simulations sera affiché avant lancement.

Pour EPM, les valeurs saisies dans TracerLPM sont respectivement
`r = 0.5, 2, 9`, tandis que PyAge reçoit `eta = 1.5, 3, 10`.

## 7. Architecture proposée

Le runner reste un adaptateur Excel autonome ; le cœur PyAge ne connaîtra ni
feuilles ni cellules du classeur.

```text
validation/tracerlpm/
  config/                    configuration Excel et mapping existants
  samples/                   cas techniques existants
  benchmark/
    configs/                 campagne et tolérances en YAML commenté
    inputs/                  séries communes et manifestes
    mappings/                transformations PFM/EMM/EPM/DM
    references/              résultats analytiques indépendants
    tracerlpm_exports_raw/    exports Excel bruts et immuables
    generated/               tables, figures et rapports
    scripts/                 génération, exécution et comparaison
    tests/                   invariants, mappings et schémas d’échange
  src/TracerLpmRunner/        automatisation COM existante
```

Tous les nouveaux fichiers propres à cette étude seront créés sous
`validation/tracerlpm/benchmark/`. Aucun script de comparaison, résultat ou
configuration TracerLPM ne sera dispersé dans `pyage/`, `tests/` ou les exemples
généraux. Seule une correction scientifique générique, démontrée indépendamment
du benchmark, pourra modifier le cœur PyAge et devra alors posséder ses propres
tests. Les copies Excel, sorties volumineuses et fichiers temporaires resteront
ignorés par Git ; les YAML, petits jeux d’entrée, manifestes et rapports retenus
seront versionnables.

## 8. Phases et points d’arrêt

### Phase 0 — figer le protocole

- valider ce document, les mappings, la matrice et les entrées ;
- valider le jeu multi-traceurs destiné aux inversions synthétiques et confirmer
  que le cas environnemental observé reste réservé à la Phase 6.

**Jalon :** protocole approuvé. Aucun calcul comparatif n’est lancé avant cela.

### Phase 1 — construire le benchmark hors Excel

- créer l’arborescence `benchmark/` ;
- définir les YAML commentés de campagne, cas et tolérances ;
- générer déterministement les cinq entrées synthétiques ;
- implémenter et tester les mappings réversibles ;
- calculer PDF, CDF, moments, quantiles et convolutions avec une référence lente
  indépendante ;
- générer des observations synthétiques à partir de paramètres vrais connus ;
- prévoir trois régimes : sans bruit, bruit déterministe faible et réalisations
  bruitées avec graines enregistrées ;
- produire un manifeste de versions, hashes et paramètres effectifs.

**Jalon :** campagne préparée et références vérifiées, puis revue avant Excel.

### Phase 2 — étendre le runner

- importer les fonctions d’entrée communes ;
- transmettre paramètres et dates d’observation ;
- exporter les valeurs utiles, et pas seulement les séries graphiques ;
- écrire un rapport d’erreur structuré sans perdre le reste du lot ;
- conserver classeurs de travail et exports bruts ;
- consigner Excel, paramètres régionaux et hashes du classeur/XLL.

**Jalon :** un cas pilote PFM + entrée constante de bout en bout, puis revue.

### Phase 3 — validation forward progressive

1. PFM : constante puis rampe ;
2. EMM : constante, échelon et multi-pics ;
3. EPM : après contrôle du décalage ;
4. DM : après contrôle des moments et de `DP` ;
5. matrice synthétique complète.

Un rapport est produit après chaque famille. Un écart systématique de convention
arrête la généralisation jusqu’à attribution.

**État au 17 août 2026 :** PFM, EMM, EPM et DM ont été exécutés de bout en bout
sur les chroniques synthétiques. Les conventions EPM (`eta=1+r`) et DM
(`sigma=tau*sqrt(2*DP)`) sont maintenant explicites et vérifiées. Les écarts
résiduels de TracerLPM sont rapportés par rapport à sa date effective sur grille
semestrielle. Les écarts PyAge concentrés aux très faibles âges restent consignés
comme effets de résolution ; conformément au périmètre décidé, ils ne déclenchent
pas de modification supplémentaire de PyAge à ce stade.

### Phase 4 — inversion synthétique et identifiabilité

- inverser d’abord les observations sans bruit issues de paramètres vrais ;
- comparer paramètres vrais, estimations PyAge et estimations TracerLPM ;
- comparer aussi concentrations recalculées et valeurs des fonctions objectif ;
- répéter depuis plusieurs initialisations communes ;
- ajouter ensuite le bruit faible, puis les réalisations à graines fixes ;
- pour EPM et DM, utiliser plusieurs CFC et analyser profils ou surfaces de la
  fonction objectif afin de détecter corrélation, équifinalité et minima locaux ;
- consigner convergence, bornes actives et statut de chaque optimiseur.

**Premier jalon symétrique exécuté le 17 août 2026 :** le pilote EMM sans bruit
à `tau=20 ans`, avec CFC-11, CFC-12 et CFC-113 dans les deux outils, retrouve
`19.9982589 ans` avec PyAge et `19.9338202 ans` avec TracerLPM. Les erreurs de
`0.00174113` et `0.0661798 an` satisfont le seuil de `0.5 an`. Le canal 3H
utilisé comme alias CFC-12 est explicitement neutralisé en décroissance. La
formule d’objectif Excel et les trois traceurs effectifs sont vérifiés.

**Jalon à deux paramètres exécuté le 17 août 2026 :** avec les mêmes trois CFC,
EPM retrouve `(tau, r)=(20.0000005, 2.0000001)` dans PyAge et
`(19.7464101, 1.9624315)` dans TracerLPM, pour une vérité `(20, 2)`. DM retrouve
`(tau, DP)=(19.9995879, 0.2000672)` dans PyAge et
`(19.7303094, 0.2057685)` dans TracerLPM, pour une vérité `(20, 0.2)`. Les quatre
estimations TracerLPM satisfont les seuils relatifs fixés à 5 % pour `tau` et
10 % pour le second paramètre. Les surfaces indépendantes 32 × 32 retrouvent
exactement le couple vrai comme minimum de grille dans les deux modèles.

Une seule concentration à une date n’est pas considérée suffisante pour
identifier deux paramètres. Un cas ne sera déclaré concluant que si les données
synthétiques rendent les paramètres identifiables dans la plage étudiée.

**Jalon :** récupération des paramètres sans bruit, puis revue avant les cas
bruités.

**Campagne bruitée commencée le 18 août 2026 :** cinq réalisations à 1 % de
bruit relatif, graines 101 à 105, ont été générées pour EPM et DM. Les dix
inversions PyAge convergent et leurs biais/RMSE sont consignés dans
`validation/tracerlpm/benchmark/generated/inversion-noisy-campaign/`. Les dix
inversions TracerLPM correspondantes ont ensuite été exécutées. L'attente
initialement attribuée à Solver provenait en réalité de la fermeture d'Excel ;
le nettoyage cible maintenant le seul PID possédé par le runner. Les RMSE des
paramètres vrais sont du même ordre dans les deux outils : respectivement
`tau/r = 1.976/0.421` pour PyAge et `1.836/0.445` pour TracerLPM en EPM, puis
`tau/DP = 2.281/0.0545` et `2.238/0.0528` en DM. Cinq réalisations restent
insuffisantes pour conclure sur les distributions d'incertitude.

**Extension Monte-Carlo du 18 août 2026 :** 30 réalisations PyAge par modèle à
1 % confirment la dispersion des deux paramètres. Les moyennes ± écarts types
sont `tau=20.401±1.493`, `r=2.158±0.340` en EPM et `tau=20.509±1.990`,
`DP=0.1885±0.0589` en DM. Trois solutions DM initialement très éloignées ont été
attribuées à une dégradation de l'objectif par Powell, et non à de meilleurs
minima : l'objectif aux paramètres vrais était nettement inférieur. Le pilote
utilise donc L-BFGS-B pour DM et conserve toujours l'initialisation lorsqu'un
optimiseur l'aggrave. Les 60 cas corrigés convergent.

**Décision SF6 du 18 août 2026 :** une campagne appariée de 30 réalisations avec
les trois CFC plus SF6 démontre un gain substantiel avant augmentation du bruit.
La RMSE de `tau` diminue de 85,1 % en EPM et 87,4 % en DM ; la RMSE du second
paramètre diminue de 36,6 % pour `r` et 76,1 % pour `DP`. La corrélation
`tau–DP`, égale à `-0.959` avec les seuls CFC, tombe à `0.248` avec SF6. Le SF6
est donc retenu pour la suite. Son ajout dans TracerLPM requiert une copie de
classeur à quatre canaux natifs et une qualification séparée du mapping ; aucun
canal hélium à traitement spécial ne sera utilisé comme alias.

### Phase 5 — convergence et tolérances

- mesurer séparément discrétisation temporelle et quadrature PyAge ;
- mesurer la répétabilité Excel/TracerLPM ;
- fixer ensuite les tolérances absolue et relative ;
- classer `pass`, `investigate` ou `not_comparable`.

Les tolérances sont justifiées par les calculs, pas ajustées pour faire passer
les résultats.

**État au 18 août 2026 : terminé pour le périmètre synthétique.** PyAge converge
vers la quadrature indépendante lorsque la résolution augmente. Les inversions
sans bruit récupèrent les paramètres EMM, EPM et DM ; les erreurs relatives
PyAge sont inférieures à 0,04 % pour EPM et DM. Les deux outils terminent les
480 inversions de robustesse. À 10–20 % de bruit, les paramètres de largeur
deviennent fréquemment non identifiables et atteignent les bornes.

### Phase 6 — cas environnemental et rapport final

- figer les chroniques CFC-11/CFC-12/CFC-113 et leurs métadonnées ;
- ajouter SF6 seulement si ses hypothèses de recharge sont maîtrisées ;
- exécuter la sous-matrice pertinente ;
- séparer incertitude analytique et tolérance numérique ;
- produire tableaux, figures, écarts attribués et limites de validation.

**État : hors de la qualification synthétique publiée ici.** Aucun résultat de
cette campagne ne doit être présenté comme une validation générale sur données
naturelles. Les fonctions objectif diffèrent actuellement (L2 pondérée dans
PyAge, somme L1 relative dans TracerLPM), les trois CFC sont corrélés, seulement
dix graines sont disponibles par cellule de robustesse et certaines
distributions anciennes ne sont couvertes qu’à 80–94 % par la fenêtre
temporelle.

## 9. Métriques et réussite

Chaque cas rapportera différence signée, absolue et relative symétrique, masse
couverte, écart à la quadrature indépendante, statut et justification. Par
famille : biais, MAE, RMSE, maximum absolu et nombres de statuts.

Pour les inversions seront ajoutés : erreur sur chaque paramètre vrai, écart
PyAge–TracerLPM, fonction objectif, convergence, initialisation, bornes actives,
dispersion entre répétitions et diagnostic d’identifiabilité.

Le benchmark minimal réussit si :

- les mappings sont testés et réversibles ;
- PFM et EMM concordent selon l’étude de convergence ;
- EPM et DM concordent, ou leurs écarts sont reproduits et attribués ;
- les inversions sans bruit récupèrent les paramètres vrais lorsqu’ils sont
  identifiables ;
- les inversions bruitées présentent un biais et une dispersion quantifiés ;
- entrées, unités et dates sont strictement communes ;
- tous les résultats, y compris les échecs, sont reproductibles.

## 10. Garde-fous

- Excel séquentiel, copie de travail par cas, PID détenu et timeout explicite.
- Aucun changement automatisé de la sécurité globale Office.
- Échanges numériques en culture invariante ; paramètres régionaux consignés.
- Tests analytiques et aller-retour des mappings avant Excel.
- Un fichier source hashé unique alimente les deux outils.
- Résultats bruts conservés avant toute normalisation ou tolérance.

## 11. Décisions enregistrées pour la campagne

La campagne exécutée a retenu :

1. le périmètre PFM, EMM, EPM et DM ;
2. les cinq entrées synthétiques ;
3. la matrice de 18 paramétrisations ;
4. le mapping DM `sigma = tau * sqrt(2*DP)` ;
5. un temps de zone non saturée nul au premier lot ;
6. la Phase 1 hors Excel, suivie d’une revue ;
7. une validation des inversions après la validation forward ;
8. le jeu CFC-11/CFC-12/CFC-113 pour contraindre EPM et DM ;
9. SF6 seulement après qualification séparée de ses hypothèses de recharge ;
10. le confinement du chantier dans `validation/tracerlpm/benchmark/`.

Le passage à un cas naturel constitue une campagne séparée, avec ses propres
hypothèses de recharge, incertitudes analytiques et critères d’acceptation.

## 12. Références

- [Migration scientifique PyAge](scientific-migration-ig-decay.md)
- Runner TracerLPM : `validation/tracerlpm/README.md`
- Jurgens, B. C., Böhlke, J. K. et Eberts, S. M. (2012), *TracerLPM
  (Version 1)*, USGS Techniques and Methods 4-F3,
  <https://doi.org/10.3133/tm4F3>.
