# Audit scientifique et plan d’amélioration de PyAges

> **Statut : diagnostic archivé.** Les options de compatibilité envisagées ici
> n’ont pas été conservées. L’implémentation et les choix scientifiques actuels
> sont décrits dans `docs/convolution-method-evolution-report.md`. Ce document
> est conservé uniquement pour expliquer l’origine des corrections et ne doit
> pas servir de description de l’état actuel de PyAges.

## 1. Objectif

Ce document sépare l’amélioration intrinsèque de PyAges de toute comparaison
avec TracerLPM. Le but est de vérifier que les objets scientifiques ont des
contrats clairs, que les paramètres portent le sens annoncé, que les données
d’entrée sont validées et que les tests vérifient des propriétés indépendantes
des valeurs de non-régression.

Les changements proposés doivent respecter trois principes :

1. ne pas modifier silencieusement les résultats historiques ;
2. corriger d’abord les défauts démontrables et documenter les migrations ;
3. préférer de petits contrats explicites à une nouvelle couche d’abstraction.

## 2. Diagnostic général

L’architecture actuelle est saine dans son principe : traceurs, LPM,
convolution et calibration sont séparés, les LPM sont enregistrés dans un
registre, et les paramètres de calibration sont externalisés en YAML.

La faiblesse principale n’est pas l’organisation générale, mais l’absence d’une
couche de vérification scientifique indépendante. Les golden tests enregistrent
fidèlement le comportement actuel, y compris une éventuelle erreur. Plusieurs
tests de convolution indiquent d’ailleurs explicitement qu’ils ne vérifient pas
la justesse scientifique.

Il faut ajouter des tests fondés sur :

- des identités analytiques ;
- la normalisation et les moments des distributions ;
- des convolutions dont la solution est connue ;
- des transformations de paramètres réversibles ;
- la conservation des unités et des métadonnées ;
- des études de convergence numérique.

## 3. Anomalies confirmées

### 3.1 Inverse Gaussian : paramètres mal nommés

Le modèle `ig` appelle actuellement :

```text
scipy.stats.invgauss(mu, loc=0, scale=sigma)
```

Dans cette paramétrisation SciPy :

$$
E[T] = \mu\sigma,
\qquad
\operatorname{Var}(T)=\mu^3\sigma^2.
$$

Les fichiers YAML décrivent pourtant `mu` comme l’âge moyen et `sigma` comme
l’écart-type. Cette description est fausse pour l’implémentation actuelle.

#### Options possibles

**Option A — correction minimale, recommandée à court terme**

- conserver les valeurs numériques et le comportement historique ;
- renommer conceptuellement les paramètres en `shape` et `scale` dans la
  documentation et les labels ;
- exposer des propriétés dérivées `mean_age` et `std_age` ;
- ajouter des fonctions explicites de conversion depuis/vers les paramètres
  hydrologiques usuels.

Avantage : aucun résultat historique ne change. Inconvénient : les anciens noms
Python `mu` et `sigma` restent ambigus tant qu’une migration d’API n’est pas
faite.

**Option B — API scientifique corrigée**

- redéfinir le constructeur public avec `mean_age` et `std_age`, ou
  `mean_age` et `dispersion_parameter` ;
- convertir en interne vers SciPy ;
- conserver un mode `legacy_scipy_parameters` pour relire les anciens YAML et
  résultats.

Cette option est préférable à long terme, mais constitue un changement de
résultats si elle est appliquée sans versionnement. Elle nécessite un plan de
migration et une version majeure ou un avertissement de dépréciation.

#### Vérifications à ajouter

- égalité entre moments analytiques et `mean()`/`std()` ;
- réversibilité des conversions ;
- normalisation pour plusieurs ordres de grandeur ;
- comparaison PDF/CDF avec une implémentation indépendante de la formule ;
- tests des cas étroits, où la quadrature actuelle est la plus fragile.

### 3.2 `dirac_double` : quantile incorrect

Les masses sont situées en :

$$
t_1=\mu_1,
\qquad
t_2=\mu_1+\mu_2,
$$

