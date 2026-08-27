# Rapport d’évolution des méthodes de convolution de PyAges

> **Statut : rapport d’évolution historique rédigé le 19 août 2026.** La
> réanalyse Ploemeur annoncée ici comme future a ensuite été terminée le
> 22 août 2026. Le contrat scientifique actuel est synthétisé dans
> {doc}`science/forward-model` et les résultats de qualification dans
> {doc}`science/validation`.

## 1. Résumé exécutif

Le moteur de convolution de PyAges a été profondément modifié afin de rendre son
erreur numérique largement indépendante de la largeur de la distribution des
temps de transit (TTD/LPM). L’ancienne méthode évaluait la densité de
probabilité du LPM sur une grille d’âge, puis appliquait une intégration de
Simpson. Une distribution étroite pouvait donc tomber entre les points de la
grille, être fortement sous-intégrée ou, dans certains chemins spécialisés,
être sur-intégrée.

La nouvelle méthode repose sur deux quantités cumulées du LPM :

- la fonction de répartition $F(t)$, qui donne exactement la masse de
  probabilité contenue dans chaque intervalle ;
- le premier moment partiel
  $M(t)=\int_{-\infty}^{t}\tau\,\mathrm dF(\tau)$, qui donne la position
  moyenne de cette masse dans l’intervalle.

Pour un intervalle $[a_i,b_i]$, PyAges calcule désormais :

\[
w_i = F(b_i)-F(a_i),
\]

\[
q_i = \left[M(b_i)-M(a_i)\right]-a_iw_i
    = \int_{a_i}^{b_i}(\tau-a_i)\,\mathrm dF(\tau).
\]

Si la réponse du traceur est localement représentée par
$K(\tau)=K(a_i)+s_i(\tau-a_i)$, la contribution du bin est :

\[
C_i=K(a_i)w_i+s_iq_i.
\]

Cette expression est exacte pour toute réponse affine du traceur dans le bin,
quelle que soit la largeur ou la position de la PDF du LPM. La grille est donc
pilotée par la réponse du traceur, préparée une seule fois, puis réutilisée pour
toutes les propositions d’une calibration MCMC. Le raffinement en loi de
puissance auparavant utilisé pour les exponentielles, notamment les
exponentielles décalées, n’est plus nécessaire.

Toutes les distributions continues intégrées à PyAges disposent maintenant de
premiers moments partiels analytiques : exponentielle, exponentielles décalées,
Gamma, uniforme, Weibull, gaussienne inverse, gaussienne inverse décalée et
ShapeFree par classes uniformes. Le mélange Dirac–exponentielle utilise la même
méthode pour sa partie continue, tandis que les masses de Dirac restent
évaluées directement.

Les tests analytiques et les quadratures indépendantes éliminent les échecs
catastrophiques observés avec les PDF étroites. Sur les audits effectués,
l’écart relatif maximal observé par rapport à une quadrature indépendante est
de l’ordre de $3.3\times10^{-5}$, soit environ 0,0033 %. La convolution d’un
traceur affine est exacte à la précision machine pour toutes les distributions
continues intégrées.

Cette évolution modifie substantiellement la partie « méthodes numériques » de
l’article. Elle ne permet toutefois pas encore de conclure sur les résultats
scientifiques de Ploemeur : les calibrations, références et figures de ce cas
d’étude seront recalculées dans une seconde phase.

## 2. Périmètre et statut

Le présent rapport couvre :

1. le remplacement de l’intégration PDF + Simpson par une convolution fondée
   sur la CDF et le premier moment partiel ;
2. la construction et la mise en cache d’une grille pilotée par le traceur ;
3. la migration de toutes les distributions continues intégrées ;
4. la correction du modèle mixte Dirac–exponentielle ;
5. la correction de la paramétrisation de la gaussienne inverse ;
6. les diagnostics de masse, les validations numériques et les premiers
   résultats de performance.

Le cas Ploemeur est volontairement exclu du présent stade. Les références
génériques ont été réactualisées, mais les résultats scientifiques, les
postérieurs et les figures Ploemeur n’ont pas été régénérés avec le nouveau
moteur.

## 3. Méthode antérieure et limites identifiées

La concentration prédite à une date donnée s’écrit :

