# Audit d'architecture et de robustesse MH — 1er septembre 2026

## Conclusion

L'API publique reste stable, mais les contrats scientifiques et les frontières
internes sont maintenant plus explicites. Le principal défaut corrigé était la
confusion entre l'état proposé par Metropolis--Hastings et l'état effectivement
accepté. La seconde correction structurante sépare désormais le domaine de
validité d'un modèle, la plage opérationnelle d'une calibration et le prior.

La suite standard passe intégralement : **1 456 tests réussis, 15 ignorés et
89 % de couverture de lignes**. Ruff passe sur tout le dépôt et garantit qu'aucune
fonction ne dépasse la complexité cyclomatique configurée de 10. Quatre cas MH
extensifs paramétrés ont également été observés comme réussis. Les cinq workflows
scientifiques extensifs restants n'ont pas fourni de statut local final après
une session de terminal orpheline; ils sont désormais obligatoires dans le CI
scientifique et dans la porte de sortie d'une release candidate.

Ce résultat ne signifie pas que chaque branche est couverte ou que tous les
fichiers ont une taille idéale. `results.py` et `manifest.py` restent les deux
principaux points chauds. Leur complexité est en grande partie liée à des
invariants de provenance et d'atomicité, mais d'autres extractions pourront être
faites dans des changements dédiés.

```{note}
Suivi du 4 septembre 2026 : les micro-modules `_sampler_transition.py` et
`_sampler_storage.py`, qui n'avaient chacun qu'un seul consommateur, ont été
réintégrés dans `sampler.py`. Le contrat décrit ci-dessous est inchangé, mais le
chemin d'accès est désormais plus direct.
```

## 1. Une proposition MH n'est plus un état accepté

### Problème

L'ancien flot évaluait une proposition en modifiant le LPM public. Si la
proposition était rejetée, le vecteur local de la chaîne restait correct, mais
`problem.lpm` pouvait encore contenir la proposition rejetée. Deux vérités
coexistaient alors :

```text
état de la chaîne : mu = 10       LPM public : mu = 40
                         rejet de la proposition 40
```

Un rapport, un callback ou une analyse exécuté à cet instant pouvait donc lire
un modèle qui ne représentait pas la chaîne.

### Solution retenue

Une copie de travail est créée une seule fois par chaîne dans
[`_sampler_target.py`](../../pyages/calibration/methods/mh/_sampler_target.py).
Elle est réutilisée pour les évaluations afin de ne pas payer une copie profonde
à chaque transition.

```text
LPM accepté theta
       |
       +--> proposition theta' --> LPM candidat privé --> score
                                                    |
                              rejet : aucune écriture publique
                              acceptation : commit theta' dans le LPM public
```

[`sampler.py`](../../pyages/calibration/methods/mh/sampler.py) sélectionne
ensemble paramètres, log-cible, chi-deux et concentrations. Un seul choix
d'acceptation déplace donc tout l'état ou rien. La séquence de tirages aléatoires
historique est conservée : une amélioration certaine ne consomme toujours pas
de tirage uniforme supplémentaire.

### Comportement

Les échantillons numériques d'une configuration valide restent inchangés. Le
changement observable est intentionnel : après un rejet, le LPM public contient
maintenant l'état courant accepté au lieu du dernier candidat essayé.

## 2. Domaine du modèle, plage de calibration et prior

### Pourquoi les anciennes `bounds` étaient ambiguës

Pour l'inverse gaussienne `ig`, l'ancienne limite `mu: [0.1, 70]` pouvait être
lue de trois façons différentes :

- la formule est-elle invalide au-dessus de 70 ans ? Non;
- souhaite-t-on chercher au-dessus de 70 ans dans cette configuration ? Non;
- le prior interdit-il les valeurs au-dessus de 70 ans ? Pas nécessairement.

La borne 70 vient du fichier de configuration historique du LPM. C'est une
**plage de calibration finie**, utile à l'optimiseur, aux propositions et au
plan d'expérience. Ce n'est ni une singularité de la formule, ni un prior.

### Contrat en trois parties

Les responsabilités sont distribuées entre trois zones :

1. [`data_io/lpm_params.py`](../../pyages/data_io/lpm_params.py) parse le
   `domain`, la `calibration_range` et la définition du `prior`;
