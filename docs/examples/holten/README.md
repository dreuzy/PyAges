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

Lecture synthetique de l'article de reference :

- l'etude s'interesse a des puits de production de l'aquifere glaciofluvial de
  Holten, echantillonnes en avril 2010 ;
- il s'agit plus precisement d'un champ captant d'eau potable, pour lequel la
  question centrale est la vulnerabilite des puits vis-a-vis de contaminations
  recentes ;
- ces puits captent des intervalles assez epais, de sorte que l'eau pompee est
  interpretee comme un melange de composantes d'ages differents plutot que
  comme une eau d'age unique ;
- l'article mobilise surtout `3H/3He`, `85Kr`, `39Ar` et `4He` pour separer les
  composantes jeunes, intermediaires et anciennes ;
- il compare ensuite plusieurs familles de modeles de distribution des ages,
  dont des modeles discrets en bins fixes, afin de retrouver des melanges
  compatibles avec les traceurs observes ;
- l'ajustement publie montre qu'un modele discret `4-bin` et un modele de
  dispersion avec fraction ancienne reproduisent bien les donnees ;
- l'article distingue aussi un contraste fort entre puits peu profonds et puits
  plus profonds : les puits superficiels pompent majoritairement de l'eau de
  moins de 20 ans, alors que les puits profonds comportent une fraction
  ancienne importante, superieure a 60 ans ;
- des mesures `3H/3He` sur des piezometres a crepine courte autour du champ
  captant servent enfin a contraindre la stratification verticale des ages dans
  l'aquifere ;
- pour PyAge, l'interet majeur du cas Holten est donc de disposer a la fois
  d'observations publiees, de chroniques de traceurs, et d'une cible de
  calibration explicitement discutee dans l'article.

Dit autrement, le cas Holten n'est pas seulement un exemple multi-traceurs. Il
relie directement trois niveaux de lecture que l'on veut conserver dans
l'exemple PyAge : la lecture des chroniques de recharge, l'interpretation des
melanges d'ages dans des puits de production reels, et la discussion article
des familles de modeles capables ou non de reproduire ces melanges.

## Pourquoi cet exemple est interessant

- Il apporte un benchmark ancre dans un jeu de donnees publie.
- Il peut mobiliser des traceurs deja presents dans le depot :
  `3H`, `kr85` et `39Ar`.
- Il permet de comparer les sorties PyAge a des resultats de reference issus de
  l'etude source.
- Il force a cadrer un jeu de traceurs et de chroniques entierement specifique
  a Holten, au plus proche de l'article.

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

- `sampling_data.txt` semble contenir 11 puits echantillonnes en avril 2010 ;
- les champs utiles comprennent au minimum :
  `Kr85_dpm_ccKr`, `3H_TU`, `3He_trit_TU`, `Ar39_pMC`, `He4_terr`, `He4`,
  des isotopes stables et plusieurs ages apparents ;
- `calibration_results.txt` semble resumer plusieurs familles de modeles de
  distribution et plusieurs ajustements par puits.

Holten est donc un bon candidat pour un exemple de benchmark, mais avec un
besoin fort de cadrage sur :

- les traceurs effectivement utilises en V1,
- le caractere entierement specifique des chroniques et des parametrages
  traceurs,
- le niveau de fidelite vise vis-a-vis de l'etude source.

## Principe directeur sur les chroniques et parametres traceurs

Point important a conserver pour la suite :

- pour Holten, les chroniques de recharge, les conventions d'unites et les
  parametres de traceurs doivent etre definis dans un espace propre a Holten ;
- l'exemple ne doit pas heriter des chroniques ou des YAML traceurs generiques
  du depot ;
- l'exemple ne doit pas chercher a fusionner un traceur Holten avec un traceur
  generique ;
- si un traceur n'a pas de definition locale suffisante pour etre exploite
  proprement, l'exemple doit le signaler comme manquant plutot que de basculer
  vers un repli implicite.

Formulation cible pour plus tard :

- strategie `holten_only` : n'utiliser que les donnees, chroniques et
  parametrages definis localement pour Holten ;
- toute absence de source locale necessaire doit produire une erreur de
  preparation ou conduire a sortir le traceur du perimetre V1.

Ce point est central, car il conditionne la proximite de l'exemple avec le cas
scientifique d'origine.

Decision retenue a ce stade pour Holten :

- la strategie de reference sera `holten_only`.

## Portee recommandee pour une version 1

Pour une premiere implementation, le perimetre recommande est :

- une seule campagne d'echantillonnage : avril 2010 ;
- plusieurs puits, mais restreints en V1 a ceux qui disposent du triplet
  `3H` + `kr85` + `39Ar` dans `sampling_data.txt` ;
- priorite aux traceurs deja supportes dans le depot :
  `3H`, `kr85` et `39Ar` ;
- usage exclusif de chroniques et parametrages de traceurs propres a Holten ;
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
- une explication de ce qui est strictement repris de l'article et de ce qui
  est adapte pour l'execution PyAge.

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
- une documentation scientifique dediee a Holten ;
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

- garder les fichiers par puits comme format canonique d'entree PyAge ;
- prevoir en plus un fichier agrege simple pour piloter un traitement par lot
  des puits retenus, sans remplacer les fichiers unitaires.

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
      exemple_holten.ipynb
      run_holten.py
      holten.yaml
      data_lpm/
        <future_holten_4bin_name>/
          params.yaml
      tracers/
        3H/
          3H.yaml
        kr85/
          kr85.yaml
        39Ar/
          39Ar.yaml
      data/
        holten_2010_<well_id>.txt
        holten_2010_selected_wells.txt
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
3. Jusqu'ou une definition entierement specifique des traceurs Holten aide-t-elle
   a rester coherent avec l'article ?
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
- ces valeurs ne devront pas etre reportées dans les parametrages generiques du
  depot ;
- dans les futurs YAML locaux des traceurs, ces valeurs seront rangees dans une
  sous-section dediee `holten:`.

## Premier cadrage du traceur 39Ar

Le traceur `39Ar` est le premier candidat naturel pour verrouiller le mapping
des unites et des parametres article-specifiques, car l'article fournit une
valeur explicite pour la composante `old`.

Point retenu a ce stade :

- l'article exprime la composante `old` de `39Ar` en `45% modern` ;
- la convention d'execution visee dans PyAge pour `39Ar` est `%modern` ;
- la traduction la plus directe pour Holten est donc :
  `old_endmember.value = 0.45`, soit `45% modern` dans la convention
  numerique interne deja utilisee par PyAge.

Implication pratique :

- le cas `39Ar` est plus simple que `kr85`, mais il faut tout de meme lever une
  ambiguite de convention numerique ;
- dans `sampling_data.txt`, l'observation est notee `Ar39_pMC` et prend des
  valeurs du type `104`, `93`, `51` ;
- dans l'etat actuel de PyAge, la recharge moderne de reference est manipulee
  comme `1` et non `100`.

Position retenue a ce stade pour Holten :

- conserver la convention numerique deja utilisee par PyAge pour `39Ar` ;
- lire les valeurs Holten `Ar39_pMC` comme des pourcentages modernes
  experimentaux ;
- convertir directement a l'entree ces valeurs vers la convention interne de
  PyAge par division par `100` ;
- garder l'unite textuelle `%modern` pour rester coherent avec l'execution
  actuelle de PyAge, meme si numeriquement il s'agit d'une fraction de moderne
  comprise en pratique entre `0` et `1`.

Formule pratique :

```text
Ar39_pyage[%modern] = Ar39_pMC / 100
```

Exemples Holten :

```text
104 pMC -> 1.04
 93 pMC -> 0.93
 51 pMC -> 0.51
```

Consequence operationnelle :

- oui, la conversion `39Ar` pourra elle aussi etre faite directement a l'entree ;
- il n'y a pas besoin de chronique locale temporelle pour `39Ar`, car la V1
  retiendra une recharge moderne constante definie localement pour Holten ;
- le point important sera surtout de documenter clairement cette normalisation
  dans le futur fichier local `examples/natural/holten/tracers/39Ar/39Ar.yaml`
  et dans les fichiers d'observation convertis.

## Premier constat sur les unites des traceurs

Les unites ne sont pas aujourd'hui homogenes entre les chroniques Holten et les
observations Holten. L'exemple devra donc definir ses propres unites de travail
de bout en bout.

Point important pour `kr85` :

- la chronique locale `examples/natural/holten/doc/freiburg_krypton.txt` est en
  `Bq/cbm air` ;
- les observations Holten dans `sampling_data.txt` sont en `dpm/ccKr` ;
- la V1 devra choisir une unite locale de travail sans chercher a retrouver une
  convention externe preexistante.