\[
C=\int_0^{T_{\max}}K(\tau)g(\tau)\,\mathrm d\tau,
\]

où $K(\tau)$ est la réponse complète du traceur pour un âge $\tau$, $g$
la PDF du LPM et $T_{\max}$ la profondeur temporelle de la chronique
disponible.

### 3.1 Chemin continu « classique »

Le moteur historique évaluait $K(\tau)g(\tau)$ sur une grille uniforme,
typiquement de 200 points, puis utilisait `scipy.integrate.simpson`. Le cache de
$K$ évitait de recalculer le traceur pendant les MCMC, mais la grille restait
fixe et indépendante de la forme réelle de la PDF.

Cette méthode est correcte lorsque la PDF et la réponse du traceur sont toutes
deux suffisamment résolues. Elle ne garantit cependant pas qu’une PDF étroite,
un support uniforme très court ou une distribution fortement décalée soit
échantillonné. Augmenter globalement le nombre de points réduit certains
écarts, mais augmente le coût de toutes les propositions MCMC sans apporter de
garantie générale.

### 3.2 Chemin spécialisé des exponentielles

Les exponentielles utilisaient une grille en loi de puissance, concentrée près
du début du support, puis une intégration de Simpson de la PDF. Cette méthode
était relativement efficace dans les cas usuels, mais sa résolution dépendait
toujours de la largeur et du décalage du LPM. Elle recalculait en outre la
réponse du traceur sur cette grille lors des convolutions.

### 3.3 Chemin spécialisé de la gaussienne inverse décalée

Les gaussiennes inverses décalées très étroites disposaient d’une grille
construite à partir de plusieurs quantiles. L’audit avait montré que ce chemin
pouvait produire une masse PDF intégrée très supérieure à 1 et des erreurs de
convolution supérieures à 1000 %. Cette spécialisation a été supprimée au
profit du moteur commun fondé sur la CDF.

### 3.4 Modèle mixte Dirac–exponentielle

Dans l’ancien code, la PDF de la partie exponentielle contenait déjà le facteur
((1-r)), puis la routine de convolution multipliait une seconde fois cette
partie par ((1-r)). Pour un traceur constant et une fenêtre contenant toute la
distribution, la masse calculée était donc :

\[
r+(1-r)^2=1-r+r^2,
\]

au lieu de 1. Pour $r=0.5$, le résultat était 0,75. Ce défaut était une erreur
de modèle, distincte de l’erreur de quadrature.

## 4. Nouvelle formulation CDF–premier moment

### 4.1 Séparation du traceur et du LPM

La nouvelle architecture sépare deux échelles numériques :

- la grille doit résoudre les variations de la réponse du traceur $K$ ;
- la CDF et le premier moment doivent décrire la masse et sa position dans le
  LPM.

Ainsi, une distribution peut devenir arbitrairement étroite sans nécessiter de
nouveaux points de grille, tant que $K$ est correctement représenté dans le
bin qui contient cette distribution.

### 4.2 Préparation de la grille du traceur

Pour une date d’échantillonnage donnée, la grille contient toujours 0 et
$T_{\max}$. Lorsqu’une chronique est disponible, tous ses nœuds situés dans la
fenêtre sont convertis en âges et introduits comme bords de bins. Cela aligne la
grille avec les ruptures de pente de l’interpolation temporelle.

Chaque intervalle est ensuite testé à gauche, au milieu et à droite. Il est
accepté lorsque :

\[
\max(K_a,K_m,K_b)-\min(K_a,K_m,K_b)
\leq 5\times10^{-4}K_{\mathrm{global}}
   +2\times10^{-2}K_{\mathrm{local}}.
\]

Ces valeurs sont regroupées dans l’objet immuable `TracerGridSettings`, qui
peut être transmis au constructeur de la convolution et enregistré avec un
calcul reproductible. Ce sont des paramètres numériques, non des paramètres
scientifiques du modèle. Une analyse de sensibilité reste recommandée dans le
matériel supplémentaire de l’article.

Le raffinement est limité à 20 subdivisions par intervalle et à 20 000 bins.
Un dépassement produit une erreur explicite plutôt qu’une boucle incontrôlée.
Une recharge constante conserve une grille minimale d’un seul bin.