2. [`lpm/core/parameter_manager.py`](../../pyages/lpm/core/parameter_manager.py)
   expose et contrôle le domaine mathématique et la plage opérationnelle;
3. [`calibration/methods/mh/prior.py`](../../pyages/calibration/methods/mh/prior.py)
   calcule support, densité, quantiles et moments probabilistes.

Exemple canonique :

```yaml
- name: mu
  domain: {min: 0.0, min_inclusive: false, max: null}
  calibration_range: [0.1, 70.0]
  prior:
    type: uniform
    min: 0.0
    max: 100.0
```

Ici, la formule accepte tout `mu > 0`, la calibration cherche dans
`[0.1, 70]`, et le support MH effectif est l'intersection
`[0.1, 70] ∩ [0, 100] = [0.1, 70]`.

### Décisions prises

- La plage de calibration doit être entièrement incluse dans le domaine du
  modèle.
- Un constructeur ou `set_param_from_array` refuse immédiatement une valeur
  hors du domaine, mais accepte une valeur hors de la plage de calibration si
  la formule reste valide. Par exemple, `exp(mu=150)` est un LPM valide avec le
  fichier standard, mais n'est pas un candidat admissible pour sa calibration
  standard limitée à 100.
- Les douze LPM distribués déclarent explicitement leurs deux notions. Les
  échelles et formes sont strictement positives, les âges et délais sont
  non négatifs, les taux sont dans `[0, 1]` et les coordonnées latentes du
  shape-free sont non bornées mathématiquement.
- `mix_exp_shifted.mu1 = 0` reste valide : une masse de Dirac à l'âge zéro est
  scientifiquement et numériquement représentable, même si la plage de
  calibration distribuée commence à 0.1.
- Les anciennes plages numériques ont été conservées. Elles ne changent donc
  pas la cible des calibrations standards.
- Un prior uniforme doit avoir une intersection de largeur positive avec la
  plage de calibration. Les moments théoriques de qualification sont calculés
  sur le support effectif. Cela corrige notamment le diagnostic du prior `ig`.
- Le champ historique `bounds` et les méthodes `get_bounds` restent des alias
  compatibles. Dans un ancien YAML sans `domain`, `bounds` sert aussi de domaine
  de repli. Aucun calendrier de suppression n'est décidé dans ce changement.

Le gabarit `pyages new lpm` et la documentation produisent désormais les champs
explicites.

## 3. Préparation atomique d'un problème de calibration

### Problème

Une erreur pendant la construction des traceurs pouvait laisser un objet
partiellement initialisé : LPM présent, traceurs incomplets, et état difficile
à diagnostiquer ou à réutiliser.

### Solution

[`CalibrationProblem.initialize`](../../pyages/calibration/problem.py) construit
le LPM, les traceurs et l'échantillonnage dans des variables locales. Les
attributs publics ne sont affectés qu'après le succès de toutes les étapes.
`is_prepared` est maintenant un état explicite, et un échec laisse le problème
non préparé.

## 4. Snapshot des observations

### Problème

Un `DataFrame` d'observations pouvait être modifié après la préparation. Le nom
des traceurs, la signature scientifique et les tableaux numériques risquaient
alors de décrire des cibles différentes.

### Solution

Le problème conserve un snapshot préparé. Les méthodes de calibration lisent
des tableaux détachés de ce snapshot. Toute mutation ultérieure du tableau
source est détectée par `ensure_prepared` et provoque une erreur explicite avant
le calcul.

## 5. Configuration stricte : erreur d'écriture ou changement algorithmique ?

Les ambiguïtés telles que `prior_option=1`, `burn_in=True`, une covariance non
carrée ou une chaîne sans aucun échantillon retenu sont des erreurs de
configuration, pas des variantes scientifiques utiles. Elles sont maintenant
refusées lors de la construction de `MHConfig`.

| Entrée | Avant | Maintenant |
|---|---|---|
| booléen écrit `0` ou `1` | pouvait être accepté comme booléen/nombre | erreur de type |
| covariance asymétrique ou non définie positive | échec possible plus tard | échec immédiat |
| prior empirique actif sans fichier | échec tardif | échec immédiat |
| paramètres initiaux non finis | échec variable | échec immédiat |
| configuration valide | exécution historique | même protocole numérique |

Le comportement algorithmique valide ne change donc pas. Les entrées invalides
échouent plus tôt et avec un message ciblé.

