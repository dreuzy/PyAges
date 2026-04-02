# Brouillon Exemple Holten

Statut : document de cadrage uniquement.

Cette page definit le perimetre cible d'un futur exemple `Holten` a partir du
materiel actuellement present dans `examples/natural/holten/doc/`. A ce stade, aucun
code, aucun fichier YAML, aucun jeu de donnees converti et aucun test ne sont
crees.

Les reflexions plus transverses, notamment sur l'aide au choix automatique des
modeles de distribution, sont maintenues a part dans
`docs/dev/notes-choix-modele.md`.

Les points specifiques a l'helium pour Holten sont decrits dans
`docs/examples/holten/notes-helium.md`.

## Objectif

Construire un exemple au plus proche du cas d'etude propose dans les documents
associes a Visser et al. (2013), en s'appuyant prioritairement sur les
chroniques de traceurs fournies dans le dossier Holten lorsque celles-ci
existent.

Nom de travail recommande :

- `Holten 2010 benchmark multi-traceurs`

## Intention scientifique

L'objectif n'est pas de fabriquer un exemple abstrait a partir des capacites
generiques de PyAge, mais de reproduire au plus pres un cas d'etude documente,
avec :

- les donnees d'observation Holten,
- les chroniques de traceurs fournies avec ce cas d'etude,
- une comparaison explicite avec les resultats publies,
- une presentation pedagogique de la cible de calibration avant toute
  inversion.

## Pourquoi cet exemple est interessant

- Il apporte un benchmark ancre dans un jeu de donnees publie.
- Il peut mobiliser des traceurs deja presents dans le depot :
  `3H`, `kr85` et `39Ar`.
- Il permet de comparer les sorties PyAge a des resultats de reference issus de
  l'etude source.
- Il force a clarifier la question importante des chroniques locales de
  recharge par rapport au referentiel commun du depot.

## Materiel source deja present

Les fichiers suivants sont deja disponibles dans `examples/natural/holten/doc/` :

| Chemin | Contenu apparent | Role probable dans le futur exemple |
|--------|------------------|-------------------------------------|
| `sampling_data.txt` | Tableau principal des puits et des mesures de la campagne 2010 | Source principale des observations |
| `local_tritium.txt` | Chronique locale du tritium | Chronique de recharge candidate pour `3H` |
| `freiburg_krypton.txt` | Chronique atmospherique de `85Kr` | Chronique de recharge candidate pour `kr85` |
| `calibration_results.txt` | Resultats de calibration ou de comparaison issus de l'etude | Table de reference pour l'evaluation |
| `visser_data.xlsx` | Version tableur du jeu de donnees | Source de controle et d'audit |
| `Visser et al, 2013.pdf` | Article principal | Cadrage scientifique et cible de reproduction |
| `Dataset from Visser et al (2013).pptx` | Support de presentation | Contexte secondaire et interpretation |

## Ce que suggerent deja les fichiers

Une premiere lecture indique que :

- `sampling_data.txt` semble contenir 10 puits echantillonnes en avril 2010 ;
- les champs utiles comprennent au minimum :
  `Kr85_dpm_ccKr`, `3H_TU`, `3He_trit_TU`, `Ar39_pMC`, `He4_terr`, `He4`,
  des isotopes stables et plusieurs ages apparents ;
- `calibration_results.txt` semble resumer plusieurs familles de modeles de
  distribution et plusieurs ajustements par puits.

Holten est donc un bon candidat pour un exemple de benchmark, mais avec un
besoin fort de cadrage sur :

- les traceurs effectivement utilises en V1,
- la priorite donnee aux chroniques locales,
- le niveau de fidelite vise vis-a-vis de l'etude source.

## Principe directeur sur les chroniques de traceurs

Point important a conserver pour la suite :

- si une chronique specifique existe dans un dossier dedie a Holten, c'est
  elle qui doit etre utilisee en priorite ;