avec les poids `rate` et `1-rate`. La méthode `cdf_inv()` retourne actuellement
`mu2` pour la seconde masse, alors qu’elle doit retourner `mu1 + mu2`.

À la frontière `p == rate`, le quantile généralisé
\(\inf\{t:F(t)\geq p\}\) doit retourner la première masse. Les comparaisons
`<`/`>` utilisées dans les CDF de Dirac méritent d’être harmonisées avec cette
définition.

#### Modification proposée

- corriger uniquement `cdf_inv()` et les inégalités de frontière ;
- ne pas changer la convolution directe, qui utilise déjà les deux bons temps ;
- ajouter des tests exacts pour `p = 0`, `rate`, `1-epsilon` et pour les deux
  sauts de CDF.

Impact forward attendu : aucun, car la convolution n’appelle pas ce quantile.
Impact possible : tableaux de moments, affichages et post-traitements.

### 3.3 `mix_exp_shifted` : contrat statistique incomplet

La distribution effectivement convoluée est :

- une masse de poids \(r\) en \(\mu_1\) ;
- une exponentielle de poids \(1-r\), de support
  \(L=\mu_1+s\) et d’échelle \(\mu_2\).

Sa moyenne correcte est :

$$
E[T]=\mu_1+(1-r)(s+\mu_2).
$$

Le quantile généralisé vaut :

$$
Q(p)=
\begin{cases}
\mu_1, & p\leq r,\\
L-\mu_2\ln\left(\dfrac{1-p}{1-r}\right), & p>r.
\end{cases}
$$

La moyenne, l’écart-type et le quantile actuels ne respectent pas ces formules.
Le PDF continu ne contient logiquement pas la masse de Dirac, tandis que la CDF
et la convolution la contiennent : le contrat `pdf()` n’est donc pas celui
d’une densité ordinaire complète.

#### Modification proposée

- corriger moyenne, variance, CDF et quantile à partir d’une spécification
  mathématique unique ;
- documenter que la distribution comporte une mesure discrète et une partie
  continue ;
- éviter de présenter `pdf()` seul comme représentation complète ;
- ajouter, sans nouvelle hiérarchie complexe, une méthode descriptive telle que
  `point_masses()` retournant les masses discrètes ;
- corriger l’unité YAML de `rate`, actuellement déclarée en années dans le
  bloc de prior ;
- réintégrer le modèle aux tests génériques seulement après ces corrections.

Ce modèle doit rester hors des comparaisons externes tant que ces propriétés ne
sont pas validées.

### 3.4 Constantes de décroissance radioactives

Le code applique :

$$
C(t)=C_0\exp(-t/T_d).
$$

Le champ `decay_time` désigne donc un temps caractéristique
\(T_d=t_{1/2}/\ln 2\), conformément aux modèles de traceur synthétiques et à la
documentation utilisateur.

Plusieurs YAML contiennent cependant la demi-vie directement :

| Traceur | Valeur actuelle | Temps caractéristique attendu approximatif |
|---|---:|---:|
| ³H | 12.32 | 17.77 ans |
| ⁸⁵Kr | 10.76 | 15.52 ans |
| ³⁹Ar | 267 | 385.2 ans |
| ¹⁴C | 573, 5730 selon le fichier | 8267 ans pour une demi-vie de 5730 ans |

Les variantes ¹⁴C sont particulièrement incohérentes entre données, noms de
répertoires et commentaires.

#### Modification proposée

- ne pas corriger les valeurs silencieusement ;
- choisir un vocabulaire non ambigu : `decay_mean_lifetime` ou
  `half_life`, mais pas un champ générique ;
- accepter temporairement un seul des deux champs et refuser leur présence
  simultanée ;
- convertir la demi-vie une seule fois lors du chargement ;
- enregistrer la convention effective dans les sorties reproductibles ;
- produire une note de migration listant les golden values affectées ;
- auditer séparément la signification scientifique de chaque chronique ¹⁴C.

Cette correction changera les concentrations historiques et doit être traitée
comme une correction scientifique versionnée, non comme un refactoring.

### 3.5 Unités et validation des observations

Les unités sont actuellement surtout descriptives. Une colonne absente reçoit
par défaut `mol/l`, même pour un CFC ou SF₆. Les unités d’observation ne sont pas
systématiquement comparées à celles du traceur utilisé pour la convolution.

