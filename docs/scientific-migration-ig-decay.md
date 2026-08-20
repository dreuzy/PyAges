# Migration scientifique : loi inverse gaussienne et décroissance radioactive

Cette note décrit les conventions appliquées par PyAge depuis août 2026. Elle
sert de référence pour préparer les comparaisons avec TracerLPM et pour relire
les anciens fichiers de configuration.

## Loi inverse gaussienne

Les paramètres exposés par PyAge conservent leur interprétation scientifique :

- `mu` est le temps de transit moyen ;
- `sigma` est l'écart type des temps de transit ;
- le nombre de Péclet équivalent est `Pe = mu**2 / sigma**2`.

La convention de SciPy n'utilise pas directement ces deux moments. Pour
`scipy.stats.invgauss`, PyAge effectue donc la conversion suivante :

```text
shape = (sigma / mu)**2
scale = mu**3 / sigma**2
loc   = 0
```

Cette conversion garantit analytiquement une moyenne égale à `mu` et un écart
type égal à `sigma`. Pour la variante décalée, `mu` désigne la moyenne de la
composante dispersive et la moyenne totale vaut `shift + mu`.

Les résultats numériques produits auparavant avec la convention SciPy brute
ne sont pas comparables paramètre pour paramètre. Les références numériques des
tests ont été recalculées après vérification analytique des moments et de la
densité.

## Décroissance radioactive

Le champ historique `decay_time` était ambigu : selon son interprétation, il
pouvait désigner une demi-vie ou le temps moyen de décroissance. Il est désormais
refusé explicitement. Un traceur radioactif doit définir exactement l'un des
champs suivants, dans la même unité que les âges du modèle :

```yaml
# Convention recommandée : demi-vie physique publiée du radionucléide.
half_life: 12.32

# Autre convention possible, à ne pas combiner avec half_life :
# decay_mean_lifetime: 17.774
```

PyAge convertit ces valeurs en constante de décroissance `beta` :

```text
beta = ln(2) / half_life
beta = 1 / decay_mean_lifetime
C(t) = C(0) * exp(-beta * t)
```

Ainsi, après une demi-vie la concentration vaut exactement la moitié de la
concentration initiale. Pour une production constante `P`, la concentration
produite est `P * (1 - exp(-beta*t)) / beta`.

Les configurations livrées avec PyAge utilisent maintenant les demi-vies :

- tritium (`3H`) : 12.32 ans ;
- krypton 85 (`85Kr`) : 10.76 ans ;
- argon 39 (`39Ar`) : 267 ans ;
- carbone 14 (`14C`) : 5730 ans.

La valeur erronée `573` présente dans certaines configurations du carbone 14 a
été corrigée en `5730`.

## Contrôles de non-régression

La migration est couverte par des tests analytiques dédiés : moments et densité
de la loi inverse gaussienne, moyenne de la variante décalée, division par deux
à une demi-vie, facteur `1/e` au temps moyen, asymptote de production et rejet
des configurations radioactives ambiguës ou non positives.
