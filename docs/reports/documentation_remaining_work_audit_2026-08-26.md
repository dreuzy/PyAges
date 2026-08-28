# Audit approfondi de la documentation et reste à faire

> **Mise à jour d'état au 27 août 2026.** Ce rapport est conservé comme trace
> datée. Les constats « campagne fraîche absente » et « paquet article absent »
> ont été dépassés. Voir {doc}`reproduction_campaign_status_2026-08-27` : les
> contrôles historiques restent à 0/6, mais la campagne fraîche du noyau
> stabilisé valide ses 8/8 étapes, son paquet et son archive locale.

**Date de l'audit :** 26 août 2026
**Dépôt audité :** commit `17b38579a616f899944441f73d52f9780655648a`
avec arbre de travail non propre
**Manuscrit de référence :** `PyAges_v1.0_revised_v14.docx`, 2 099 504
octets, SHA-256
`5e4eca7fc2ec32fe92f86940d5e5a0900f18ac359baf4656c6201a33dc864711`

> **Mise à jour après audit.** Le premier lot de robustesse, provenance et
> documentation a été figé et poussé au commit `9c244ac`. La numérotation
> Table 3/Table 4, le contrat d'archive et les tests de dérive documentaire ont
> ensuite été corrigés. Les lacunes d'archives numériques décrites ci-dessous
> restent inchangées.

## Conclusion exécutive

La documentation scientifique générale est maintenant **assez approfondie**.
Il n'est pas utile de recopier davantage l'introduction, la discussion ou les
résultats narratifs de l'article. Les informations nécessaires à une
implémentation et à une interprétation indépendantes sont présentes : équation
forward, fenêtre finie et masse non renormalisée, CDF et premier moment
partiel, tolérances, conventions des LPM, unités, vraisemblance, objectifs,
priors, règle de Metropolis--Hastings, rétention et diagnostics.

Le principal reste à faire n'est donc plus d'augmenter le volume de prose. Il
faut **rendre les affirmations auditables depuis une archive immuable**. Dans
le checkout courant, les six commandes de contrôle des cas d'article échouent,
y compris les cas marqués `final`. Les rapports historiques indiquent que les
campagnes ont réussi, mais les chaînes, plusieurs manifestes, Supplement S2 et
le paquet article annoncé ne sont pas disponibles ici. Une figure seule ne
permet pas de recalculer un diagnostic ou de vérifier une valeur du manuscrit.

Le cas Dirichlet est considéré comme **calculé dans un autre chantier**, selon
l'information du mainteneur. Il ne faut pas le relancer automatiquement. Son
reste à faire est l'import, le contrôle et le gel de ses preuves dans la même
archive que les autres cas.

## Périmètre et méthode

L'audit a comparé :

- les méthodes, résultats et disponibilités annoncés dans la révision v14 ;
- les pages scientifiques, le guide utilisateur, l'API et les rapports Sphinx ;
- le registre `article/cases.yaml`, les six manifestes de cas et les résultats
  réellement présents sous `results/` ;
- les scripts qui génèrent Table 4 et le paquet article ;
- la version, les tags Git, `CITATION.cff` et le processus de publication ;
- les tests, le lint, le formatage, la construction .NET et les commandes CLI.

Le contrôle `scripts.article.run_case check` ne lance aucun calcul scientifique. Il
compare seulement les chemins et empreintes annoncés avec le checkout courant.
Un échec peut donc signifier une preuve absente ou un code ayant évolué ; il ne
signifie pas à lui seul qu'un ancien résultat scientifique est faux.

## État des preuves par cas