Conclusion de cadrage :

- non, la chronique locale `kr85` n'est pas dans la meme unite que les
  observations Holten ;
- un travail explicite de conversion ou de reparametrage local du traceur sera
  necessaire avant toute implementation fiable.

Position retenue a ce stade pour Holten :

- ne pas forcer `kr85` dans une unite externe a Holten ;
- definir un parametrage local Holten du traceur `kr85` ;
- conserver une unite de travail radiometrique, au plus proche des donnees et
  de l'article ;
- prendre `dpm/ccKr` comme unite de travail recommandee pour Holten, car elle
  correspond directement aux observations de `sampling_data.txt` ;
- convertir la chronique locale `freiburg_krypton.txt` depuis `Bq/cbm air`
  vers cette unite locale, plutot que convertir l'ensemble du cas Holten vers
  `pptv`.
- effectuer cette conversion directement a l'entree, lors de la lecture de la
  chronique locale, plutot que de stocker d'abord une chronique intermediaire
  dans une autre unite.

Arguments pratiques en faveur de ce choix :

- le noyau actuel de PyAge transporte l'unite comme metadonnee et ne semble
  pas imposer ici de liste fermee stricte ;
- l'article indique que les rapports isotopiques `85Kr` et `39Ar` ne sont pas
  affectes par le degazage, ce qui conforte l'usage d'un cadrage local centre
  sur l'activite mesuree plutot que sur une conversion prematuree vers
  `pptv`.

Hypothese de conversion directe recommandee a ce stade :

- on suppose que `Bq/cbm air` signifie ici `Bq/m3 d'air sec` ;
- on suppose que `ccKr` des observations correspond a un volume de krypton de
  reference utilise classiquement pour `85Kr` ;
- on utilise la fraction volumique du krypton dans l'air sec
  `x_Kr ~= 1.14e-6` ;
- on applique ensuite uniquement une conversion de volume et de temps.

Formule pratique :

```text
A_kr[dpm/ccKr] = A_air[Bq/m3 air] * 60 / (1e6 * x_Kr)
```

Avec `x_Kr = 1.14e-6`, on obtient :

```text
1 Bq/cbm air ~= 52.6 dpm/ccKr
1 dpm/ccKr   ~= 0.0190 Bq/cbm air
```

Consequence operationnelle :

- la conversion de premier niveau entre la chronique locale et les observations
  Holten semble donc connue ;
- le point a verifier plus tard ne sera pas le principe de conversion, mais la
  convention exacte retenue pour `ccKr` et les conditions de reference du
  laboratoire si l'on veut verrouiller le dernier pourcent de precision.

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
    meaning: "old fraction end-member; 0.45 = 45% modern"
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

## Format cible des fichiers d'observation Holten convertis

Position retenue a ce stade :

- produire un fichier d'observation converti par puits ;
- prevoir aussi un fichier agrege unique pour les 3 puits V1 ;
- rester sur le format tabule simple deja utilise dans les autres exemples
  PyAge ;
- ne garder dans ces fichiers que les traceurs V1 retenus :
  `3H`, `kr85`, `39Ar` ;
- y mettre des unites deja normalisees, pour eviter de reporter les conversions
  au moment de la calibration.

Colonnes cibles :

- `element`
- `concentration`
- `error`
- `unit`
- `date`

Conventions retenues pour la V1 :

- `3H` : conserve en `TU` ;
- `kr85` : converti a l'entree et stocke en `dpm/ccKr` ;
- `39Ar` : converti a l'entree et stocke avec l'etiquette `%modern`, mais avec
  une valeur numerique normalisee entre `0` et `1` ;
- `date` : convertie en annee decimale PyAge a partir de la date exacte de
  campagne, en utilisant la fraction reelle de l'annee calendaire, puis
  arrondie dans les fichiers convertis.

Regle retenue pour la date :

```text
date_decimal = year + (date - 1er janvier 00:00) / (1er janvier annee suivante - 1er janvier)
```

Application a Holten 2010 :

- `20-04-10` -> valeur calculee `2010.2986301369863`, valeur stockee `2010.29863`
- `21-04-10` -> valeur calculee `2010.3013698630136`, valeur stockee `2010.30137`

Convention de stockage retenue :

- calculer la date decimale exacte pendant la preparation ;
- stocker dans les fichiers convertis une valeur arrondie a `5` decimales ;
- conserver la date brute source et, si utile, la valeur exacte non arrondie
  dans les fichiers de reference ou dans le journal de preparation, pas dans
  les fichiers d'observation PyAge.

Exemple cible pour un puits :

```text
element	concentration	error	unit	date
3H	6.09	0.15	TU	2010.30137
kr85	39.7	1.5	dpm/ccKr	2010.30137
39Ar	1.04	0.08	%modern	2010.30137
```

Lecture de cet exemple :

- `3H` est repris directement du tableau source ;
- `kr85` est deja dans l'unite locale de travail choisie pour Holten ;
- `39Ar = 1.04` correspond a `104 pMC` dans le tableau source ;
- l'incertitude `39Ar` suit la meme normalisation que la concentration.

Structure cible recommandee :

- `examples/natural/holten/data/holten_2010_67-19.txt`
- `examples/natural/holten/data/holten_2010_72-22.txt`
- `examples/natural/holten/data/holten_2010_85-33.txt`
- `examples/natural/holten/data/holten_2010_selected_wells.txt`

Statut respectif de ces formats :

- les fichiers par puits restent le format canonique d'entree directe pour
  PyAge ;
- le fichier agrege sert de table de pilotage pour le traitement par lot et la
  generation des fichiers unitaires ;
- il peut donc porter une colonne supplementaire `well_id`, absente des
  fichiers unitaires.

Format cible du fichier agrege :

- `well_id`
- `element`
- `concentration`
- `error`
- `unit`
- `date`

Exemple cible pour le fichier agrege :

```text
well_id	element	concentration	error	unit	date
67-19	3H	6.09	0.15	TU	2010.30137
67-19	kr85	39.7	1.5	dpm/ccKr	2010.30137
67-19	39Ar	1.04	0.08	%modern	2010.30137
72-22	3H	6.75	0.16	TU	2010.29863
72-22	kr85	35.9	1.3	dpm/ccKr	2010.29863
72-22	39Ar	0.93	0.06	%modern	2010.29863
```

Principes associes :

- un fichier converti ne doit plus contenir d'unites brutes article-specifiques
  non normalisees ;
- la tracabilite vers `sampling_data.txt` devra etre conservee a part, soit
  dans la documentation, soit dans des fichiers de reference, mais pas au prix
  d'un format d'observation PyAge plus complexe ;
- les extensions futures autour de l'helium devront vivre dans d'autres
  fichiers ou dans un pretraitement dedie, pas dans ces fichiers V1.

## Convention minimale de validation des fichiers convertis Holten

Principe retenu :

- la validation doit intervenir juste apres la preparation des donnees et avant
  tout appel au launcher ;
- elle doit verifier a la fois la structure tabulaire, les unites et la
  coherence scientifique minimale des valeurs converties ;
- elle doit distinguer ce qui bloque la calibration de ce qui releve seulement
  d'un avertissement utile.

### Erreurs bloquantes

La preparation doit echouer si l'un des points suivants est rencontre :

- absence d'une colonne obligatoire :
  `element`, `concentration`, `error`, `unit`, `date`
  pour un fichier par puits ;
- absence d'une colonne obligatoire :
  `well_id`, `element`, `concentration`, `error`, `unit`, `date`
  pour le fichier agrege ;
- presence d'un traceur hors perimetre V1 :
  autre que `3H`, `kr85`, `39Ar` ;
- absence d'une ligne attendue pour un traceur obligatoire d'un puits retenu ;
- doublon exact sur la cle :
  `element + date`
  pour un fichier par puits ;
- doublon exact sur la cle :
  `well_id + element + date`
  pour le fichier agrege ;
- valeur manquante dans `concentration`, `error`, `unit` ou `date` ;
- `error <= 0` ;
- `concentration < 0` pour `3H`, `kr85` ou `39Ar` ;
- unite incoherente avec la convention Holten V1 :
  `3H -> TU`,
  `kr85 -> dpm/ccKr`,
  `39Ar -> %modern` ;
- `39Ar` avec une valeur manifestement dans la mauvaise convention, par exemple
  `> 10` au lieu d'une fraction de moderne ;
- date hors campagne 2010 dans la V1 ou date non convertible en float ;
- ligne du fichier agrege portant un `well_id` hors du trio retenu.

### Normalisations automatiques autorisees