La fin récente d’une chronique peut introduire une discontinuité entre une
valeur nulle hors domaine et la première valeur de la chronique. Cette date est
désormais traitée comme une frontière physique avec deux limites unilatérales,
ce qui empêche le raffinement de poursuivre indéfiniment autour du saut.

### 4.3 Masse exacte dans chaque bin

À chaque nouvelle proposition de paramètres du LPM, la CDF est évaluée de
manière vectorisée aux bords de la grille. Les poids
$w_i=F(b_i)-F(a_i)$ représentent exactement la masse de probabilité dans les
bins, à l’erreur flottante de la CDF près.

Le moteur vérifie la monotonie de la CDF. Seules de minuscules valeurs
négatives compatibles avec l’arrondi machine peuvent être ramenées à zéro ;
une masse négative significative provoque une erreur explicite.

### 4.4 Rôle du premier moment partiel

Une formulation utilisant seulement $w_i$ et la valeur de $K$ au milieu du
bin garantit la masse, mais pas la position de cette masse. Ce point est
particulièrement important pour une exponentielle décalée étroite : presque
toute la probabilité se situe immédiatement après le décalage, et non au milieu
d’un bin potentiellement large.

Le premier moment partiel donne directement le barycentre de la masse :

\[
\bar\tau_i=\frac{M(b_i)-M(a_i)}{w_i}, \qquad w_i>0.
\]

La formule effectivement utilisée évite la division par $w_i$ et reste donc
stable lorsque la masse est très petite :

\[
C_i=K(a_i)w_i+s_i
\left[M(b_i)-M(a_i)-a_iw_i\right].
\]

Pour un $K$ affine, cette formule n’est pas une approximation de quadrature :
elle est l’intégrale analytique exacte de l’interpolation linéaire de $K$
contre la distribution du LPM.

### 4.5 Réponse non linéaire du traceur

La linéarité locale est contrôlée par l’écart entre $K$ au milieu et la
moyenne des valeurs aux extrémités. Lorsque la courbure résiduelle est faible,
la formule au premier moment est utilisée. Lorsqu’elle est détectable mais que
la variation totale du bin respecte déjà la tolérance, le moteur conserve la
valeur au milieu du bin.

Il s’agit donc d’un schéma hybride : exact au premier ordre et prudent lorsque
la réponse locale n’est pas affine. L’erreur résiduelle dépend de la courbure de
$K$, plus de la largeur de la PDF. La méthode ne fournit pas encore une borne
d’erreur formelle globale ; sa précision est établie empiriquement par les
tests analytiques et les quadratures indépendantes.

### 4.6 Troncature temporelle

La masse couverte par la chronique est :

\[
m_{\mathrm{fenêtre}}=F(T_{\max})-F(0)
\]

pour une distribution continue. Cette masse n’est jamais renormalisée. Une
partie du LPM plus ancienne que la chronique reste volontairement omise, ce qui
équivaut à appliquer une entrée nulle dans la période non documentée.

Cette convention doit être explicitée dans l’article. Une valeur
$m_{\mathrm{fenêtre}}<1$ n’est pas nécessairement une erreur numérique : elle
peut signaler une troncature réelle du support temporel disponible.

## 5. Pourquoi le raffinement en loi de puissance n’est plus nécessaire pour l’exponentielle décalée

Considérons $T=s+X$, avec $X\sim\mathrm{Exp}(\mu)$. Lorsque $\mu$ est petit,
la PDF est très concentrée au voisinage de $s$. L’ancien maillage devait
placer beaucoup de points près de $s$ pour intégrer correctement cette PDF.
Ce besoin dépendait donc directement du LPM.

Avec la nouvelle méthode :

- $F(b)-F(a)$ donne exactement la masse située entre $a$ et $b$, même si
  aucun point de grille ne traverse le pic de PDF ;
- $M(b)-M(a)$ donne exactement l’âge moyen non normalisé de cette masse ;
- l’interpolation de $K$ évalue donc cette masse à sa position moyenne
  correcte.

La grille n’a plus à résoudre la PDF exponentielle. Elle doit uniquement
résoudre $K$. Cette conclusion vaut également pour une Gamma étroite, une
uniforme de largeur 0,5 an, une Weibull concentrée ou une gaussienne inverse de
faible dispersion.