- la chronique du referentiel commun (`data_core/data_tracer/...`) ne doit etre
  utilisee qu'en repli, lorsqu'aucune chronique specifique n'existe pour le
  traceur considere ;
- ce comportement devra etre parametrable explicitement.

Formulation cible pour plus tard :

- mode `prefer_local` : utiliser la chronique Holten si elle existe, sinon la
  chronique commune ;
- mode `force_local` : n'utiliser que la chronique locale et signaler une
  erreur si elle manque ;
- mode `force_global` : ignorer les chroniques locales et utiliser le
  referentiel commun.

Ce point est central, car il conditionne la proximite de l'exemple avec le cas
scientifique d'origine.

Decision retenue a ce stade pour Holten :

- le comportement par defaut sera `prefer_local`.

## Portee recommandee pour une version 1

Pour une premiere implementation, le perimetre recommande est :

- une seule campagne d'echantillonnage : avril 2010 ;
- plusieurs puits, mais restreints en V1 a ceux qui disposent du triplet
  `3H` + `kr85` + `39Ar` dans `sampling_data.txt` ;
- priorite aux traceurs deja supportes dans le depot :
  `3H`, `kr85` et `39Ar` ;
- usage du mode `prefer_local` pour les chroniques de traceurs ;
- comparaison systematique avec les resultats de reference publies ;
- `3He_trit_TU`, `He4_terr`, `He4`, `DeltaNe_pct`, `delta2H` et `delta18O`
  gardes comme variables de contexte ou comme extensions futures.

Pourquoi ce choix :

- il reste proche du cas d'etude source ;
- il reutilise des briques traceurs deja presentes ;
- il reduit les ambiguities de cadrage pour une premiere version ;
- il fixe un comportement clair pour la gestion des chroniques de recharge ;
- il evite de melanger trop tot observations directes, ages apparents et
  corrections derivees ;
- il permet de documenter proprement les decisions de conversion et de
  parametrage.

Puits candidats identifies a ce stade dans `sampling_data.txt` :

- `59-05`
- `67-19`
- `72-22`
- `73-29`
- `85-33`
- `85-34`
- `85-35`

Decision retenue a ce stade pour le noyau V1 :

- retenir 3 puits pour la V1 ;
- privilegier un sous-ensemble de puits contrastes ;
- retenir preferentiellement une composition de type :
  `2 puits jeunes / peu profonds + 1 puits ancien / profond` ;
- ne pas se limiter aux cas les plus simples a lire.

Trio retenu a ce stade pour la V1 :

- `67-19` comme puits jeune, tres lisible et fortement contraint par les
  traceurs jeunes ;
- `72-22` comme second puits jeune/intermediaire, pour apporter plus de variete
  qu'un second cas trop proche de `67-19` ;
- `85-33` comme puits ancien/profond, avec un contraste net sur `3H`, `kr85`,
  `39Ar` et `He4_terr`.

Justification synthetique de ce choix :

- `67-19` et `72-22` evitent de dupliquer deux cas jeunes presque jumeaux ;
- `72-22` semble offrir un cas plus equilibre et pedagogique que `73-29` pour
  la comparaison multi-traceurs ;
- `85-33` est le puits profond le plus contraste et donc le plus utile pour une
  V1 demonstrative ;
- ce trio couvre mieux la transition entre composantes jeunes, intermediaires
  et anciennes qu'un choix plus redondant.

## Place de l'helium dans l'interpretation

L'article Holten n'utilise pas l'helium comme un bloc unique ; il distingue au
contraire des roles differents :

- `3He` tritiogenique, utilise avec `3H` pour construire un age apparent
  `3H/3He` et pour reconstruire un "tritium initial" ;
- `4He` radiogenique ou terrigene, interprete comme indicateur d'une composante
  plus ancienne, d'un melange, ou d'un apport externe ;
- l'ensemble des gaz nobles, utile aussi pour corriger ou interpreter les
  effets d'exces d'air et de degazage.