Ces normalisations peuvent etre faites automatiquement, mais doivent etre
tracees dans le journal de preparation :

- tri des lignes par `well_id`, `date`, `element` ;
- coercition simple des colonnes numeriques vers `float` ;
- arrondi de `date` a `5` decimales ;
- normalisation des noms de traceurs vers la casse et l'ecriture retenues :
  `3H`, `kr85`, `39Ar` ;
- suppression d'espaces parasites dans les unites et les identifiants de puits.

### Avertissements non bloquants

Les cas suivants peuvent generer un avertissement sans bloquer la preparation :

- valeur `3H` tres faible ou tres forte mais restant physiquement plausible ;
- valeur `kr85` tres proche de zero pour un puits jeune ;
- valeur `39Ar` legerement superieure a `1` ;
- presence de colonnes supplementaires non exploitees dans le fichier agrege ;
- ordre des lignes non canonique avant normalisation.

### Regles minimales de couverture pour la V1

Pour les `3` puits retenus, la table agregee doit contenir exactement :

- `3` puits ;
- `3` traceurs par puits ;
- donc `9` lignes de donnees utiles apres filtrage V1.

Chaque fichier par puits doit contenir exactement :

- `3` lignes utiles ;
- une ligne pour `3H` ;
- une ligne pour `kr85` ;
- une ligne pour `39Ar`.

### Position retenue pour la V1

- aucun fichier converti Holten incomplet ne doit partir en calibration ;
- les verifications de structure et d'unites restent dans `holten_prepare.py` ;
- les appreciations plus interpretatives sur la plausibilite des resultats
  restent dans `holten_benchmark.py`.

## Solutions recommandees pour les derniers points de coherence

Pour eviter de laisser subsister des decisions implicites, les solutions
suivantes sont recommandees pour la V1.

### 1. Dates de campagne

Solution retenue :

- utiliser systematiquement la conversion exacte vers annee decimale ;
- stocker dans les fichiers convertis une valeur arrondie a `5` decimales ;
- conserver la date brute source seulement dans les fichiers de reference ou la
  documentation de preparation.

Pourquoi :

- cela colle a la convention PyAge deja utilisee ailleurs ;
- cela evite a la fois les arrondis trop grossiers du type `2010.3` et les
  valeurs inutilement longues du type `2010.3013698630136` ;
- cela rend les fichiers convertis stables et reproductibles.

### 2. Ambiguite semantique du `39Ar`

Solution retenue pour Holten :

- conserver `unit: "%modern"` pour rester compatible avec le traceur PyAge
  existant ;
- documenter explicitement dans le futur YAML local Holten que les valeurs
  stockees sont numeriquement des fractions de moderne entre `0` et `1` ;
- utiliser une cle locale explicite du type
  `holten.input_normalization: "pMC_to_fraction_modern_divide_by_100"`.

Solution recommandee plus large pour le depot, a discuter plus tard :

- soit renommer la convention interne vers quelque chose comme
  `fraction_modern` ;
- soit garder `%modern` mais ajouter une metadonnee explicite de type
  `value_scale: fraction_of_modern`.

### 3. Convention exacte de conversion `kr85`

Solution retenue pour la V1 :

- figer une hypothese explicite et reproductible de conversion ;
- prendre `Bq/cbm air = Bq/m3 air sec` ;
- prendre `x_Kr = 1.14e-6` ;
- prendre le facteur de conversion de travail
  `1 Bq/cbm air ~= 52.6 dpm/ccKr` ;
- stocker cette hypothese et ce facteur dans le futur YAML local
  `examples/natural/holten/tracers/kr85/kr85.yaml`.

Pourquoi :

- cela permet de lancer une V1 scientifiquement lisible sans attendre une
  clarification laboratoire plus fine ;
- si une convention plus precise est obtenue plus tard, il suffira de revoir la
  preparation Holten sans changer le cadrage general de l'exemple.

## Structures cibles des YAML locaux Holten

Les fichiers YAML locaux Holten sont proposes ici comme structures cibles pour
la suite. Ils ne sont pas encore implementes dans le code a ce stade.

Principe general recommande :

- garder en top-level les champs de configuration traceur directement utiles a
  PyAge ;
- utiliser une sous-section `holten:` pour les hypotheses, conversions et
  parametres article-specifiques ;
- garder des cles simples et explicites, quitte a rester un peu verbeux.

Structure generique recommandee :

```yaml
unit: "<working unit>"
recharge: true
# recharge_constant: <value>     # si pas de chronique temporelle
decay_time: <years>
datemin: <decimal year>          # seulement si utile
datemax: <decimal year>          # seulement si utile

holten:
  reference: "Visser et al. (2013)"
  notes: "<case-specific notes>"
  source:
    observation_field: "<field name in sampling_data.txt>"
    observation_unit: "<raw observation unit>"
    recharge_file: "<local raw file>"   # si chronique locale
    recharge_unit: "<raw recharge unit>"# si chronique locale
  preparation:
    input_normalization: "<normalization rule>"
    output_unit: "<working unit>"
  old_endmember:
    value: <value>
    unit: "<working unit>"
    meaning: "<interpretation>"
```

## Champs obligatoires recommandes pour un YAML local Holten complet

Definition retenue ici d'un YAML local Holten complet :

- il doit suffire a documenter sans ambiguite la source, l'unite de travail et
  la regle de preparation du traceur ;
- il doit permettre a `holten_prepare.py` de generer un YAML prepare
  compatible avec `Tracer` sans aller chercher d'information implicite dans un
  traceur generique du depot ;
- les chemins declares dans `holten.source` doivent etre explicites et
  preferablement repo-relatifs, afin de rester autoportants.

### Champs obligatoires communs a tous les traceurs Holten

Top-level obligatoires :

- `unit`
- `decay_time`
- et soit :
  `recharge: true`
  soit :
  `recharge_constant: <value>`

Contraintes top-level associees :

- si `recharge: true`, le YAML doit fournir une source de chronique locale via
  `holten.source.recharge_file` et `holten.source.recharge_unit` ;
- si `recharge_constant` est utilise, `datemin` et `datemax` deviennent
  obligatoires ;
- `production_rate` ne devient obligatoire que pour un traceur qui en aurait
  reellement besoin ; ce n'est pas le cas du noyau V1 Holten.

Sous-section `holten:` obligatoire :

- `holten.reference`
- `holten.source.observation_table`
- `holten.source.observation_field`
- `holten.source.observation_unit`
- `holten.preparation.input_normalization`
- `holten.preparation.output_unit`

Champs fortement recommandes mais non strictement obligatoires :

- `holten.notes`
- `holten.old_endmember.meaning`
- `holten.premodern_input.meaning`

### Champs obligatoires par traceur pour la V1

`3H.yaml`

- top-level :
  `unit`, `recharge`, `decay_time`
- `holten.source` :
  `observation_table`, `observation_field`, `observation_unit`,
  `recharge_file`, `recharge_unit`
- `holten.preparation` :
  `input_normalization`, `output_unit`
- `holten.premodern_input` :
  `value`, `unit`, `uncertainty`

`kr85.yaml`

- top-level :
  `unit`, `recharge`, `decay_time`
- `holten.source` :
  `observation_table`, `observation_field`, `observation_unit`,
  `recharge_file`, `recharge_unit`
- `holten.preparation` :
  `input_normalization`, `output_unit`,
  `krypton_air_fraction`, `conversion_factor`
- `holten.old_endmember` :
  `value`, `unit`

`39Ar.yaml`

- top-level :
  `unit`, `recharge_constant`, `decay_time`, `datemin`, `datemax`
- `holten.source` :
  `observation_table`, `observation_field`, `observation_unit`
- `holten.preparation` :
  `input_normalization`, `output_unit`, `value_scale`
- `holten.old_endmember` :
  `value`, `unit`

### Convention minimale de validation des YAML Holten

Principe retenu :

- la validation doit se faire avant toute conversion de donnees ;
- elle doit produire des erreurs bloquantes sur les points qui rendent le
  traceur ambigu ou inexploitable ;
- elle peut autoriser quelques normalisations automatiques simples, mais jamais
  de completions implicites de contenu scientifique.

#### Erreurs bloquantes

La preparation doit echouer si l'un des points suivants est rencontre :

- absence d'un champ obligatoire liste plus haut ;
- presence simultanee de `recharge` et `recharge_constant` ;
- absence conjointe de `recharge` et `recharge_constant` ;
- `recharge: true` sans `holten.source.recharge_file` ou sans
  `holten.source.recharge_unit` ;