| Cas | Statut du registre | Contrôle local du 26 août | Preuve présente | Reste à faire |
| --- | --- | --- | --- | --- |
| `s3_forward_verification` | `final` | échec : empreinte de `supplement_s1.md` différente | nouveau run S1 complet au commit `17b3857`, 133 lignes par niveau de tolérance, invariants et performances | enregistrer ce run comme nouvelle preuve sans réécrire l'ancien manifeste ; mettre à jour le pointeur et l'empreinte du cas |
| `s3_1_tracerlpm` | `partial` | échec : Supplement S2 et manifeste de lancement absents, script modifié | configurations, références compactes, tests Python et adaptateur .NET | importer Supplement S2, exports TracerLPM/Excel, manifeste de lancement, versions et empreintes ; conserver le statut portable `partial` si Excel reste nécessaire |
| `s3_2_shifted_exponential` | `final` | échec : chaînes, pilotes et manifeste historique absents ; script modifié | rapport versionné résumant 19/19 cas | restaurer ou archiver les 95 chaînes, pilotes, diagnostics, résumés, Table 4 et environnement, puis vérifier les empreintes |
| `s4_1_holten` | `final` | échec : chaînes, pilotes et manifeste historique absents ; script modifié | rapport versionné résumant 7/7 puits | restaurer ou archiver les chaînes, diagnostics, comparaisons Visser, résidus, manifestes et environnement |
| `s4_2_ploemeur` | `final` | échec : chaînes, audit de données et manifeste historique absents ; script modifié | Figure 4 en PDF, PNG et TIFF seulement | importer chaînes, audit de données, prédictions ligne par ligne, diagnostics, résumés et manifeste ; vérifier que la figure présente en dérive exactement |
| `holten_prior_dirichlet1` | `unvalidated` | échec : chaînes, pilotes et manifeste historique absents ; script modifié | aucune preuve locale ; campagne déclarée terminée ailleurs | importer le paquet externe, vérifier convergence, écarts de posterior et résidus, puis seulement passer le statut à `final` ou `qualified` |

Tous les résultats sont ignorés par Git via `results/`. C'est acceptable pour
des sorties volumineuses, mais seulement si une archive externe identifiée,
immuable et vérifiable transporte effectivement les fichiers requis. Aucune
archive de ce type n'a été trouvée dans le checkout ou dans les emplacements
locaux d'archive examinés.

La commande
`python -m scripts.release.build_article_package --validate-only results/article_package`
échoue actuellement car
`results/article_package/provenance/article_package_manifest.json` est absent,
alors que le rapport de campagne annonce un paquet de 67 artefacts.

## Concordance entre le manuscrit v14 et les preuves

### Opérateur forward

Les valeurs de la révision v14 sont retrouvées dans le nouveau Supplement S1 :

- 133 comparaisons indépendantes au réglage par défaut ;
- 95e percentile de l'erreur relative :
  `3.595558353699866e-05` ;
- erreur relative maximale : `1.413462328021509e-04` ;
- matrices de sensibilité à `0.5x`, `1x` et `2x` et invariants analytiques
  présents.

Cette partie est scientifiquement vérifiable localement. Son seul blocage de
traçabilité est que le manifeste de cas pointe vers un ancien commit et une
ancienne empreinte, tandis que le run présent a son propre manifeste propre au
commit `17b3857`.

Le temps total de la matrice `2x` vaut toutefois environ 6 145 s, contre 60 s
au réglage par défaut, alors même que le nombre médian de bins diminue. Le
rapport précise que la machine était fortement chargée. Les erreurs et nombres
de bins démontrent bien le compromis précision--résolution ; ces temps muraux
ne démontrent pas un compromis précision--temps. Avant de publier une
affirmation de performance, il faut soit répéter le benchmark sur une machine
isolée, soit retirer les temps contaminés et définir explicitement le coût par
le nombre de bins ou d'évaluations.

### Comparaison TracerLPM

Le manuscrit affirme que les résultats appariés, mappings, bornes, seeds,
versions et objectifs natifs sont conservés dans Supplement S2. Ce supplément
et les sorties Excel ne sont pas présents. Les 55 tests de l'adaptateur Python
passent et le projet .NET compile, mais cela ne remplace pas l'exécution
qualifiée de TracerLPM dans Excel. Cette preuve est un verrou de soumission si
Table 3 reste dans l'article.