Decision retenue a ce stade :

- en V1, l'helium reste hors du socle principal de calibration ;
- il est conserve comme support d'interpretation et de validation scientifique ;
- un futur pretraitement specifique Holten est envisage.

Les details de cette perspective sont conserves dans
`docs/examples/holten/notes-helium.md`.

## Premiere analyse hors modele

Avant toute calibration, il serait utile d'ajouter une phase pedagogique de
visualisation "hors modele" du probleme.

Decision retenue a ce stade :

- la V1 visera une visualisation "riche" plutot qu'un affichage minimal.

Objectif :

- representer les chroniques de traceurs en regard des donnees mesurees pour
  chaque puits ou pour un sous-ensemble de puits ;
- montrer visuellement ou se situe la cible de calibration par rapport a
  l'histoire du traceur ;
- fournir une premiere lecture qualitative de la composante jeune, intermediaire
  ou ancienne du signal.

Cette premiere analyse pourrait inclure plus tard :

- la courbe temporelle de chaque chronique de recharge retenue ;
- la position des valeurs mesurees sur ces courbes ;
- une mise en regard simple des ages apparents fournis dans les tableaux ;
- une comparaison entre chronique locale et chronique commune lorsque les deux
  existent.

Forme recommandee pour la V1 :

- un graphe par traceur montrant la chronique retenue et les valeurs observees
  des puits ;
- un graphe par puits regroupant `3H`, `kr85` et `39Ar` pour donner une lecture
  synthetique de la cible multi-traceurs ;
- des figures suffisamment pedagogiques pour etre lues avant toute calibration.

Valeur attendue :

- meilleure lisibilite scientifique de l'exemple ;
- support pedagogique avant l'etape de calibration ;
- aide a comprendre pourquoi certains modeles de distribution seront plus ou
  moins plausibles.

## Forme cible de l'exemple

La forme la plus coherente pour une V1 serait :

- un exemple benchmark multi-traceurs centre sur la campagne 2010 ;
- une documentation scientifique commune ;
- une etape explicite de preparation des donnees ;
- une etape explicite de visualisation hors modele ;
- une calibration sur un sous-ensemble choisi de puits ;
- une comparaison avec les resultats publies.

Deux styles d'implementation sont envisageables plus tard :

1. Fichiers par puits :
   un fichier d'entree PyAge par puits, plus simple a verifier.
2. Traitement par lot :
   un pilote unique qui boucle sur plusieurs puits, plus pratique pour un
   benchmark global.

Choix recommande pour commencer :

- demarrer avec des fichiers par puits, puis ajouter un mode par lot si besoin.

## Proposition de structure future

Rien de ce qui suit n'est cree maintenant. Il s'agit seulement d'une structure
cible.

```text
docs/
  dev/
    notes-choix-modele.md
  examples/
    holten/
      README.md
      notes-helium.md
      notes-data-mapping.md
      notes-validation.md

examples/
  natural/
    holten/
      README.md
      run_holten.py
      holten.yaml
      tracers/
        3H/
          3H.yaml
        kr85/
          kr85.yaml
        39Ar/
          39Ar.yaml
      data/
        holten_2010_<well_id>.txt
      reference/
        sampling_data_raw.txt
        local_tritium_raw.txt
        freiburg_krypton_raw.txt
        calibration_results_reference.txt
```

## Questions scientifiques que l'exemple devra eclairer

1. PyAge peut-il reproduire une interpretation multi-traceurs coherente pour
   des puits Holten echantillonnes en 2010 ?
2. Dans quelle mesure les resultats obtenus sont-ils proches des resultats
   publies ?
3. Quel est l'impact du choix des chroniques locales par rapport aux chroniques
   communes du depot ?
4. Que gagne-t-on a visualiser les chroniques et les mesures avant de calibrer ?
5. Quelles parties de l'etude d'origine sont directement reproductibles avec
   l'etat actuel de PyAge, et lesquelles demandent un developpement
   complementaire ?