- `recharge_constant` sans `datemin` ou `datemax` ;
- `decay_time <= 0` ;
- `datemin >= datemax` ;
- `holten.preparation.output_unit` different de `unit` ;
- `holten.source.observation_table` manquant ou pointant vers un fichier
  absent ;
- `holten.source.observation_field` absent de la table source ;
- `holten.source.observation_unit` absent alors que la colonne source est
  utilisee ;
- `holten.source.recharge_file` absent ou illisible lorsqu'une chronique locale
  est requise ;
- `holten.old_endmember.unit` different de `unit` lorsqu'un `old_endmember` est
  defini ;
- `holten.premodern_input.unit` different de `unit` lorsqu'un
  `premodern_input` est defini ;
- YAML de `39Ar` sans `value_scale` explicite ;
- YAML de `kr85` sans `krypton_air_fraction` ou sans `conversion_factor`.

#### Normalisations automatiques autorisees

Ces normalisations peuvent etre faites automatiquement pendant la preparation,
mais doivent etre tracees dans le journal de preparation :

- resolution des chemins repo-relatifs vers des chemins absolus ;
- coercition simple `int -> float` pour `decay_time`, `datemin`, `datemax`,
  `recharge_constant`, `old_endmember.value`, `premodern_input.value`,
  `premodern_input.uncertainty` ;
- normalisation mineure de chaines, par exemple suppression d'espaces de debut
  ou de fin dans les unites et les chemins.

#### Avertissements non bloquants

Les cas suivants peuvent donner un avertissement sans bloquer la preparation :

- absence de `holten.notes` ;
- absence de champ `meaning` dans `old_endmember` ou `premodern_input` ;
- presence de champs supplementaires dans `holten:` qui ne sont pas encore
  exploites ;
- `39Ar` avec une valeur `old_endmember.value` atypique par rapport a la valeur
  article `0.45` ;
- `kr85` avec un `conversion_factor` qui s'ecarte de la valeur de travail
  `52.6` tout en restant volontairement documente.

#### Regles minimales par traceur

`3H`

- `recharge` doit etre `true` ;
- `holten.premodern_input.value` et
  `holten.premodern_input.uncertainty` doivent etre positifs ;
- la chronique locale `local_tritium.txt` doit etre presente et lisible.

`kr85`

- `recharge` doit etre `true` ;
- `krypton_air_fraction` et `conversion_factor` doivent etre strictement
  positifs ;
- la chronique locale `freiburg_krypton.txt` doit etre presente et lisible.

`39Ar`

- `recharge_constant` doit etre defini et strictement positif ;
- `value_scale` doit etre explicitement `fraction_of_modern` ;
- `old_endmember.value` doit etre compris strictement entre `0` et `1.5` pour
  eviter les incoherences manifestes de convention numerique.

#### Position retenue pour la V1

- aucun comportement par defaut silencieux ne doit completer un YAML Holten ;
- tout YAML incomplet ou contradictoire doit faire echouer la preparation ;
- les seules corrections automatiques admises sont de nature syntaxique ou
  purement technique, jamais scientifique.

### Proposition pour `3H.yaml`

```yaml
unit: "TU"
recharge: true
decay_time: 12.32

holten:
  reference: "Visser et al. (2013)"
  notes: "Local tritium chronicle preferred for Holten."
  source:
    observation_table: "examples/natural/holten/doc/sampling_data.txt"
    observation_field: "3H_TU"
    observation_unit: "TU"
    recharge_file: "examples/natural/holten/doc/local_tritium.txt"
    recharge_unit: "TU"
  preparation:
    input_normalization: "none"
    output_unit: "TU"
  premodern_input:
    value: 3.0
    unit: "TU"
    uncertainty: 0.4
    meaning: "premodern initial concentration before 1953"
```

### Proposition pour `kr85.yaml`

```yaml
unit: "dpm/ccKr"
recharge: true
decay_time: 10.76

holten:
  reference: "Visser et al. (2013)"
  notes: "Holten-specific radiometric convention; do not force pptv."
  source:
    observation_table: "examples/natural/holten/doc/sampling_data.txt"
    observation_field: "Kr85_dpm_ccKr"
    observation_unit: "dpm/ccKr"
    recharge_file: "examples/natural/holten/doc/freiburg_krypton.txt"
    recharge_unit: "Bq/cbm air"
  preparation:
    input_normalization: "Bq_cbm_air_to_dpm_ccKr"
    output_unit: "dpm/ccKr"
    krypton_air_fraction: 1.14e-6
    conversion_factor: 52.6
  old_endmember:
    value: 0.0
    unit: "dpm/ccKr"
    meaning: "plausible premodern old-fraction end-member for V1"
```

### Proposition pour `39Ar.yaml`

```yaml
unit: "%modern"
recharge_constant: 1
decay_time: 267
datemin: 200
datemax: 2021

holten:
  reference: "Visser et al. (2013)"
  notes: "Stored as fraction of modern although unit label stays %modern."
  source:
    observation_table: "examples/natural/holten/doc/sampling_data.txt"
    observation_field: "Ar39_pMC"
    observation_unit: "pMC"
  preparation:
    input_normalization: "pMC_to_fraction_modern_divide_by_100"
    output_unit: "%modern"
    value_scale: "fraction_of_modern"
  old_endmember:
    value: 0.45
    unit: "%modern"
    meaning: "old fraction end-member; 0.45 = 45% modern"
```

Ce que ces structures resolvent :

- `3H` garde une convention locale simple en `TU` ;
- `kr85` rend explicite la conversion locale choisie pour Holten ;
- `39Ar` rend explicite l'ecart entre etiquette textuelle et echelle numerique ;
- les hypotheses article-specifiques sont visibles sans etre codees en dur dans
  le futur LPM.

## Strategie recommandee pour charger les YAML locaux Holten

Point important issu de l'etat actuel du code :

- le chargeur `Tracer` de `pyage/tracer/tracer_root.py` est strict sur les cles
  top-level ;
- a ce stade, toute cle inconnue dans un YAML de traceur provoque une erreur ;
- une sous-section libre `holten:` ne peut donc pas etre lue directement par le
  chargeur actuel sans adaptation ;
- de plus, `ConvolutionTracers` utilise encore par defaut
  `gp.DIRECTORY_TRACER_DATA`, donc le launcher ne sait pas encore prendre un
  repertoire local de traceurs via son YAML standard.

Consequence :

- les futurs YAML locaux Holten ne devront pas etre injectes tels quels dans le
  chargeur standard au premier jalon ;
- il faut une etape de preparation ou une petite extension de l'infrastructure ;
- cette etape de preparation ne devra pas chercher a fusionner Holten avec les
  traceurs generiques du depot.

Solution recommandee pour la V1 : repertoire de traceurs prepares

Principe :

- conserver les YAML locaux Holten comme source de verite documentaire et
  scientifique ;
- lire ces YAML locaux dans `holten_prepare.py`, sans passer par `Tracer` ;
- en deriver un repertoire temporaire ou prepare au format traceur standard
  PyAge, sans sous-section `holten:` ;
- y ecrire, pour chaque traceur retenu, un YAML "aplati" compatible avec
  `Tracer` et, si necessaire, une `recharge.csv` deja convertie ;
- faire ensuite pointer l'execution Holten vers ce repertoire prepare comme
  source unique des traceurs du cas Holten.

Structure cible recommandee :

```text
examples/
  natural/
    holten/
      tracers/
        3H/
          3H.yaml
        kr85/
          kr85.yaml
        39Ar/
          39Ar.yaml
      prepared_tracers/
        data_tracer/
          3H/
            3H.yaml
            recharge.csv
          kr85/
            kr85.yaml
            recharge.csv
          39Ar/
            39Ar.yaml
```

Sens de cette distinction :

- `tracers/` :
  source locale editable par l'utilisateur, avec la sous-section `holten:` ;
- `prepared_tracers/data_tracer/` :
  artefacts normalises, strictement compatibles avec le chargeur PyAge actuel.

Regle de transformation recommandee :

- partir uniquement des YAML locaux Holten et des sources article-specifiques
  du dossier Holten ;
- generer pour chaque traceur un YAML exploitable de maniere autonome, complet sur
  les champs requis par `Tracer` ;
- si une chronique locale est necessaire au traceur, la preparer localement et
  l'ecrire sous `prepared_tracers/data_tracer/<name>/recharge.csv` ;
- si un traceur repose sur une recharge constante locale, ecrire cette
  information directement dans le YAML prepare ;
- si un traceur n'a pas de definition locale suffisante, produire une erreur de
  preparation explicite plutot qu'un repli implicite ;