### Campagnes MCMC

Le rapport historique contient les nombres attendus pour les 19 cas shifted
exponential, les 7 puits Holten et les 4 calibrations Ploemeur. Les scripts
courants calculent maintenant split-$\hat R$, ESS et l'erreur Monte Carlo sur
la moyenne (`mcse_mean`). Les sorties historiques correspondantes ne sont pas
présentes dans ce checkout, donc les nombres du manuscrit ne peuvent pas être
recalculés ici.

La révision v14 donne un bon niveau de synthèse, notamment le nombre de chaînes,
les itérations, le burn-in, split-$\hat R$ et ESS pour le benchmark shifted
exponential. L'archive ou le supplément doit encore fournir, pour chaque cas :

- le nombre exact d'états retenus par chaîne, y compris les répétitions après
  rejet ;
- la configuration de proposal réellement utilisée et les éventuelles
  extensions de chaîne ;
- split-$\hat R$, ESS et MCSE pour chaque paramètre et quantité dérivée ;
- les identifiants de chaîne, états initiaux, seeds et taux d'acceptation ;
- les résidus observation par observation et les échantillons joints utilisés
  pour les intervalles et figures.

Des résumés marginaux seuls ne suffisent pas : ils ne permettent ni de
recalculer les diagnostics multi-chaînes, ni de préserver la dépendance entre
paramètres.

### Sensibilité Dirichlet

Le paragraphe Holten de la révision v14 conclut à de faibles déplacements du
posterior et à des résidus essentiellement inchangés sous un prior
Dirichlet(1,1,1,1). Puisque le calcul a été fait ailleurs, l'action requise est
de copier ou référencer son paquet immuable et de vérifier quantitativement :

- les mêmes données, transformations et vraisemblance que le cas canonique ;
- la densité Dirichlet dans les coordonnées physiques et le Jacobien de la
  transformation utilisée par le sampler ;
- les critères multi-chaînes pour les quatre fractions ou les trois degrés de
  liberté indépendants ;
- les déplacements des médianes et intervalles, ainsi que les écarts de
  résidus, selon des seuils annoncés avant la conclusion.

Tant que cette intégration n'est pas faite, le statut local `unvalidated` est
correct même si le calcul externe est terminé.

## Incohérences de numérotation et de génération

La révision v14 définit sans ambiguïté :

- **Table 3** : comparaison PyAges--TracerLPM ;
- **Table 4** : 19 cas shifted exponential.

Le registre et les pages scientifiques utilisent cette numérotation. Après
l'audit, le générateur de production et le constructeur du paquet article ont
été corrigés : titre, descriptions, README, `scope`, identifiants et
destinations destinés au lecteur disent désormais **Table 4**. Les fichiers
sources historiques `table3_final.*` restent inchangés pour la provenance. Un
test automatique interdit la réapparition de « Table 3 » dans les sorties de
production courantes.

Les scripts plus anciens d'exploration ou de qualification peuvent conserver
leur numérotation historique à condition d'être clairement marqués comme tels
et exclus du paquet éditorial courant.

## Documentation utilisateur

L'audit a trouvé et corrigé les dérives suivantes :

- `dirac` était documenté avec `tau` au lieu de `mu` ;
- Gamma était documentée avec `mu, sigma` au lieu de `k, scale` ;
- Uniform était documentée avec `a, b` au lieu de `tmin, delta` ;
- quatre modèles enregistrés manquaient à la liste statique ;
- les défauts de `run`, `verbose`, `lpm_number`, `seed_enabled` et des figures
  temporelles ne correspondaient pas aux modèles Pydantic ;
- le rôle de `lpm_number`, de `monitor` et du nombre d'itérations MCMC était
  présenté de manière trop forte ;
- la règle de résolution des chemins et le nom du dossier de résultat
  single-date étaient inexacts ;
- le préavis de provenance des données n'était pas accessible dans le site
  Sphinx.