## Position retenue pour la validation V1

La validation V1 visera les deux niveaux suivants :

- une validation qualitative, pour verifier la coherence des tendances, des
  contrastes entre puits et des ordres de grandeur ;
- une validation semi-quantitative, avec des ecarts explicites rapportes puits
  par puits par rapport a `calibration_results.txt`.

Cette combinaison est preferable a un simple controle qualitatif, mais reste
plus prudente qu'un objectif de reproduction numerique stricte des resultats
publies.

## Position retenue sur la premiere famille de modeles

La premiere famille de modeles a cadrer pour Holten sera un modele discret en
bins, au plus proche de l'approche histogramme de l'article.

Implication directe :

- ce modele n'existe pas encore tel quel dans le socle actuel de PyAge ;
- il faudra donc le developper comme nouveau LPM.

Orientation recommandee pour la suite :

- viser un LPM generique de type histogramme discret a bins fixes ;
- conserver des fractions de bins comme variables calibrees ;
- utiliser d'abord une version proche du cas article, avant de chercher une
  generalisation plus ambitieuse.

Decision retenue a ce stade :

- prendre le `4-bin` comme premiere cible operationnelle ;
- garder des bins fixes au depart ;
- avancer progressivement, sans chercher tout de suite une generalisation
  `n-bin`.

Forme cible retenue pour cette premiere version du modele discret :

- bin 1 : `0-20 ans`
- bin 2 : `20-40 ans`
- bin 3 : `40-60 ans`
- composante 4 : fraction `old`, correspondant a `>60 ans`, plus proche de la
  logique de l'article qu'un quatrieme bin ferme de largeur fixe.

Pourquoi ce choix :

- c'est la forme la plus centrale dans l'article ;
- elle offre un bon compromis entre lisibilite, contraste et contrainte par les
  donnees ;
- elle cadre bien avec les trois puits retenus pour la V1 ;
- elle permet de developper un premier LPM discret utile sans ouvrir tout de
  suite le chantier d'un histogramme totalement generique.
- elle reste plus fidele a l'article, dans lequel le dernier compartiment joue
  un role de fraction ancienne ouverte plutot qu'un bin borne comme les trois
  premiers.

Lecture retenue de l'article a ce stade :

- oui, l'article travaille bien avec un nombre fixe de bins (`3`, `4`, `5`,
  `9`) ;
- oui, la largeur est constante pour les bins jeunes/intermediaires ;
- mais dans la logique Holten, le dernier compartiment du `4-bin` se lit mieux
  comme une fraction `old` ouverte `>60 ans` que comme un bin ferme ordinaire
  de largeur identique.

Lecture plus precise de la parametrisation de l'article :

- pour un modele a `n` bins, l'article utilise `n-1` parametres libres ;
- les `n-1` premiers bins ont une largeur constante `w` ;
- la derniere composante est determinee par fermeture et represente la fraction
  plus ancienne que la derniere borne ;
- autrement dit, l'article ne calibre pas `n` fractions independantes, mais
  seulement `n-1`, la derniere etant le reliquat.

Dans cette logique :

- `3-bin` : `2` parametres libres, avec coupures a `30` et `60` ans ;
- `4-bin` : `3` parametres libres, avec coupures a `20`, `40` et `60` ans ;
- `5-bin` : `4` parametres libres, avec pas de `15` ans jusqu'a `60` ans ;
- `9-bin` : `8` parametres libres, avec pas de `7.5` ans jusqu'a `60` ans,
  plus une contrainte de lissage supplementaire dans l'article.

Interpretation de structure pour PyAge :

- oui, le futur `4-bin` Holten derive bien d'une forme plus generique
  `n-bin` ;
- plus precisement, il derive d'une famille generique nommee a ce stade
  `n_bin_old`, avec :
  `n-1` bins jeunes/intermediaires de largeur constante, puis une composante
  finale `old` obtenue par fermeture ;