- appliquer les conversions documentees dans `holten.preparation` ;
- copier dans le YAML aplati seulement les cles reconnues aujourd'hui par
  `Tracer` :
  `unit`, `recharge`, `recharge_constant`, `decay_time`, `production_rate`,
  `datemin`, `datemax` ;
- ne jamais recopier `holten:` dans le YAML prepare destine au chargeur
  standard.

Solution de raccord recommandee avec l'execution :

- `run_holten.py` prepare ce repertoire `prepared_tracers/data_tracer/` avant
  l'appel au launcher ;
- l'execution Holten doit ensuite utiliser explicitement ce repertoire de
  traceurs prepares ;
- la voie la plus propre a moyen terme sera d'ajouter au launcher une notion de
  `tracer_data_dir` configurable ;
- en attendant, une integration locale Holten peut rester acceptable si elle
  est circonscrite a `run_holten.py` et n'affecte pas les autres exemples.

Solutions a eviter pour la V1 :

- chercher a fusionner les YAML Holten avec des YAML generiques du depot ;
- utiliser un repertoire generique du depot comme base de composition pour les
  traceurs Holten ;
- coder des valeurs article-specifiques en dur dans le futur LPM ;
- faire lire directement par `Tracer` un YAML contenant `holten:` sans definir
  de convention de compatibilite plus generale ;
- disperser la logique de conversion dans plusieurs endroits du code.

Pourquoi cette approche est recommandee :

- elle n'impose pas de casser le chargeur actuel ;
- elle garde les hypotheses Holten visibles et editables ;
- elle garde Holten entierement autonome du point de vue des traceurs ;
- elle prepare une evolution plus generale du depot vers un
  `tracer_data_dir` injectable sans rendre ce chantier bloquant pour la V1.

Evolution plus propre a moyen terme, a discuter plus tard :

- etendre `LauncherConfig` et `LauncherParams` avec un champ optionnel
  `tracer_data_dir` ;
- faire en sorte que `ConvolutionTracers` n'utilise plus directement
  `gp.DIRECTORY_TRACER_DATA`, mais un repertoire injecte ;
- autoriser ensuite, si souhaite, la conservation d'une sous-section libre
  comme `holten:` dans les YAML sources sans que cela perturbe l'execution.

## Structure cible du futur `holten.yaml`

Le futur fichier `examples/natural/holten/holten.yaml` peut etre pense comme un
fichier pilote unique pour la V1.

Point important pour la compatibilite :

- le schema actuel du launcher PyAge repose surtout sur les sections
  `dataset`, `lpm`, `run`, `reachable_concentrations`, `objective_function`,
  `calibration_metropolis_hastings` et `calibration_simplex` ;
- les modeles Pydantic du depot ignorent deja les cles inconnues ;
- on peut donc viser un fichier avec :
  un coeur compatible avec le launcher existant,
  plus des sections `holten:` ou `preparation:` qui seront exploitees plus
  tard par un pilote ou un pretraitement dedie.

Principe de conception recommande :

- garder les sections deja connues par PyAge en l'etat ;
- centraliser dans `holten:` tout ce qui concerne les puits, les traceurs
  locaux, la preparation des donnees et les sorties de benchmark ;
- faire du fichier agrege `holten_2010_selected_wells.txt` l'entree dataset par
  defaut pour le traitement par lot ;
- laisser les fichiers par puits disponibles comme sorties ou entrees
  secondaires de verification.

Structure cible recommandee :

```yaml
dataset:
  name: holten_2010_selected_wells.txt
  label: Holten 2010 benchmark multi-traceurs
  year: 2010
  data_dir: examples/natural/holten/data
  verbose: true

lpm:
  model_name: <future_holten_4bin_name>
  data_directory: examples/natural/holten/data_lpm

run:
  reachable_concentrations: true
  objective_function: true
  calibration_metropolis_hastings: true
  calibration_simplex: false

reachable_concentrations:
  nmodels: 4000

objective_function:
  nmodels: 6000

calibration_metropolis_hastings:
  nstep: 5000
  prior_option: false
  likelihood: true
  monitor: false
  display_traj: false

holten:
  campaign:
    label: "April 2010"
    tracer_scope: "holten_only"
    selected_wells:
      - "67-19"
      - "72-22"
      - "85-33"
  tracers:
    calibration:
      - "3H"
      - "kr85"
      - "39Ar"
    local_directories:
      3H: examples/natural/holten/tracers/3H
      kr85: examples/natural/holten/tracers/kr85
      39Ar: examples/natural/holten/tracers/39Ar
    prepared_data_dir: examples/natural/holten/prepared_tracers/data_tracer
  preparation:
    source_sampling_file: examples/natural/holten/doc/sampling_data.txt
    source_tritium_file: examples/natural/holten/doc/local_tritium.txt
    source_kr85_file: examples/natural/holten/doc/freiburg_krypton.txt
    generate_per_well_files: true
    aggregated_dataset: examples/natural/holten/data/holten_2010_selected_wells.txt
    date_round_decimals: 5
  figures:
    pre_model:
      tracer_panels: true
      well_panels: true
  validation:
    reference_results: examples/natural/holten/doc/calibration_results.txt
    qualitative: true
    semi_quantitative: true
```

Lecture de cette structure :

- la partie haute reste proche d'un YAML de launcher standard ;
- la section `holten.campaign` fixe le sous-ensemble de puits et la strategie
  `holten_only` ;
- la section `holten.tracers` relie le benchmark aux futurs YAML locaux ;
- elle peut aussi porter le chemin du repertoire de traceurs prepares utilise
  effectivement par l'execution ;
- la section `holten.preparation` documente les sources brutes et la logique de
  generation des fichiers convertis ;
- la section `holten.figures` cadre la visualisation hors modele ;
- la section `holten.validation` rattache explicitement l'exemple aux resultats
  publies.

Solution recommandee pour la V1 :

- utiliser `holten_2010_selected_wells.txt` comme table de pilotage et de
  preparation ;
- lancer effectivement le launcher puits par puits a partir des fichiers
  `holten_2010_<well_id>.txt` ;
- produire en parallele les fichiers `holten_2010_<well_id>.txt` pour audit et
  verification ;
- utiliser un `params.yaml` local au futur LPM Holten sous
  `examples/natural/holten/data_lpm/` ;
- laisser le nom concret du futur LPM `4-bin` encore ouvert tant que son
  implementation n'est pas engagee.

Note d'implementation actuelle :

- un premier branchement executable peut s'appuyer provisoirement sur un LPM
  local `uniform`, uniquement comme modele bootstrap de workflow ;
- ce branchement ne remplace pas la cible scientifique restee fixee sur le
  futur `4-bin` derive de `n_bin_old`.

## Structure cible du futur `run_holten.py`

Le futur script `examples/natural/holten/run_holten.py` doit rester un pilote
leger, dans l'esprit de `run_ploemeur.py`, `run_albuquerque.py` ou
`run_fontainebleau.py`, mais avec quelques etapes supplementaires propres a
Holten.

Principe general recommande :

- ne pas y recoder la logique du launcher PyAge ;
- utiliser ce script comme point d'entree orchestration de l'exemple ;
- deleguer la calibration au launcher existant ;
- reserver a `run_holten.py` les etapes de preparation, de visualisation hors
  modele et de comparaison aux resultats publies.

Enchainement logique recommande pour la V1 :

1. charger `holten.yaml` ;
2. lire la section `holten.campaign` pour connaitre les puits et la strategie
   `holten_only` ;
3. preparer les donnees converties a partir des fichiers bruts Holten ;
4. preparer le repertoire `prepared_tracers/data_tracer/` compatible avec le
   chargeur standard, mais entierement derive des sources locales Holten ;
5. produire le fichier agrege `holten_2010_selected_wells.txt` et, si demande,
   les fichiers unitaires par puits ;
6. produire la visualisation hors modele ;
7. generer des YAML launcher derives, un par puits ;
8. appeler `scripts/launcher.py` puits par puits ;
9. relire les sorties de calibration ;
10. comparer les sorties a `calibration_results.txt` ;
11. ecrire un petit resume de benchmark.

Philosophie de conception :

- si les fichiers convertis existent deja et sont a jour, `run_holten.py`
  pourra sauter leur regeneration ;
- la preparation doit etre idempotente ;
- la calibration doit rester lancable seule ;
- la comparaison finale doit pouvoir etre rejouee sans recalculer toutes les
  etapes amont.

Modes d'execution cibles recommandee :

- mode par defaut : tout enchainer de la preparation a la comparaison ;
- `prepare_only` : convertir les donnees et sortir les figures hors modele sans
  calibration ;
- `calibration_only` : partir des fichiers convertis existants et lancer
  seulement le launcher ;