La correction durable consiste à tester les exemples YAML de la documentation
contre les modèles Pydantic et à comparer automatiquement la table des LPM au
registre. Une génération complète de la page à partir du schéma serait
possible, mais un test de dérive est préférable si l'on veut conserver des
explications éditoriales lisibles.

L'inventaire AST courant trouve 453 définitions publiques documentées sur 464,
174 docstrings de moins de huit mots et 11 omissions apparentes. Les 11
omissions sont des accesseurs, callbacks ou helpers locaux ; aucune ne définit
une équation, une unité, un prior, une tolérance ou une convention de résultat.
Atteindre artificiellement 100 % n'est donc pas une priorité scientifique.

## Version, tag et citation

L'identité de paquet est cohérente entre le code, les métadonnées et
`CITATION.cff` : `0.1.0b1`, statut beta. Aucun DOI fictif n'est présent.

Le dépôt contenait alors un tag historique `1.0`, objet Git `de835be`, daté du
17 janvier 2026 et visant le commit `5af69268`, avec le message « VERSION AVANT
REFACTORING COMPLET ». Il est ancêtre du code courant et ne correspond ni à la
beta `0.1.0b1`, ni au futur artefact stable visé par le manuscrit. Avant
publication, il faut décider et appliquer une seule identité stable,
recommandée ici comme `v1.0.0`, puis faire correspondre exactement le tag, le
paquet, l'archive, le DOI, `CITATION.cff` et le texte de disponibilité.

> **Mise à jour du 27 août 2026 :** ce tag ambigu a été supprimé. Son ancienne
> cible reste traçable par le commit
> `5af69268da4ed1e22cc5307eac8d6f46522f8ade`. Le nom `v1.0.0` reste réservé à
> la future publication stable.

## Contrôles techniques

| Contrôle | Résultat observé |
| --- | --- |
| suite Python standard | 594 passed, 5 skipped |
| tests de l'adaptateur TracerLPM | 55 passed |
| construction .NET x64 | réussite, 0 avertissement, 0 erreur |
| contrôle CLI par `python -m pyages.cli.main` | 10/10 contrôles, 12 LPM, 13 traceurs, version `0.1.0b1` |
| commande console `pyages` dans l'environnement courant | absente du `PATH`; elle devra être testée depuis la roue installée |
| HTML Sphinx strict (`-E -a -W --keep-going`) | réussite, 66 sources, sortie `docs/_build/deep-doc-audit-20260826/` |
| liens Sphinx stricts | réussite après contrôle de tous les liens ; quatre DOI Wiley valides sont exclus URL par URL pour réponse robot 403, cinq redirections valides sont consignées |
| `ruff check` | réussite après correction des changements audités |
| `ruff format --check` | réussite, 296 fichiers conformes |
| contrôles des cas article | 0/6 réussis dans ce checkout |
| validation du paquet article | échec : manifeste du paquet absent |

La réussite de la suite de tests est rassurante pour le code courant. Elle ne
compense pas l'absence des preuves de calcul. Le lint et le formatage sont
maintenant au vert, mais devront être rejoués au gate de publication.

Ces contrôles ont utilisé l'environnement déjà actif, notamment Python 3.12.4,
NumPy 2.1.2, SciPy 1.14.1, pandas 2.2.3 et Sphinx 7.4.7. Il ne correspond pas au
jeu de versions directes actuellement qualifié dans `install/constraints.txt`.
Le gate final doit donc être répété dans un environnement neuf installé avec
ces contraintes ; le succès local ne doit pas être présenté comme le test de
la matrice de dépendances de publication.

## Plan d'action priorisé

### P0 — avant soumission ou archive scientifique

1. **Créer un espace de gel propre.** Partir d'un commit revu sans modification
   locale, arrêter les producteurs de résultats, enregistrer environnement et
   dépendances, puis ne plus modifier les scripts de calcul de ce gel.