- le `4-bin` correspond alors au cas particulier `n = 4` avec coupures
  `20`, `40`, `60` ans ;
- la partie la moins generique n'est pas la structure en bins elle-meme, mais
  le traitement article-specifique de la composante `old` comme end-member par
  traceur.

Consequence pratique retenue pour PyAge :

- pour le futur `4-bin`, il faudra probablement utiliser une parametrisation
  transformee des `3` parametres libres ;
- l'objectif est de garantir automatiquement :
  `f1 >= 0`, `f2 >= 0`, `f3 >= 0`, `f_old >= 0`, et `f1 + f2 + f3 + f_old = 1` ;
- cela evitera d'appuyer l'implementation sur une calibration fragile sous
  contraintes manuelles.

Piste technique recommandee a ce stade :

- utiliser une transformation de type `stick-breaking` ou une transformation
  equivalente ;
- calibrer des variables libres internes, puis reconstruire les fractions
  physiques `f1`, `f2`, `f3`, `f_old` ;
- garder cette transformation comme detail d'implementation du futur LPM,
  sans l'exposer inutilement dans l'interface scientifique de l'exemple.

Formule illustrative possible :

```text
v1 = sigmoid(u1)
v2 = sigmoid(u2)
v3 = sigmoid(u3)

f1    = v1
f2    = (1 - v1) * v2
f3    = (1 - v1) * (1 - v2) * v3
f_old = (1 - v1) * (1 - v2) * (1 - v3)
```

Cette forme a l'avantage de garantir automatiquement :

- `0 <= f_i <= 1`
- `f1 + f2 + f3 + f_old = 1`

Elle est donnee ici comme exemple de transformation interne plausible, sans
verrouiller a ce stade l'implementation exacte.

Hypothese d'implementation recommandee dans PyAge :

- developper un premier modele specifique derive de la famille `n_bin_old` ;
- garder les bornes fixes `0-20`, `20-40`, `40-60`, puis une fraction `old` ;
- calibrer uniquement les fractions ;
- calculer les concentrations modelisees comme un melange d'end-members de
  bins, plutot qu'en cherchant d'emblee une distribution continue plus
  generale ;
- reserver a une etape ulterieure la generalisation vers un histogramme
  `n-bin` plus complet.

Le nom concret du premier LPM a implementer reste volontairement ouvert a ce
stade.

Decision retenue a ce stade :

- faire au plus proche de l'article pour la composante `old` ;
- traiter `old` comme un end-member specifique par traceur ;
- ne pas ramener `old` a une regle generique unique commune a tous les
  traceurs.

Implication pratique pour la suite :

- `3H`, `kr85` et `39Ar` pourront avoir chacun une definition propre de la
  composante `old` dans le futur modele Holten ;
- les valeurs ou regles associees a `old` devront etre documentees comme choix
  scientifiques lies a l'article, et non comme simple consequence numerique
  d'un bin `>60 ans`.
- si une valeur explicite est fournie dans l'article, elle devra etre stockee
  dans les fichiers de parametres locaux des traceurs du cas Holten, plutot
  qu'etre codee en dur dans le LPM.

Valeurs explicites deja identifiees dans l'article :

- `39Ar` : end-member de la fraction `old` estime a `45% modern`, soit `0.45`
  en fraction de moderne, correspondant a un age apparent d'environ `310 ans` ;
- `3H` : concentration premoderne initiale estimee a `3.0 +/- 0.4 TU`, utilisee
  dans l'article pour la precipitation anterieure a `1953` ;
- `kr85` : aucune valeur numerique explicite d'end-member `old` n'a ete reperee
  a ce stade dans l'article, mais la valeur la plus plausible pour Holten est
  `0` ou quasi nulle, a traiter comme hypothese inferee a partir du caractere
  premoderne de la fraction `old`, de la chronologie atmospherique du `85Kr`
  et de sa decroissance radioactive.