- `compare_only` : relire les resultats existants et refaire uniquement la
  comparaison au referentiel publie.

Pseudo-structure recommandee :

```python
def main():
    cfg = load_holten_config()
    paths = resolve_paths(cfg)

    if needs_preparation(cfg, paths):
        prepared = prepare_holten_inputs(cfg, paths)
    else:
        prepared = load_prepared_inputs(paths)

    if cfg["holten"]["figures"]["pre_model"]:
        build_pre_model_figures(cfg, prepared, paths)

    if should_run_calibration(cfg):
        results_dir = run_launcher_with_yaml(paths.holten_yaml)
    else:
        results_dir = locate_existing_results(cfg, paths)

    benchmark = compare_with_reference_results(cfg, prepared, results_dir)
    write_benchmark_summary(benchmark, results_dir)
```

Sous-fonctions cibles utiles :

- `prepare_holten_inputs(...)`
- `convert_sampling_table(...)`
- `load_local_recharge_histories(...)`
- `build_pre_model_figures(...)`
- `run_launcher_with_yaml(...)`
- `compare_with_reference_results(...)`
- `write_benchmark_summary(...)`

Sorties minimales recommandees :

- fichiers convertis dans `examples/natural/holten/data/`
- figures hors modele par traceur et par puits
- resultats standards PyAge du launcher
- tableau de comparaison aux resultats publies
- court fichier texte ou CSV de synthese benchmark
- une structure de sorties detaillee est recommandee plus bas dans ce document,
  pour rester compatible avec le launcher tout en isolant les artefacts propres
  a Holten

Position retenue pour la V1 :

- `run_holten.py` doit rester petit et lisible ;
- les transformations de donnees un peu denses doivent etre poussees dans un ou
  plusieurs helpers locaux plutot que laissees dans `main()` ;
- l'orchestration doit privilegier la reproductibilite et la tracabilite sur
  l'optimisation prematuree.

## Structure cible des helpers locaux Holten

Pour la V1, il vaut mieux viser une petite architecture locale plutot qu'un
grand module unique ou un sous-package trop fragmente.

Solution recommandee :

- garder `run_holten.py` comme point d'entree unique ;
- ajouter `3` modules helpers locaux a cote ;
- ne creer un sous-repertoire `scripts/` ou `helpers/` que si la logique grossit
  reellement au-dela de cette V1.

Structure cible recommandee :

```text
examples/
  natural/
    holten/
      run_holten.py
      holten.yaml
      holten_case.py
      holten_prepare.py
      holten_benchmark.py
```

### 1. `holten_case.py`

Responsabilite :

- centraliser les chemins, la lecture de configuration et les objets de
  contexte partages ;
- eviter de re-resoudre partout les memes chemins et les memes cles YAML.

Contenu cible recommande :

- une dataclass `HoltenPaths`
- une dataclass `HoltenContext` ou `PreparedHoltenCase`
- `case_paths()`
- `load_holten_config()`
- `resolve_paths()`
- `load_reference_results()`
- eventuellement `decimal_year_from_sampling_date()`

Pourquoi :

- c'est l'equivalent naturel du role joue par `synthetic_case.py` dans
  l'exemple synthetique ;
- cela donne un seul point de verite pour les chemins et la config.

### 2. `holten_prepare.py`

Responsabilite :

- transformer les sources brutes Holten en fichiers d'entree PyAge propres ;
- porter toute la logique de normalisation des unites et de selection des puits.

Contenu cible recommande :

- `read_sampling_table(...)`
- `select_v1_wells(...)`
- `validate_local_tracer_yaml(...)`
- `convert_sampling_observations(...)`
- `convert_3h_record(...)`
- `convert_kr85_record(...)`
- `convert_39ar_record(...)`
- `build_prepared_tracer_directory(...)`
- `validate_converted_dataset(...)`
- `write_per_well_files(...)`
- `write_aggregated_dataset(...)`
- `prepare_holten_inputs(...)`

Sorties attendues :

- DataFrame converti pour les 3 puits V1
- fichiers `holten_2010_<well_id>.txt`
- fichier `holten_2010_selected_wells.txt`
- eventuellement une trace de preparation ou un petit journal CSV

Pourquoi :

- ce module concentre la partie la plus mecanique et la plus sujette aux
  incoherences si elle reste dispersee ;
- il rend l'exemple testable plus facilement.

### 3. `holten_benchmark.py`

Responsabilite :

- produire la lecture scientifique hors modele ;
- comparer les sorties PyAge au referentiel publie ;
- ecrire la synthese finale du benchmark.

Contenu cible recommande :

- `build_pre_model_figures(...)`
- `plot_tracer_histories_vs_observations(...)`
- `plot_well_panels(...)`
- `compare_with_reference_results(...)`
- `build_qualitative_assessment(...)`
- `build_semi_quantitative_table(...)`
- `write_benchmark_summary(...)`

Sorties attendues :

- figures hors modele
- tableau de comparaison puits par puits
- court resume texte ou CSV de benchmark

Pourquoi :

- cela separe proprement la preparation de donnees de l'analyse des resultats ;
- cela garde `run_holten.py` lisible.

## Repartition recommande des responsabilites

`run_holten.py`

- orchestre
- appelle les helpers
- decide quelles etapes lancer

`holten_case.py`

- charge et resolve le contexte

`holten_prepare.py`

- convertit et ecrit les donnees

`holten_benchmark.py`

- trace, compare et resume

## Ce qu'il vaut mieux eviter

- mettre les conversions d'unites directement dans `run_holten.py` ;
- dupliquer la resolution des chemins dans plusieurs fichiers ;
- melanger preparation des donnees et comparaison benchmark dans le meme module ;
- creer trop tot `5` ou `6` petits helpers tres specialises.

## Position retenue sur l'emplacement des validations et des parametres

Oui : tant qu'une logique est specifique a Holten, elle doit rester dans
l'espace Holten.

Validations Holten a laisser dans les helpers locaux :

- validation des YAML locaux Holten ;
- validation des fichiers prepares `prepared_tracers/` ;
- validation des conversions d'unites Holten ;
- validation des fichiers d'observation convertis ;
- controles de coherence par rapport a l'article.

Repartition recommandee :

- `holten_case.py` :
  lecture de configuration, resolution des chemins, petits controles de
  presence ;
- `holten_prepare.py` :
  validations bloquantes sur les YAML traceurs, construction de
  `prepared_tracers/`, validation des fichiers convertis ;
- `holten_benchmark.py` :
  validations scientifiques et comparaison au referentiel publie.

Ce qui ne devrait passer dans le socle commun PyAge que plus tard, et seulement
si cela se revele reutilisable :

- un mecanisme generique de `tracer_data_dir` injectable ;
- un validateur generique de YAML de traceur source vs YAML prepare ;
- un support plus general de metadata libres du type `holten:`.

## Position retenue sur les fichiers de parametres

Oui : pour la V1 Holten, les fichiers de parametres doivent devenir
specifiques.

Concretement :

- les YAML de traceurs seront specifiques a Holten sous
  `examples/natural/holten/tracers/` ;
- les YAML prepares pour l'execution seront specifiques a Holten sous
  `examples/natural/holten/prepared_tracers/data_tracer/` ;
- le `params.yaml` du premier LPM `4-bin` devra lui aussi etre local a Holten
  sous `examples/natural/holten/data_lpm/<future_holten_4bin_name>/params.yaml`
  ;
- le fichier pilote `holten.yaml` restera naturellement specifique a Holten.

Raison de ce choix :

- garantir la coherence avec l'article avant toute tentative de factorisation ;
- eviter qu'un parametrage article-specifique soit pris a tort pour une
  convention generique du depot ;
- garder visible, testable et discutable tout ce qui releve du cas Holten.

Position de prudence pour la suite :

- on pourra generaliser plus tard une partie du LPM ou de certains parametres
  vers `data_core` ;
- mais cette generalisation ne devra intervenir qu'apres validation sur Holten,
  pas avant.

Position retenue pour la V1 :

- `3` helpers locaux suffisent ;
- `holten_case.py` doit etre le module leger de contexte ;
- `holten_prepare.py` doit porter les conversions et la generation des fichiers ;
- `holten_benchmark.py` doit porter les figures et la comparaison ;
- si un jour la partie figures devient plus lourde, elle pourra etre extraite
  ensuite sans casser cette premiere structure.

## Objets de contexte et tables cibles

Pour eviter des signatures floues et des DataFrames ambigus, il est utile de
poser des objets de travail explicites des la phase de cadrage.

Solution recommandee pour la V1 :