## 6. Premiers moments analytiques par distribution

On note $P(a,x)$ la fonction Gamma incomplète régulière, $\Phi$ la CDF
normale standard et $M(t)=E[T\mathbf 1_{T\leq t}]$.

### 6.1 Exponentielle et exponentielle décalée

Pour $T=s+X$, $X\sim\mathrm{Exp}(\mu)$, et
$z=(t-s)/\mu>0$ :

\[
F(t)=1-e^{-z},
\]

\[
M(t)=sF(t)+\mu P(2,z)
=sF(t)+\mu\left[1-(1+z)e^{-z}\right].
\]

Les calculs utilisent `expm1` pour préserver la précision lorsque $z$ est
petit. La même implémentation analytique est utilisée par `exp` et
`exp_shifted`.

### 6.2 Loi Gamma

Pour $T\sim\Gamma(k,\theta)$ :

\[
F(t)=P(k,t/\theta),
\]

\[
M(t)=k\theta P(k+1,t/\theta).
\]

### 6.3 Loi uniforme

Pour $T\sim U[a,a+d]$, lorsque $a<t<a+d$ :

\[
F(t)=\frac{t-a}{d},
\]

\[
M(t)=\frac{t^2-a^2}{2d}.
\]

Les expressions sont prolongées par 0 avant le support et par la masse et la
moyenne totales après le support.

### 6.4 Loi de Weibull

Pour une forme $k$ et une échelle $\lambda$ :

\[
F(t)=1-\exp\left[-(t/\lambda)^k\right],
\]

\[
M(t)=\lambda\Gamma(1+1/k)
P\left(1+1/k,(t/\lambda)^k\right).
\]

### 6.5 Gaussienne inverse

Les paramètres publics ont désormais leur sens physique : $\mu$ est la
moyenne et $\sigma$ l’écart-type. Le paramètre de forme conventionnel est :

\[
\lambda_{IG}=\frac{\mu^3}{\sigma^2}.
\]

En posant :

\[
A=\sqrt{\frac{\lambda_{IG}}{t}}\left(\frac{t}{\mu}-1\right),
\qquad
B=-\sqrt{\frac{\lambda_{IG}}{t}}\left(\frac{t}{\mu}+1\right),
\]

on obtient :

\[
F(t)=\Phi(A)+\exp(2\lambda_{IG}/\mu)\Phi(B),
\]

\[
M(t)=\mu\left[\Phi(A)-\exp(2\lambda_{IG}/\mu)\Phi(B)\right].
\]

L’implémentation évalue le terme réfléchi dans le domaine logarithmique afin
d’éviter les débordements numériques. Pour la variante décalée
$Y=s+T$ :

\[
F_Y(t)=F_T(t-s),
\qquad
M_Y(t)=sF_T(t-s)+M_T(t-s).
\]

### 6.6 ShapeFree par classes uniformes

Chaque classe est traitée comme une loi uniforme portant sa fraction de masse.
La CDF et le premier moment sont la somme exacte des contributions
polynomiales tronquées de chaque classe. La largeur du dernier bin ancien est
donc prise en compte sans intégrer numériquement sa PDF.

## 7. Correction et traitement du modèle mixte

Le modèle `mix_exp_shifted` est maintenant défini sans ambiguïté par :

- une masse $r$ à l’âge $\mu_1$ ;
- une exponentielle normalisée de masse 1, de support inférieur
  $L=\mu_1+s$ et d’échelle $\mu_2$, pondérée ensuite par $1-r$.

Sa convolution est :

\[
C=rK(\mu_1)+(1-r)C_{\mathrm{exp,norm}}.
\]

Chaque poids est appliqué exactement une fois. La CDF, le quantile généralisé,
la moyenne et l’écart-type du mélange ont également été corrigés. Sa moyenne
est :

\[
E[T]=r\mu_1+(1-r)(\mu_1+s+\mu_2)
=\mu_1+(1-r)(s+\mu_2).
\]

La conservation a été vérifiée pour
$r\in\{0,0.1,0.5,0.9,1\}$. Avec un traceur constant et toute la masse dans la
fenêtre, la convolution vaut désormais 1.

## 8. Reparamétrisation scientifique de la gaussienne inverse