Consequence de cadrage :

- les valeurs article-specifiques devront etre portees plus tard dans des
  fichiers de parametres de traceurs specifiques a Holten ;
- les parametres globaux communs des traceurs ne devront pas etre modifies si
  la valeur ne vaut que pour ce cas d'etude.
- dans les futurs YAML locaux des traceurs, ces valeurs seront rangees dans une
  sous-section dediee `holten:`.

## Premier cadrage du traceur 39Ar

Le traceur `39Ar` est le premier candidat naturel pour verrouiller le mapping
des unites et des parametres article-specifiques, car l'article fournit une
valeur explicite pour la composante `old`.

Point retenu a ce stade :

- l'article exprime la composante `old` de `39Ar` en `45% modern` ;
- le traceur `39Ar` de PyAge est deja configure en `%modern` ;
- la traduction la plus directe pour Holten est donc :
  `old_endmember.value = 0.45` avec une unite logique `%modern`.

Implication pratique :

- il n'y a pas a ce stade de conversion conceptuelle complexe pour `39Ar` ;
- le point principal sera d'assurer la coherence entre la valeur lue dans les
  donnees, l'unite attendue par PyAge et l'end-member `old` specifique a
  Holten ;
- cette coherence devra etre documentee explicitement dans le futur fichier
  local `examples/natural/holten/tracers/39Ar/39Ar.yaml`.

## Premier constat sur les unites des traceurs

Les unites ne sont pas aujourd'hui homogenes entre les chroniques Holten, les
observations Holten et les configurations traceurs communes de PyAge.

Point important pour `kr85` :

- la chronique locale `examples/natural/holten/doc/freiburg_krypton.txt` est en
  `Bq/cbm air` ;
- les observations Holten dans `sampling_data.txt` sont en `dpm/ccKr` ;
- le traceur commun `data_core/data_tracer/kr85/kr85.yaml` est actuellement
  configure en `pptv`.

Conclusion de cadrage :

- non, la chronique locale `kr85` n'est pas dans la meme unite que les
  observations Holten ;
- non, elle n'est pas non plus dans l'unite actuellement configuree dans le
  traceur commun PyAge ;
- un travail explicite de conversion ou de reparametrage local du traceur sera
  necessaire avant toute implementation fiable.

Point de comparaison utile :

- `3H` est dans une situation plus simple, car la chronique locale et les
  observations Holten sont toutes deux exprimees en `TU` ;
- `39Ar` est conceptuellement plus proche aussi, car l'observation Holten est
  donnee en `pMC` alors que PyAge attend `%modern`, ce qui semble beaucoup plus
  facile a aligner que le cas `kr85`.

Structure cible minimale recommandee pour cette sous-section :

```yaml
holten:
  reference: "Visser et al. (2013)"
  notes: "Parametres specifiques au cas Holten"
  old_endmember:
    value: 0.45
    unit: "%modern"
    meaning: "old fraction end-member"
  premodern_input:
    value: 3.0
    unit: "TU"
    uncertainty: 0.4
    meaning: "premodern initial concentration"
```

Principes associes :

- seules les cles pertinentes pour un traceur donne devront etre renseignees ;
- un traceur peut n'utiliser que `old_endmember` ou seulement
  `premodern_input` ;
- une cle absente signifiera qu'aucune valeur explicite n'a ete retenue a ce
  stade pour ce traceur.
- la sous-section `holten:` devra rester simple et ne pas introduire a ce stade
  de champ supplementaire du type `source_type`.

## Travaux de preparation a prevoir plus tard

La future implementation devra probablement traiter les points suivants :

- selection des premiers puits cibles ;
- normalisation des identifiants de puits et des dates ;
- conversion des unites sources vers les unites attendues par les configurations
  de traceurs ;
- definition explicite du mode `prefer_local` et des cas de repli ;
- transformation de la table source en fichiers d'observation PyAge ;
- tracabilite de chaque valeur convertie vers sa source d'origine ;
- definition des figures de premiere lecture hors modele, a la fois par
  traceur et par puits.