- un objet `HoltenPaths` pour tous les chemins fixes ;
- un objet `HoltenContext` pour la configuration chargee et les choix V1 ;
- un objet `PreparedHoltenCase` pour les donnees deja converties, pretes a etre
  tracees ou calibrees ;
- des DataFrames nommes selon leur role plutot que selon leur provenance brute.

### Dataclass `HoltenPaths`

Responsabilite :

- contenir tous les chemins utilises par l'exemple ;
- eviter les chemins recalcules a la main dans plusieurs modules.

Champs cibles recommandes :

- `example_dir`
- `data_dir`
- `tracer_dir`
- `reference_dir`
- `yaml_path`
- `sampling_raw_path`
- `tritium_raw_path`
- `kr85_raw_path`
- `reference_results_path`
- `aggregated_dataset_path`
- `per_well_dataset_paths`

### Dataclass `HoltenContext`

Responsabilite :

- contenir la configuration interpretee du cas Holten ;
- porter les choix qui ne changent pas pendant un run.

Champs cibles recommandes :

- `paths: HoltenPaths`
- `config: dict`
- `selected_wells: list[str]`
- `calibration_tracers: list[str]`
- `tracer_scope: str`
- `date_round_decimals: int`
- `lpm_name: str`

### Dataclass `PreparedHoltenCase`

Responsabilite :

- servir d'objet d'echange entre preparation, figures, calibration et
  benchmark ;
- eviter de passer `5` ou `6` DataFrames separes a chaque fonction.

Champs cibles recommandes :

- `context: HoltenContext`
- `sampling_raw: pd.DataFrame`
- `observed_aggregated: pd.DataFrame`
- `observed_by_well: dict[str, pd.DataFrame]`
- `tracer_histories: dict[str, pd.DataFrame]`
- `preparation_log: pd.DataFrame | None`

### Tables cibles recommandees

`sampling_raw`

- table brute lue depuis `sampling_data.txt`
- colonnes source conservees autant que possible

`observed_aggregated`

- table propre au format PyAge et au format lot Holten
- colonnes cibles :
  `well_id`, `element`, `concentration`, `error`, `unit`, `date`

`observed_by_well[well_id]`

- sous-table par puits au format PyAge direct
- colonnes cibles :
  `element`, `concentration`, `error`, `unit`, `date`

`tracer_histories["3H"]`, `tracer_histories["kr85"]`, `tracer_histories["39Ar"]`

- chroniques de recharge ou pseudo-chroniques pretes a etre tracees
- pour `3H` et `kr85` :
  `date`, `concentration`, `unit`
- pour `39Ar` :
  soit une pseudo-serie minimale constante,
  soit une structure de metadonnees de recharge constante selon ce qui sera le
  plus simple a tracer pedagogiquement

`preparation_log`

- table de tracabilite recommandee
- colonnes cibles :
  `well_id`, `element`, `raw_value`, `raw_unit`, `converted_value`,
  `converted_unit`, `conversion_rule`, `source_field`

Pourquoi cette structure :

- elle clarifie ce qui est brut, converti, unitaire ou agrege ;
- elle facilite les tests futurs ;
- elle rend le notebook plus lisible, car chaque cellule peut afficher un objet
  bien nomme.

## Structure cible des sorties de resultats Holten

Pour rester compatible avec le launcher actuel, les sorties standard PyAge
doivent continuer a vivre sous :

- `results/test_cases/<dataset_name>/`

Pour Holten, il est recommande d'ajouter dans ce dossier un sous-repertoire
specifique `holten/`, afin de bien separer :

- les sorties standard du launcher ;
- les artefacts de preparation et de benchmark propres a l'exemple ;
- les figures didactiques qui ne relevent pas directement du coeur du launcher.

Structure cible recommandee :

```text
results/
  test_cases/
    holten_2010_selected_wells/
      concentrations.txt
      02_parameter_summary.png
      03_objective_summary.png
      ...
      holten/
        prepared/
          holten_2010_selected_wells.txt
          wells/
            holten_67-19.txt
            holten_72-22.txt
            holten_85-33.txt
          tracer_histories/
            3H_local_prepared.txt
            kr85_local_prepared.txt
            39Ar_local_prepared.txt
          preparation_log.txt
        pre_model/
          tracer_3H_history_and_observations.png
          tracer_kr85_history_and_observations.png
          tracer_39Ar_history_and_observations.png
          well_67-19_multi_tracer_panel.png
          well_72-22_multi_tracer_panel.png
          well_85-33_multi_tracer_panel.png
        benchmark/
          comparison_by_well.csv
          comparison_by_well.md
          benchmark_summary.txt
          benchmark_summary.csv
```

Sens recommande de chaque sous-repertoire :

`holten/prepared/`

- copie tracable des entrees effectivement utilisees par le run ;
- ne remplace pas les fichiers canoniques sous
  `examples/natural/holten/data/` ;
- sert a documenter exactement ce qui a ete injecte dans la calibration.

`holten/pre_model/`

- figures hors modele construites avant toute calibration ;
- support principal du notebook pour la lecture pedagogique du cas ;
- lieu naturel pour les graphes par traceur et par puits.

`holten/benchmark/`

- tableaux et syntheses de comparaison aux resultats publies ;
- sorties directement exploitables dans le notebook et dans une revue rapide ;
- support de la validation qualitative et semi-quantitative.

Sorties minimales recommandees pour la V1 :

- `holten/prepared/preparation_log.txt`
- `holten/pre_model/tracer_3H_history_and_observations.png`
- `holten/pre_model/tracer_kr85_history_and_observations.png`
- `holten/pre_model/tracer_39Ar_history_and_observations.png`
- `holten/pre_model/well_67-19_multi_tracer_panel.png`
- `holten/pre_model/well_72-22_multi_tracer_panel.png`
- `holten/pre_model/well_85-33_multi_tracer_panel.png`
- `holten/benchmark/comparison_by_well.csv`
- `holten/benchmark/benchmark_summary.txt`

Pourquoi cette structure :

- elle reste compatible avec le launcher sans le surcharger ;
- elle rend explicite la frontiere entre "run PyAge standard" et "benchmark
  Holten" ;
- elle fournit au notebook des artefacts directement lisibles, sans lui faire
  relancer toute la logique.

## Structure cible du notebook `exemple_holten.ipynb`

Un notebook associe est fortement recommande, dans l'esprit de
`exemple_ploemeur.ipynb`, mais avec une ambition plus didactique et plus
exhaustive sur les choix scientifiques et techniques retenus pour Holten.

Position retenue pour la V1 :

- nom cible : `examples/natural/holten/exemple_holten.ipynb`
- role : support pedagogique, scientifique et benchmark
- il ne doit pas dupliquer toute la logique metier ;
- il doit s'appuyer sur les helpers locaux et sur `run_holten.py`.

Principe recommande :

- le script `run_holten.py` reste le point d'entree reproductible ;
- le notebook sert a expliquer pas a pas :
  la preparation, la lecture hors modele, la calibration, puis la comparaison ;
- il doit proposer une lecture "beginner" puis une lecture "expert", comme
  Ploemeur, mais avec plus de contexte scientifique explicite ;
- chaque grande section doit dire clairement :
  ce qui vient de l'article,
  ce qui est adapte pour PyAge,
  ce qui est volontairement differe en V1.

Article de reference a relier explicitement dans le notebook :

- [Visser et al. (2013)](../../../examples/natural/holten/doc/Visser%20et%20al,%202013.pdf)
- `examples/natural/holten/doc/sampling_data.txt`
- `examples/natural/holten/doc/calibration_results.txt`
- `../../../docs/examples/holten/notes-helium.md`

Elements de l'article a citer explicitement et a expliquer dans le notebook :

- `Table 1` :
  source principale des observations de puits de production retenues pour la V1
- `Table 2` :
  contexte sur les puits de suivi et sur la lecture verticale des eaux jeunes
  et anciennes, utile pour interpreter les contrastes mais pas repris en V1
- `Figure 4` :
  justification de la lecture hors modele de la chronique `3H` et de la logique
  `3H + 3He_trit`
- `Figures 5` et `6` :
  contexte interpretatif sur la structuration verticale des ages et le role de
  l'helium ; utiles pour expliquer, mais reportes hors coeur V1
- `Figure 8` :
  justification du role diagnostique de `39Ar` et de `4He` pour les composantes
  plus anciennes
- `Figure 9` :
  point d'ancrage principal pour la pedagogie autour des traceurs, des
  end-members et du modele discret `4-bin`
- `Figure 10` :
  point d'ancrage principal pour expliquer la famille `n_bin_old` et la place
  du `4-bin` par rapport aux autres familles de modeles

Lecture didactique recommandee :