## 6. Intégrité des résultats

Les objets de résultat copient et figent leurs entrées mutables. Ils vérifient
désormais :

- l'ordre exact des paramètres initiaux et des colonnes échantillonnées;
- les taux, temps d'exécution, graines et matrices;
- le contenu des tables après le snapshot diagnostique;
- l'identité scientifique complète du template LPM entre chaînes, pas seulement
  ses noms de paramètres;
- la covariance, l'état fixe du modèle, les domaines, plages, unités et moments
  par des empreintes déterministes isolées dans
  [`_result_fingerprint.py`](../../pyages/calibration/methods/mh/_result_fingerprint.py).

Le pooling utilise une copie profonde du template. Modifier le résultat poolé
ne peut plus modifier rétrospectivement une chaîne archivée.

## 7. Tests et CI

### Vérifications locales

- `python -m ruff check .` : succès;
- `python -m pytest --cov=pyages --cov-report=term -q` :
  **1 456 réussis, 15 ignorés, 89 %**, en 843.46 s;
- quatre variantes de `test_calibration_mh_extensive` (`exp`, `ig`,
  `exp_shifted`, `ig_shifted`) ont été observées comme réussies;
- les deux workflows GitHub modifiés sont lisibles par le parseur YAML.

Les tests ajoutés couvrent directement : rejet sans mutation du LPM accepté,
commit d'une acceptation en mode prior seul, préparation atomique, mutation des
observations, séparation domaine/plage, support effectif du prior, configuration
ambiguë, cohérence des templates multi-chaînes, détachement du pooling et
contrats/fermeture des figures de trajectoire.

### Couverture des zones modifiées

| Module | Couverture de lignes |
|---|---:|
| `calibration/problem.py` | 100 % |
| `_sampler_target.py` | 97 % |
| `trajectory.py` | 94 % |
| `_result_fingerprint.py` | 93 % |
| `sampler.py` | 90 % |
| `prior.py` | 89 % |
| `lpm_params.py` | 85 % |
| `config.py` | 84 % |
| `results.py` | 83 % |

Tout n'est donc pas couvert. Les priorités de test restantes sont les branches
d'erreur de `_prior_support.py` (68 %), les chemins défensifs de
`ParameterManager` (75 %), certaines validations rares de `results.py`, et les
commandes CLI de gestion de stages. Les tests de liens/jonctions ignorés sous
Windows doivent continuer à être exécutés sur Linux dans le CI.

### Garde-fous CI

Le workflow extensif est maintenant déclenché sur les pull requests touchant la
calibration, les LPM, leurs schémas et données, la configuration, les workflows,
les exemples ou leurs tests. Une qualification scientifique extensive est aussi
une dépendance obligatoire de la porte `release-candidate-gate`. Une release ne
peut donc plus être validée uniquement par les tests rapides et les smoke tests
du paquet.

## 8. Organisation des fichiers

Les modules publics restent les façades d'accès. Après la simplification du
4 septembre, la transition et le stockage à consommateur unique sont lisibles
directement dans `sampler.py` :

```text
calibration/methods/mh/
├── sampler.py                 orchestration publique d'une chaîne
├── _sampler_target.py         évaluation sur le LPM candidat
├── prior.py                   façade et cycle de vie du prior
├── _prior_support.py          bornes et probabilités
├── _prior_parametric.py       normal/uniform et moments conditionnels
├── _prior_empirical.py        grilles empiriques
├── results.py                 objets publics et invariants relationnels
└── _result_fingerprint.py     empreintes d'intégrité

config/
├── models.py                  façade des modèles de configuration
├── _models_base.py            base, chemins, nombres non booléens
└── _models_cli.py             modèles CLI/check

workflows/runtime/
├── manifest.py                façade et orchestration de provenance
├── _manifest_types.py         handles et états immuables
└── _manifest_fs.py            accès fichiers stricts, liens et inventaires
```

Les imports publics existants ne changent pas. Cette organisation permet de
lire `sampler.py` comme un scénario, puis d'ouvrir uniquement le mécanisme
nécessaire.

## 9. Trajectoire MH

`MHTrajectory` refuse maintenant les capacités négatives ou booléennes, les
noms vides/dupliqués, les états non finis et les mises à jour de mauvaise
dimension. Le redimensionnement ne peut pas dépasser le nombre réellement
écrit. Les graphiques sont enregistrés explicitement en PNG et toutes les
figures sont fermées, y compris sans répertoire de sortie.