Le fichier ³H annonce `mol` dans son YAML alors que sa chronique est documentée
en TU. Des variantes ¹⁴C utilisent `pCm%`, `pmC` ou `%modern`.

#### Modification proposée

- ne pas introduire immédiatement une bibliothèque générale d’unités ;
- définir un petit registre d’unités canoniques et d’alias ;
- exiger une unité explicite à l’entrée, ou utiliser `unknown` plutôt que
  `mol/l` par défaut ;
- vérifier l’égalité canonique observation/traceur avant calibration ;
- réserver les conversions physiques eau/atmosphère à des fonctions nommées et
  documentées, jamais implicites.

### 3.6 Lecture des chroniques CSV

Le chargeur utilise le premier enregistrement non commenté comme en-tête. Les
fichiers CFC-12 et ¹⁴C NH/SH commencent directement par une ligne numérique ;
leur premier point est donc absorbé comme nom de colonne.

D’autres incohérences ont été observées entre les métadonnées commentées et les
données réellement présentes, par exemple la période annoncée du tritium.

#### Modification proposée

- imposer le schéma `date,concentration` à tous les fichiers ;
- ajouter un validateur autonome des chroniques : en-tête, types, dates finies,
  ordre, doublons, valeurs négatives, plage annoncée et nombre de lignes ;
- trier explicitement les dates après validation ;
- décider explicitement de la politique hors domaine : zéro, erreur ou
  extrapolation interdite ;
- stocker source, version, zone atmosphérique et date de récupération dans un
  bloc de métadonnées structuré.

### 3.7 Convolution et troncature temporelle

La convolution classique intègre seulement entre `datemin` et la date
d’observation. Toute masse du LPM plus ancienne est multipliée par une entrée
nulle. Ce comportement peut être correct pour une histoire inconnue supposée
nulle, mais il ne faut pas le confondre avec une distribution renormalisée sur
la fenêtre disponible.

La résolution globale de 200 points n’est pas reliée à une tolérance numérique.
Les exponentielles et certaines inverse Gaussian ont des traitements spéciaux,
mais la précision n’est pas exposée dans les résultats.

#### Modification proposée

- rendre la politique de préhistoire explicite ;
- calculer et rapporter la masse \(F(t_{max})-F(t_{min})\) effectivement couverte ;
- ajouter un mode de référence lent fondé sur `scipy.integrate.quad` ou une
  quadrature adaptative, uniquement pour validation ;
- garder les chemins rapides actuels pour la production ;
- remplacer à terme la seule notion de résolution par une tolérance et une
  limite de coût configurables ;
- ajouter des tests de convergence sur fonctions constante, affine, échelon et
  exponentielle analytique.

### 3.8 Moments numériques génériques

Le calcul générique des moments tronque la distribution à
`1.2 * cdf_inv(0.98)` sans renormalisation. Il peut donc sous-estimer les moments
des distributions à longue traîne. Les modèles SciPy remplacent généralement ce
calcul par leurs moments analytiques, mais ce comportement reste dangereux pour
les nouveaux modèles personnalisés.

#### Modification proposée

- utiliser les moments analytiques lorsqu’ils existent ;
- pour le fallback, intégrer avec contrôle de masse et tolérance ;
- avertir si la masse couverte est insuffisante ;
- ne jamais utiliser un quantile arbitraire de 98 % comme contrat implicite.

### 3.9 Fonction objectif et erreurs analytiques

`L2_norm_diff()` divise par l’erreur sans refuser les zéros ou valeurs
négatives. Un autre chemin affiche seulement un message quand une erreur nulle
subsiste. L’affectation automatique d’erreurs peut également masquer un jeu de
données incomplet.

#### Modification proposée

- valider strictement `error > 0` avant toute calibration ;
- rendre l’imputation d’erreurs explicite dans la configuration et les sorties ;
- séparer clairement somme \(\chi^2\), RMSE normalisée et log-transformations
  destinées aux figures ;
- remplacer les `print`/`sys.exit` des chemins scientifiques par des exceptions
  typées, sans refaire toute l’architecture.