Cette évolution est distincte du changement de quadrature, mais elle affectera
potentiellement davantage les résultats de l’article.

L’ancien code transmettait directement `mu` comme forme SciPy et `sigma` comme
échelle SciPy. Dans cette convention, la moyenne réelle était
$\mu\sigma$ et la variance $\mu^3\sigma^2$, alors que les paramètres PyAges
étaient décrits comme moyenne et écart-type.

PyAges convertit maintenant les moments physiques vers SciPy :

\[
\text{shape}_{SciPy}=(\sigma/\mu)^2,
\qquad
\text{scale}_{SciPy}=\mu^3/\sigma^2.
\]

Cette conversion garantit $E[T]=\mu$ et
$\operatorname{Std}(T)=\sigma$. Pour la gaussienne inverse décalée, la
moyenne totale vaut $s+\mu$, tandis que $\sigma$ reste l’écart-type de la
composante dispersive.

Conséquence importante : deux calculs utilisant les mêmes valeurs numériques
de `mu` et `sigma` avant et après cette correction ne représentent généralement
pas la même distribution. Les anciennes estimations fondées sur la convention
SciPy brute ne doivent pas être comparées paramètre par paramètre aux nouvelles
sans conversion ou recalibration.

## 9. Cache, coût MCMC et contrat strict

La grille et toutes les valeurs de $K$ aux extrémités et aux milieux des bins
sont calculées une seule fois par couple traceur–date. Après préparation, 1,
10 ou 100 convolutions successives ne provoquent aucun nouvel appel au calcul
du traceur. Les effets fixes du traceur — interpolation, décroissance et
production — sont donc inclus dans le cache.

Pour les LPM intégrés, une proposition MCMC nécessite seulement :

1. une évaluation vectorisée de $F$ et $M$ sur les bords ;
2. des différences vectorielles ;
3. quelques opérations vectorielles et une somme.

La stratégie continue porte maintenant le nom explicite `CONTINUOUS`. Les noms
historiques `CLASSIC` et `EXPONENTIAL` ont été supprimés. La préparation
explicite du cache reste possible avec `prepare()`, mais `convolve()` construit
automatiquement la grille lorsqu’elle manque ou lorsque la date change ; aucun
booléen d’état n’est demandé à l’appelant.

Tout LPM continu doit fournir une CDF vectorisée et un premier moment partiel.
L’absence de ce contrat produit une erreur explicite. PyAges ne reconstruit plus
silencieusement une CDF par intégration trapézoïdale de la PDF et n’utilise plus
de quadrature adaptative dans le moteur de production. Les quadratures lentes
restent réservées aux tests et aux outils de validation indépendants.

Le contrat des traceurs est également devenu strict. Un traceur doit fournir
explicitement son domaine temporel, ses valeurs caractéristiques, ses dates de
chronique éventuelles et le nombre initial de bins à employer lorsqu’il ne
possède pas de chronique. Le moteur n’inspecte plus d’attribut privé et ne
devine plus ces informations avec des valeurs par défaut. Un objet incomplet
est refusé dès la construction de `Convolution`.

Cette migration a été accompagnée d’un nettoyage volontairement cassant des
anciennes interfaces : suppression de la façade `global_parameters`, du
lanceur temporel dupliqué, des ajustements automatiques de `sys.path`, de
l’ancien générateur autonome de composants et des fichiers de paramètres LPM
antérieurs à `params.yaml`. Les configurations YAML refusent maintenant toute
clé inconnue. Les générateurs aléatoires utilisent exclusivement
`numpy.random.Generator`. Ces changements ne modifient pas la formulation
scientifique, mais réduisent les chemins d’exécution possibles et rendent la
configuration effectivement utilisée traçable.

## 10. Diagnostics numériques

Après chaque convolution continue, PyAges conserve :

- `window_mass` : masse du LPM située dans la fenêtre disponible ;
- `n_bins` : nombre de bins de la grille du traceur ;
- `min_weight` : plus petite différence de CDF avant correction éventuelle ;
- `clipped_weight_count` : nombre de poids négatifs de taille flottante ramenés
  à zéro.

Le moteur vérifie aussi que le moment centré d’un bin satisfait :

\[
0\leq q_i\leq(b_i-a_i)w_i.
\]