2. **Assembler les preuves des six cas.** Importer les sorties historiques ou
   externes, notamment Dirichlet et Supplement S2, et exécuter
   `scripts.article.run_case check` jusqu'à six succès. Ne jamais remplacer une
   ancienne empreinte pour masquer une évolution : créer un nouveau manifeste
   de run relié à l'ancien.
3. **Terminé après audit — corriger Table 3/Table 4 dans les générateurs.** Les
   noms de fichiers sources historiques sont conservés, tandis que le rapport,
   le README, le manifeste et le paquet final exposent Table 4.
4. **Reconstruire le paquet article.** Inclure les sorties permettant de
   recalculer figures, tables, résidus et diagnostics. Si les chaînes brutes
   sont stockées séparément, le paquet doit contenir leur URI immuable, taille,
   SHA-256 et manifeste de structure.
5. **Relier le manuscrit au gel exact.** Mettre à jour le texte de disponibilité
   seulement après validation du tag, de l'archive et de leurs métadonnées.

### P1 — qualification scientifique et éditoriale

6. Rattacher le nouveau Supplement S1 au registre et refaire les mesures de
   performance sur machine isolée, ou limiter les conclusions aux erreurs et
   nombres de bins.
7. Ajouter aux suppléments les tables complètes de chaînes, proposals,
   rétention, split-$\hat R$, ESS, MCSE et résidus ; conserver dans le texte
   principal la synthèse déjà lisible.
8. **Terminé après audit.** Des tests couvrent maintenant les numéros de
   tables, le registre des LPM, la validité des exemples YAML et la concordance
   des tables de valeurs par défaut avec les modèles Pydantic. Ils ont notamment
   détecté puis corrigé le défaut documenté de `calibration.seed`, qui vaut
   `null` tant qu'aucune seed explicite n'est configurée.
9. `ruff check` et `ruff format --check` sont au vert. Il reste à exécuter la
   couverture, la suite `--run-extensive`, la construction des distributions et
   le smoke test de la roue sur les versions Python supportées.

### P2 — améliorations non bloquantes

10. Ajouter des docstrings aux 11 helpers seulement lorsqu'elles apportent une
    information de contrat ; ne pas viser un score mécanique de 100 %.
11. Harmoniser progressivement la langue des pages et raccourcir les rapports
    historiques très longs, sans supprimer leur valeur de provenance.

## Ce qu'il ne faut pas faire

- Ne pas copier l'article entier dans la documentation scientifique.
- Ne pas relancer Dirichlet si son paquet externe complet et vérifiable existe.
- Ne pas appeler `final` un cas uniquement parce qu'un rapport narratif indique
  qu'il a convergé ; distinguer résultat scientifique, preuve locale et
  portabilité de la reproduction.
- Ne pas renommer rétroactivement des artefacts historiques sans table de
  correspondance et empreintes.
- Ne pas recréer le tag historique `1.0`; réserver `v1.0.0` à l'artefact stable
  effectivement qualifié.

## Critère de clôture recommandé

La documentation et la couche article seront prêtes à auditer lorsque, depuis
un checkout propre de l'artefact candidat :

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m pytest -q validation/tracerlpm/benchmark/tests
python -m pytest -q --run-extensive
python -m scripts.article.run_case check s3_forward_verification
python -m scripts.article.run_case check s3_1_tracerlpm
python -m scripts.article.run_case check s3_2_shifted_exponential
python -m scripts.article.run_case check s4_1_holten
python -m scripts.article.run_case check s4_2_ploemeur
python -m scripts.article.run_case check holten_prior_dirichlet1
python -m scripts.release.build_article_package --validate-only results/article_package
python -m sphinx -E -a -W --keep-going -b html docs docs/_build/html
python -m sphinx -E -a -W --keep-going -b linkcheck docs docs/_build/linkcheck
```

À ce stade, le travail scientifique restant dans la documentation sera
principalement de maintenance. Le verrou actuel est l'intégration vérifiable
des preuves de calcul et leur correspondance exacte avec le manuscrit v14.