## 4. Refactoring minimal proposé

Le refactoring utile reste limité à quatre contrats :

1. **Paramètres de distribution** : paramètres natifs, unités, domaine et
   grandeurs dérivées explicitement distingués.
2. **Traceur** : fonction d’entrée, décroissance, production et politique hors
   domaine documentées séparément.
3. **Convolution** : valeur, masse couverte et diagnostic numérique disponibles
   ensemble dans un mode de diagnostic optionnel.
4. **Validation** : fonctions pures de validation des YAML, CSV et observations,
   appelées par les chargeurs existants.

Il n’est pas recommandé d’introduire une nouvelle hiérarchie de modèles, un
système général de dimensions physiques ou un moteur de calcul parallèle dans
ce chantier.

## 5. Nouvelle stratégie de tests

### 5.1 Tests analytiques de LPM

Pour chaque distribution :

- domaine des paramètres ;
- PDF positive ou description correcte des masses ;
- CDF monotone, bornée et cohérente aux frontières ;
- `cdf(cdf_inv(p)) >= p` selon la définition du quantile ;
- masse totale égale à 1 ;
- moyenne et variance analytiques ;
- cas limites documentés.

### 5.2 Tests analytiques de traceurs

- demi-vie : vérifier exactement \(C(t_{1/2})=C_0/2\) ;
- production stable : pente linéaire ;
- production avec décroissance : limite asymptotique ;
- interpolation linéaire sur une chronique minimale ;
- comportement avant/après la chronique ;
- détection des en-têtes absents, doublons et unités incompatibles.

### 5.3 Tests analytiques de convolution

- entrée constante et support suffisamment long : sortie constante ;
- PFM : évaluation exacte de l’entrée à l’âge imposé ;
- entrée exponentielle avec EMM : solution fermée ;
- mélange de Dirac : combinaison linéaire exacte ;
- comparaison chemin rapide / quadrature de référence ;
- convergence avec la résolution ;
- diagnostic de masse tronquée.

### 5.4 Rôle futur des golden tests

Les golden tests restent utiles pour détecter une dérive logicielle, mais ils
doivent venir après les invariants scientifiques. Lors d’une correction
scientifique :

1. le test analytique doit échouer avant la correction ;
2. la cause et l’impact doivent être documentés ;
3. les golden values ne sont mises à jour qu’après revue ;
4. les anciennes valeurs sont conservées dans une note de migration si elles
   ont été publiées ou utilisées dans un manuscrit.

## 6. Ordre de travail recommandé

| Priorité | Action | Nature | Risque pour les résultats |
|---|---|---|---|
| P0 | Ajouter les tests analytiques sans changer le code | Vérification | Aucun |
| P0 | Corriger le chargement des CSV sans en-tête | Données | Localisé mais réel |
| P0 | Clarifier et versionner les constantes radioactives | Scientifique | Élevé |
| P0 | Clarifier la paramétrisation inverse Gaussian | Scientifique/API | Élevé si reparamétrée |
| P1 | Corriger `dirac_double.cdf_inv()` | Bug démontré | Faible |
| P1 | Corriger le contrat de `mix_exp_shifted` | Bug démontré | Moyen |
| P1 | Valider unités et erreurs avant calibration | Robustesse | Moyen |
| P1 | Ajouter quadrature de référence et diagnostics | Vérification | Aucun en mode optionnel |
| P2 | Remplacer `print`/`sys.exit` dans le cœur | Refactoring | Faible |
| P2 | Rationaliser les variantes ¹⁴C | Données scientifiques | Élevé |

## 7. Critères d’acceptation avant comparaison externe

PyAges sera prêt pour une comparaison ciblée lorsque :

- PFM/Dirac, exponentielle et inverse Gaussian auront des tests analytiques ;
- la signification de chaque paramètre sera non ambiguë ;
- le temps de décroissance aura une convention unique ;
- les chroniques utilisées passeront un validateur de schéma et de métadonnées ;
- une quadrature de référence permettra de quantifier l’erreur des chemins
  rapides ;
- les sorties du benchmark enregistreront la masse couverte et les versions de
  données.
