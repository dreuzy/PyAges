# Gabarit de plugin LPM externe

Ce dossier montre à quoi pourrait ressembler un paquet LPM conservé entièrement
en dehors de PyAges.

Il contient un modèle continu complet qui **n'utilise pas `scipy.stats`** :
`bounded_power`. Sa densité est une loi de puissance normalisée sur l'intervalle
`[0, tau]`.

## Statut important

La classe mathématique et ses tests utilisent les contrats actuels de PyAges.
En revanche, la découverte automatique du plugin dépend de l'API proposée
`pyages.lpm.extensions.LpmDefinition`, qui n'est pas encore implémentée.

Le dossier est donc un gabarit de conception, pas encore un plugin installable
et découvrable par la version actuelle de PyAges.

## Organisation

```text
external_lpm_plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── pyages_lpm_bounded_power/
│       ├── __init__.py
│       ├── model.py
│       ├── plugin.py
│       └── data_lpm/
│           └── bounded_power/
│               └── params.yaml
└── tests/
    └── test_model.py
```

## Distribution d'exemple

Pour `tau > 0` et `alpha > 0`, la densité vaut :

```text
              alpha + 1   t
pdf(t) =      --------- (---)^alpha     pour 0 <= t <= tau
                  tau     tau
```

Elle est nulle en dehors de `[0, tau]`.

Sa fonction de répartition est :

```text
cdf(t) = (t / tau)^(alpha + 1)          pour 0 <= t <= tau
```

Le paramètre `tau` fixe l'âge maximal et `alpha` contrôle la forme : plus
`alpha` est grand, plus la masse est concentrée vers les âges proches de
`tau`.

Ce modèle est choisi pour sa simplicité pédagogique. Son utilisation dans une
étude hydrogéologique demanderait une justification scientifique propre.

## Utiliser ce dossier comme gabarit

1. Copier tout le dossier hors du dépôt PyAges.
2. Remplacer `bounded_power` par le nom du nouveau modèle.
3. Renommer le paquet `pyages_lpm_bounded_power`.
4. Adapter la classe et les formules dans `model.py`.
5. Adapter les paramètres dans `params.yaml`.
6. Mettre à jour le point d'entrée dans `pyproject.toml`.
7. Remplacer les invariants scientifiques dans `tests/test_model.py`.

Les méthodes à conserver pour un modèle continu sont :

```text
pdf
cdf
cdf_inv
mean
std
cdf_and_partial_first_moment
```

La dernière méthode est nécessaire au moteur de convolution continue de
PyAges.

## Séparation des responsabilités

- `model.py` contient uniquement les mathématiques du modèle.
- `params.yaml` contient les bornes et réglages de calibration.
- `plugin.py` relie le modèle à son fichier de paramètres.
- `pyproject.toml` annonce le plugin à PyAges.
- `test_model.py` vérifie indépendamment les formules essentielles.