Une violation significative signale une incohérence entre CDF et premier
moment et interrompt le calcul.

## 11. Validation effectuée

### 11.1 Tests analytiques

Les premiers moments partiels de toutes les distributions ont été comparés à
une intégration indépendante de $\tau g(\tau)$ avec des tolérances relatives
de l’ordre de $2\times10^{-11}$. Les tests couvrent la vectorisation,
$t=+\infty$, la moyenne totale et des paramètres extrêmes.

Un traceur affine $K(\tau)=2+0.01\tau$ a été convolué sur un seul bin. Toutes
les distributions continues et le modèle mixte reproduisent exactement :

\[
C=2\,m_{\mathrm{fenêtre}}+0.01\,M(T_{\max})
\]

à environ $2\times10^{-13}$ près ou mieux.

### 11.2 Cas pathologiques de l’audit

Les tests permanents comprennent notamment :

- exponentielle d’échelle 0,1 an ;
- gaussienne inverse $(\mu,\sigma)=(0.5,0.1)$ ;
- gaussiennes inverses décalées étroites ;
- Gamma $(k,\theta)=(10,0.1)$ et $(0.5,50)$ ;
- uniformes de largeur 0,5 an à différents âges ;
- Weibull très étroite et Weibull à longue traîne ;
- CFC-11 et argon 39 comme réponses de traceur contrastées.

Ces cas sont comparés à une intégration indépendante dans l’espace des
quantiles. Le pire écart relatif observé dans cet audit ciblé est d’environ
$1.10\times10^{-5}$, soit 0,00110 %, pour une gaussienne inverse étroite avec
l’argon 39. La tolérance de non-régression est fixée à $2\times10^{-4}$, soit
0,02 %.

### 11.3 Matrice multi-traceurs indépendante

Une vérification exploratoire a comparé les résultats à une quadrature de
Gauss–Legendre à 128 et 256 points entre chaque nœud de chronique, pour CFC-11,
Kr-85, CFC-12, CFC-113 et SF6, et pour toutes les familles continues ainsi que
le mélange.

- Les traceurs sans courbure radioactive résiduelle concordent généralement à
  la précision machine.
- Le pire écart relatif de la matrice est
  $3.222\times10^{-5}$, soit 0,003222 %, pour une loi uniforme avec Kr-85.
- Les références à 128 et 256 points concordent entre elles à environ
  $3\times10^{-16}$ dans cette matrice.

Cette matrice a servi d’audit exploratoire ; les cas pathologiques et les
invariants principaux sont, eux, enregistrés comme tests permanents.

### 11.4 Suite logicielle

La couverture complète hors Ploemeur a été exécutée de manière consolidée :

- 497 tests du dépôt réussis ;
- 53 tests supplémentaires du banc de qualification TracerLPM réussis ;
- 550 tests réussis au total ;
- 4 tests ignorés ;
- aucun échec.

Les contrôles de style, la compilation Python et le contrôle d’intégrité des
diffs sont également réussis. Les golden tests génériques de convolution, de
chroniques de concentration et de calibration ont été réactualisés après les
comparaisons indépendantes. Les golden tests Ploemeur n’ont pas été
réactualisés dans cette phase.

## 12. Performance mesurée

Un premier benchmark a comparé l’exponentielle décalée avec l’ancien chemin
Simpson à 1001 points, sur 200 jeux de paramètres :

| Configuration | Nouvelle méthode | Ancienne méthode | Accélération |
|---|---:|---:|---:|
| 1 traceur | 0,1807 s | 0,2218 s | 1,23× |
| 4 traceurs | 0,6423 s | 0,8487 s | 1,32× |
| 5 traceurs | 0,7808 s | 1,0803 s | 1,38× |

Les différences de somme de contrôle avec l’ancien Simpson sont d’environ
$8\times10^{-7}$ en relatif et correspondent à la suppression de l’erreur de
quadrature de l’ancien chemin ; l’ancien résultat n’est pas utilisé comme
référence scientifique.

Ce benchmark indique que l’unification des exponentielles ne sacrifie pas les
performances. Il ne remplace pas encore un benchmark systématique publié de
toutes les familles de LPM. Avant soumission de l’article, il serait utile de
mesurer séparément temps de préparation, temps par proposition et nombre de
bins pour Gamma, uniforme, Weibull et gaussienne inverse sur les configurations
effectivement utilisées à Ploemeur.