## Questions techniques ouvertes

- Comment parametrer proprement le futur LPM discret en bins dans PyAge ?
- Comment representer numeriquement la composante `old` dans le premier modele
  `4-bin`, en restant fidele a sa logique d'end-member specifique par traceur ?
- Comment mapper `Kr85_dpm_ccKr` vers l'unite attendue par la configuration
  actuelle de `kr85` ?
- Comment mapper `Ar39_pMC` vers la configuration actuelle de `39Ar`, exprimee
  en `%modern` ?
- Comment cadrer plus tard un pretraitement specifique pour `3He_trit_TU`,
  `He4_terr` et les corrections associees ?
- Quels ecarts semiquantitatifs faudra-t-il rapporter prioritairement par puits
  par rapport a `calibration_results.txt` ?
- Faut-il montrer des comparaisons locale vs globale dans certaines figures,
  meme si le mode par defaut reste `prefer_local` ?

## Premier jalon recommande

Le premier jalon d'implementation devrait rester etroit :

- choisir 3 puits contrastes ;
- utiliser `3H`, `kr85` et `39Ar` ;
- documenter explicitement les conversions d'unites ;
- rendre explicite la strategie `prefer_local` de selection des chroniques ;
- produire une premiere visualisation hors modele riche des chroniques et des
  mesures, par traceur et par puits ;
- lancer une calibration sur un premier modele discret en bins clairement
  choisi ;
- comparer les sorties a la table de reference publiee, de maniere qualitative
  et semi-quantitative.

## Criteres d'acceptation du futur exemple

L'exemple pourra etre considere comme pret lorsque :

- la provenance de chaque jeu de donnees est documentee ;
- au moins un puits Holten pourra etre traite de bout en bout avec le code du
  depot ;
- la strategie de selection des chroniques sera explicite et parametrable ;
- l'exemple inclura une visualisation pedagogique avant calibration ;
- les sorties comprendront une comparaison aux resultats publies ;
- l'ecart entre observations supportees et observations differees sera clairement
  explique.

## Prochaines enrichissements utiles de ce document

Les prochains ajouts utiles seraient :

- confirmer le nom final de l'exemple ;
- choisir les premiers puits cibles parmi les puits disposant du triplet
  `3H` + `kr85` + `39Ar` ;
- expliciter pourquoi le trio retenu represente bien le contraste
  `jeune/jeune/ancien` ;
- justifier le caractere contraste du sous-ensemble retenu ;
- fixer le jeu de traceurs V1 ;
- preciser la forme cible du premier modele discret en bins ;
- preciser le statut exact du bin `old` dans le `4-bin` initial ;
- decrire le format cible des donnees converties ;
- lister les sorties et figures attendues pour la visualisation riche ;
- preciser les details operationnels du mode `prefer_local` ;
- ajouter une section de validation par rapport a l'article, a la fois
  qualitative et semi-quantitative.

## Mode de travail pour la suite

La suite de ce document peut etre construite par echanges successifs, en
fixant progressivement les choix qui demandent une decision scientifique ou
pratique.

Ordre logique recommande pour ces echanges :

1. choisir le perimetre exact des puits de la V1 ;
2. confirmer le jeu de traceurs effectivement utilise ;
3. definir la visualisation hors modele a produire ;
4. cadrer la comparaison aux resultats publies ;
5. revenir ensuite, si utile, sur les extensions futures autour de l'helium.

Tant que ces points ne sont pas stabilises, il vaut mieux garder le document au
niveau cadrage et ne pas figer de structure d'implementation trop precise.

## Notes

- Le depot contient deja des traceurs `3H`, `kr85` et `39Ar`.
- Ce brouillon ne decide pas encore des details d'implementation.
- Ce brouillon n'ajoute ni script, ni configuration, ni donnees converties.