Ce changement ne modifie pas la chaîne. Il supprime des états de monitoring
ambigus et une fuite potentielle de figures Matplotlib.

## Complexité restante et justification

Ruff impose une complexité cyclomatique maximale de 10 et passe sur tout le
dépôt. La complexité locale des fonctions est donc bornée. La taille de certains
fichiers reflète toutefois encore un nombre élevé de contrats :

| Fichier | Lignes physiques | Couverture | Justification / décision |
|---|---:|---:|---|
| `sampler.py` | 561 | 86 % | orchestration séquentielle d'une chaîne; cible, transition et stockage ont été extraits |
| `prior.py` | 652 | 85 % | cycle de vie commun aux priors paramétriques et empiriques; calculs mathématiques extraits, initialisation encore candidate à une extraction |
| `ensemble.py` | 639 | 90 % | coordination pilote/production/diagnostics et indépendance des graines; complexité scientifique justifiée, à maintenir sans adaptation cachée |
| `results.py` | 924 | 78 % | quatre objets publics avec invariants croisés et qualification; empreintes extraites, validations rares encore à mieux tester |
| `lpm_params.py` | 652 | 82 % | schéma, compatibilité version 1, cache de contenu et vues utilitaires; séparation interne correcte mais un module de schéma dédié reste possible |
| `manifest.py` | 1 783 | 80 % | atomicité, sécurité contre liens/jonctions, CAS, verrous, rollback, quarantaine et provenance; types et accès fichiers extraits, point chaud restant |

La complexité de `manifest.py` est la plus justifiée par les garanties de
publication atomique et de sécurité multi-plateforme, mais sa taille n'est pas
considérée comme définitivement satisfaisante. Une prochaine modification
dédiée pourra extraire `_manifest_inspection.py` puis
`_manifest_promotion.py`. Elle devra conserver les tests de course, rollback,
liens et verrous comme critères d'acceptation; ce découpage n'a pas été mêlé aux
corrections scientifiques MH afin de limiter le risque.

## Bilan des changements de comportement

Les comportements volontairement modifiés sont :

1. un rejet MH ne laisse plus le LPM public sur le candidat rejeté;
2. une observation modifiée après préparation provoque une erreur;
3. un paramètre hors domaine mathématique est refusé plus tôt;
4. une configuration ambiguë ou invalide est refusée plus tôt;
5. les moments théoriques d'un prior sont ceux du support effectivement
   échantillonné;
6. un résultat poolé ne partage plus son template mutable avec une chaîne;
7. les figures de trajectoire sont toujours fermées.

Les plages de calibration distribuées, les formules LPM, la vraisemblance, la
règle d'acceptation, les graines par défaut et le protocole de tirages des
configurations valides n'ont pas été changés.

## Clôture du réaudit

Le passage final a rendu `calibration_range` canonique dans le code interne.
`ParameterManager` et `LpmBase` portent maintenant l'implémentation dans
`get_calibration_range()`, `get_calibration_ranges()`,
`get_calibration_range_width()` et les deux méthodes
`param_within_calibration_range*()`. Les anciens noms `bounds`, `get_bounds`,
`get_param_range`, `get_param_interval`, `get_p_min`, `get_p_max` et
`param_within_bounds*` délèguent vers ce contrat et restent compatibles sans
calendrier de suppression. Le nom de configuration stable `bounds_stratified`
est conservé, mais sa description utilise la notion exacte de plage de
calibration.

`LpmScipy` est explicitement abstraite par `_scipy_params()`, et le sampler
utilise le nom canonique `MHTrajectory.summary()` tout en conservant `check()`
comme alias historique. Les exemples Holten et Albuquerque déclarent désormais
séparément `domain` et `calibration_range`.

La clôture a été validée par 1 458 tests standards réussis et 15 ignorés, une
couverture de branches globale de 85,17 % pour un seuil CI de 75 %, Ruff, le
contrôle des docstrings qualifiées, l'inventaire généré, la construction Sphinx
HTML stricte et le contrôle des liens. Les neuf cas scientifiques extensifs
restent opt-in; les chemins modifiés déclenchent leur workflow sur pull request
et la qualification est également exigée par le workflow de release candidate.