## 13. Changements attendus dans l’article

### 13.1 Partie Méthodes

La description d’une intégration de la PDF par Simpson et d’un raffinement
spécial des exponentielles doit être remplacée par une section consacrée à la
méthode CDF–premier moment. Cette section devrait préciser :

1. la définition de la fenêtre temporelle ;
2. la construction de la grille à partir des nœuds du traceur ;
3. le raffinement fondé sur la variation de $K$ ;
4. les poids exacts $w_i$ issus de la CDF ;
5. le premier moment partiel et la formule affine exacte ;
6. l’absence de renormalisation de la masse tronquée ;
7. le traitement direct des Dirac ;
8. la mise en cache avant les MCMC.

Le nom recommandé dans l’article est **CDF–partial-first-moment convolution**,
ou en français **convolution par fonction de répartition et premier moment
partiel**. Le terme « quadrature CDF » seul est insuffisant, car l’amélioration
décisive par rapport à la méthode au milieu du bin vient du premier moment.

### 13.2 Définition des LPM

Une table des LPM devrait donner pour chaque famille : les paramètres
physiques, le support, la moyenne, et la disponibilité d’une expression
analytique de $F$ et $M$. La gaussienne inverse doit explicitement définir
`mu` comme moyenne, `sigma` comme écart-type et indiquer la conversion vers la
convention interne de la bibliothèque numérique.

Le mélange Dirac–exponentielle doit être présenté comme une mesure mixte, et
non comme une PDF continue ordinaire. Sa masse discrète, sa partie continue
normalisée et leurs poids doivent être écrits séparément.

### 13.3 Résultats et comparabilité historique

Les changements de résultats devront être attribués à trois causes distinctes :

1. **nouvelle intégration numérique** : petits écarts dans les cas bien résolus,
   correction potentiellement très forte lorsque l’ancienne grille manquait une
   PDF étroite ;
2. **correction du mélange** : changement systématique de la contribution
   continue lorsque $0<r<1$ ;
3. **reparamétrisation de la gaussienne inverse** : changement de distribution
   physique pour des valeurs numériques identiques de `mu` et `sigma`.

Ces effets ne doivent pas être agrégés sous l’expression générale « changement
de précision numérique ». Le troisième est une correction de convention
scientifique et peut déplacer substantiellement les paramètres calibrés.

Une autre migration présente dans l’état actuel de PyAges concerne la
décroissance radioactive : les configurations utilisent désormais des champs
non ambigus de demi-vie ou de temps moyen de décroissance. Si Ploemeur utilise
des radionucléides, l’impact de cette correction devra être quantifié
séparément de celui du moteur de convolution.

### 13.4 Matériel supplémentaire recommandé

Le supplément numérique devrait contenir :

- un schéma de la grille pilotée par $K$ ;
- une démonstration de la formule affine ;
- les expressions de $M(t)$ par famille de LPM ;
- les cas de test constant, affine et fortement tronqué ;
- le tableau complet des erreurs par traceur et LPM ;
- une analyse de sensibilité aux tolérances de raffinement ;
- les temps de préparation et de convolution répétés ;
- la masse de fenêtre pour chaque configuration Ploemeur finale.

## 14. Ce qui peut être affirmé dès maintenant

Les affirmations suivantes sont étayées par le code et les tests actuels :

- le calcul de masse ne peut plus manquer une distribution étroite placée entre
  deux points d’évaluation de PDF ;
- la convolution est exacte pour une réponse affine du traceur et les premiers
  moments analytiques intégrés ;
- aucune renormalisation implicite de la masse temporellement tronquée n’est
  effectuée ;
- la composante continue du mélange est pondérée exactement une fois ;
- les évaluations du traceur sont mises en cache avant les répétitions MCMC ;
- le chemin spécialisé en loi de puissance des exponentielles n’est plus
  nécessaire ;
- les échecs catastrophiques identifiés dans l’audit sont éliminés dans les cas
  de non-régression testés.

Les affirmations suivantes doivent attendre la phase Ploemeur :