- chaque bloc de notebook doit commencer par une courte cellule Markdown qui
  repond a :
  "Que reprend-on de l'article ?",
  "Qu'adapte-t-on pour PyAge ?",
  "Pourquoi ce choix ?"
- chaque transformation importante de donnees doit etre accompagnee d'un rappel
  de la source et de la convention retenue ;
- les cellules de code doivent rester courtes et deleguer la logique aux
  helpers locaux ;
- chaque grande etape doit se terminer par une cellule de synthese courte.

Feuille de route cible du notebook :

1. `# Holten 2010 benchmark multi-traceurs`
2. `## Notebook roadmap`
3. `## 1. What comes directly from the article`
4. `## 2. What is adapted for PyAge and why`
5. `## 3. Case settings and selected wells`
6. `## 4. Source data and converted observations`
7. `## 5. Local tracer histories and pre-model reading`
8. `## 6. Why start with a discrete 4-bin model`
9. `## 7. Run the Holten workflow`
10. `## 8. Read the benchmark outputs first`
11. `## 9. Compare well by well with published results`
12. `## 10. Expert mode`
13. `## 11. Deferred items and next extensions`

Contenu recommande par section :

`## 1. What comes directly from the article`

- lister ce qui est repris tel quel de l'article de reference
- expliciter que la V1 s'appuie d'abord sur les puits de production et les
  chroniques locales disponibles
- rappeler les figures et tableaux vraiment exploites en V1

`## 2. What is adapted for PyAge and why`

- expliquer la strategie `holten_only`
- expliquer les conversions d'unites `kr85` et `39Ar`
- expliquer pourquoi `39Ar` garde une etiquette `%modern` mais une valeur
  numerique normalisee entre `0` et `1`
- expliquer pourquoi l'helium est temporairement sorti du coeur V1

`## 3. Case settings and selected wells`

- afficher `holten.yaml`
- rappeler les 3 puits retenus
- rappeler les traceurs V1
- rappeler la strategie `holten_only`
- rappeler la logique du trio contraste :
  `67-19`, `72-22`, `85-33`

`## 4. Source data and converted observations`

- afficher un extrait de `sampling_raw`
- afficher `observed_aggregated`
- afficher un exemple de fichier par puits
- commenter les conversions `kr85` et `39Ar`
- montrer la table de tracabilite `preparation_log`

`## 5. Local tracer histories and pre-model reading`

- tracer la chronique `3H`
- tracer la chronique `kr85`
- montrer la convention de `39Ar`
- produire les graphes par traceur et par puits
- relier cette lecture a `Figure 4` et a la logique pedagogique de `Figure 9`

`## 6. Why start with a discrete 4-bin model`

- expliquer la famille `n_bin_old`
- expliquer pourquoi la premiere instanciation est un `4-bin`
- rappeler les classes `0-20`, `20-40`, `40-60`, `old`
- relier ce choix a `Figure 9` et `Figure 10`
- rappeler que l'objectif V1 est la clarte et la proximite a l'article, pas la
  generalisation maximale

`## 7. Run the Holten workflow`

- appeler `run_holten.py` ou les helpers d'orchestration
- afficher le repertoire de resultats
- montrer ou se trouvent les sorties `prepared`, `pre_model` et `benchmark`

`## 8. Read the benchmark outputs first`

- montrer les figures principales
- lire rapidement les resultats sans entrer dans tous les details internes
- commencer par les sorties les plus parlantes pour un lecteur non expert

`## 9. Compare well by well with published results`

- tableau qualitatif et semi-quantitatif
- ecarts puits par puits
- commentaire rapide sur la coherence globale
- rappel de ce qui est strictement comparable a l'article et de ce qui ne l'est
  pas encore

`## 10. Expert mode`

- afficher les objets internes utiles :
  posterior, grille objectif, fractions estimees du modele discret, etc.
- si disponible plus tard :
  lecture du `4-bin` ou `n_bin_old` dans l'espace des fractions
- montrer les points ou PyAge converge ou diverge du cadrage article

`## 11. Deferred items and next extensions`

- renvoyer vers `notes-helium.md`
- rappeler les limites V1
- lister les prochaines extensions scientifiques utiles

Objets notebook recommandes :

- `ctx` pour `HoltenContext`
- `prepared` pour `PreparedHoltenCase`
- `results_dir` pour le repertoire de sortie
- `comparison_table` pour la comparaison au referentiel
- `article_links` pour une petite table de renvoi vers les figures et tableaux
  cites

Position retenue pour la V1 :

- notebook pedagogique et scientifique, pas simple carnet d'execution ;
- reutiliser au maximum les helpers locaux ;
- privilegier des cellules courtes, lisibles, avec sorties directement
  interpretables ;
- separer clairement ce qui est donnees preparees, visualisation hors modele,
  calibration et benchmark final ;
- rendre explicite, dans le texte du notebook, ce qui a ete exploite de
  l'article et pourquoi ;
- rendre tout aussi explicite ce qui n'est pas encore exploite et pourquoi.

## Travaux de preparation a prevoir plus tard

La future implementation devra probablement traiter les points suivants :

- encodage explicite des `3` puits cibles retenus ;
- normalisation des identifiants de puits et des dates ;
- conversion des unites sources vers les unites attendues par les configurations
  de traceurs ;
- implementation explicite de la strategie `holten_only` pour les traceurs ;
- transformation de la table source en fichiers d'observation PyAge ;
- tracabilite de chaque valeur convertie vers sa source d'origine ;
- generation des figures de premiere lecture hors modele, a la fois par
  traceur et par puits.

## Questions techniques ouvertes

- Comment parametrer proprement le futur LPM discret en bins dans PyAge ?
- Comment representer numeriquement la composante `old` dans le premier modele
  `4-bin`, en restant fidele a sa logique d'end-member specifique par traceur ?
- Comment encoder proprement, dans les futurs YAML locaux Holten, les
  conventions de normalisation retenues pour `kr85` et `39Ar` ?
- Comment cadrer plus tard un pretraitement specifique pour `3He_trit_TU`,
  `He4_terr` et les corrections associees ?
- Quels ecarts semiquantitatifs faudra-t-il rapporter prioritairement par puits
  par rapport a `calibration_results.txt` ?
- Comment injecter proprement un repertoire de traceurs Holten entierement
  autonome dans le launcher sans alourdir les autres exemples ?

## Premier jalon recommande

Le premier jalon d'implementation devrait rester etroit :

- choisir 3 puits contrastes ;
- utiliser `3H`, `kr85` et `39Ar` ;
- documenter explicitement les conversions d'unites ;
- rendre explicite la strategie `holten_only` pour les chroniques et
  parametrages de traceurs ;
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
- la strategie de traceurs Holten specifiques sera explicite et reproductible ;
- l'exemple inclura une visualisation pedagogique avant calibration ;
- les sorties comprendront une comparaison aux resultats publies ;
- l'ecart entre observations supportees et observations differees sera clairement
  explique.

## Prochaines enrichissements utiles de ce document

Les prochains ajouts utiles seraient :

- figer plus finement la nomenclature finale du premier LPM concret derive de
  `n_bin_old` ;
- preciser comment les futurs YAML locaux `holten:` seront effectivement lus
  sans casser les configurations existantes ;
- cadrer les indicateurs de comparaison a rapporter en priorite puits par puits
  contre `calibration_results.txt` ;
- figer le branchement exact entre `run_holten.py`, `prepared_tracers` et le
  launcher ;
- preparer une table de renvoi stable entre sections du futur notebook et
  figures/tableaux de l'article ;
- confirmer les noms exacts des fichiers de sortie une fois la premiere
  implementation lancee.

## Mode de travail pour la suite

La suite de ce document peut etre construite par echanges successifs, en
fixant progressivement les choix qui demandent une decision scientifique ou
pratique.

Ordre logique recommande pour ces echanges :

1. preciser le futur chargement des YAML locaux Holten et la sous-section
   `holten:` ;
2. cadrer la validation article par article et puits par puits ;
3. figer les conventions de sortie du benchmark et du notebook ;
4. revenir ensuite sur l'implementation du premier LPM concret derive de
   `n_bin_old` ;
5. revenir enfin, si utile, sur les extensions futures autour de l'helium.

Tant que ces points ne sont pas stabilises, il vaut mieux garder le document au
niveau cadrage et ne pas figer de structure d'implementation trop precise.

## Notes

- Le depot contient deja des traceurs `3H`, `kr85` et `39Ar`.
- Ce brouillon ne decide pas encore des details d'implementation.
- Ce brouillon n'ajoute ni script, ni configuration, ni donnees converties.