- l’ampleur du changement des paramètres postérieurs ;
- la stabilité des classements entre familles de LPM ;
- l’effet sur les intervalles de confiance et les conclusions hydrogéologiques ;
- la comparaison finale des figures et tableaux anciens/nouveaux ;
- le coût total des calibrations longues dans la configuration de production.

## 15. Plan de la seconde phase : Ploemeur

1. **Geler les conventions** : enregistrer la version du code, les paramètres
   de raffinement, les chroniques et les conventions de décroissance.
2. **Calcul direct avant calibration** : comparer ancien et nouveau moteur sur
   une grille commune de paramètres pour chaque LPM utilisé.
3. **Diagnostic de troncature** : enregistrer `window_mass` pour chaque
   traceur, date et région pertinente de l’espace des paramètres.
4. **Références indépendantes** : contrôler un sous-ensemble représentatif par
   quadrature en espace des quantiles ou quadrature segmentée haute précision.
5. **Recalibrations courtes contrôlées** : utiliser des graines et états
   initiaux communs pour identifier les effets méthodologiques.
6. **Calibrations longues de production** : relancer les chaînes retenues et
   vérifier convergence, autocorrélation et stabilité entre répétitions.
7. **Décomposition des écarts** : séparer intégration, mélange, gaussienne
   inverse et décroissance radioactive.
8. **Mise à jour de l’article** : régénérer figures, tableaux, annexes et
   résultats numériques uniquement après validation.
9. **Golden tests Ploemeur** : mettre à jour les références seulement après
   acceptation scientifique des nouveaux résultats.

## 16. Proposition de paragraphe méthodologique pour l’article

Le texte suivant peut servir de base à une version anglaise du manuscrit :

> Convolutions were evaluated over the time interval covered by each tracer
> input history using a grid designed to resolve the tracer response rather
> than the probability density of the transit-time distribution. Chronicle
> nodes were included as bin boundaries, and the grid was refined once, prior
> to repeated model evaluations, according to the within-bin variation of the
> tracer response. For each bin \([a_i,b_i]\), the probability mass was computed
> exactly from the cumulative distribution function as
> \(w_i=F(b_i)-F(a_i)\). The partial first moment
> \(M(t)=E[T\mathbf 1_{T\le t}]\) was used to integrate the local linear
> representation of the tracer response, yielding
> \(K(a_i)w_i+s_i[M(b_i)-M(a_i)-a_iw_i]\). Consequently, narrow or shifted
> transit-time distributions do not require distribution-specific mesh
> refinement. Probability mass older than the available tracer history was not
> renormalized, and its omission was reported through the covered-window mass.
> Discrete Dirac components were evaluated directly, while continuous mixture
> components were normalized and weighted exactly once. The tracer-response
> grid was cached and reused throughout repeated calibration evaluations.

Ce texte était une proposition de travail au 19 août 2026. Les tolérances, les
familles de LPM retenues et les qualifications finales ont depuis été précisées
dans la révision v14 du manuscrit ; leur synthèse maintenue se trouve dans
{doc}`science/forward-model` et {doc}`science/validation`.

## 17. Traçabilité dans le dépôt

Les principaux éléments sont accessibles dans :

- `pyages/convolution/convolution.py` : préparation de la grille, convolution
  CDF–moment, diagnostics et mélanges ;
- `pyages/lpm/models/` : expressions analytiques des CDF et premiers moments ;
- `tests/convolution/test_convolution_scientific.py` : invariants de masse,
  cache, troncature, cas pathologiques et références indépendantes ;
- `tests/lpm/test_continuous_partial_moments.py` : validation des premiers
  moments de toutes les familles continues ;
- `tests/lpm/test_inverse_gaussian_analytics.py` : contrat physique de la
  gaussienne inverse ;
- `docs/scientific-migration-ig-decay.md` : note séparée sur la gaussienne
  inverse et la décroissance radioactive.

Ce rapport conserve l’état du chantier au 19 août 2026. La campagne Ploemeur
ultérieure, ses résultats finaux et son périmètre d’interprétation sont décrits
dans la couche `article/` et dans {doc}`science/case-studies`. Les formulations
prospectives ci-dessus doivent donc être lues comme l’historique de la méthode,
pas comme l’état courant du manuscrit.
