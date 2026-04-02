# Audit des notebooks et des figures

## Perimetre

Audit realise sur les elements suivants :

- `examples/natural/ploemeur/exemple_ploemeur.ipynb`
- `examples/natural/ploemeur_temporal/exemple_ploemeur_temporal.ipynb`
- `examples/natural/ploemeur/run_ploemeur.py`
- `examples/natural/ploemeur_temporal/run_ploemeur_temporal.py`
- `scripts/launcher.py`
- `scripts/launcher_temporal.py`
- les fonctions de trace utilisees par ces exemples

L'objectif de cette note est de regarder ces exemples du point de vue d'une personne qui debute avec PyAge, sans proposer de modification de code a ce stade.

## Synthese

Les deux notebooks ne jouent pas encore pleinement leur role de porte d'entree.

- `exemple_ploemeur.ipynb` parait ancien, tres bas niveau, et contient des cellules trompeuses ou peu utiles pour un debutant.
- `exemple_ploemeur_temporal.ipynb` est mieux structure, mais il reste centre sur l'infrastructure de lancement plutot que sur la lecture scientifique du resultat.
- Les figures actuelles privilegient des diagnostics exhaustifs plutot qu'un petit nombre de figures vraiment pedagogiques.
- Les titres, etiquettes et legendes utilisent souvent des noms internes de fichiers ou de colonnes, ce qui degrade fortement la lisibilite.
- Le cas temporal produit beaucoup trop de figures si on passe par le lanceur script. Avec la configuration courante, on arrive a environ `198` PNG, dont `174` figures de concentrations 2D peu didactiques.

En premiere intention, je viserais :

- pour `ploemeur` : `4` a `6` figures maximum par defaut
- pour `ploemeur_temporal` : `1` figure de donnees + `1` figure d'ajustement par LPM + `1` figure de synthese des parametres, avec les figures exhaustives releguees en mode avance

## Constats detailles

## 1. Notebook `examples/natural/ploemeur/exemple_ploemeur.ipynb`

### Points positifs

- Le notebook couvre bien les grandes etapes du workflow : donnees, espace atteignable, calibration, fonction objectif.
- Le cas d'etude est petit, donc il se prete bien a un notebook d'introduction.

### Points qui penaliseront un debutant

#### 1. L'entree dans le notebook est trop technique

Des la premiere cellule utile, on expose :

- la detection du repo root
- la manipulation de `sys.path`
- plusieurs imports bas niveau

Cela arrive avant de dire clairement :

- quel est le probleme scientifique
- quelles sont les donnees
- ce qui sera produit a la fin
- quelles cellules un debutant doit vraiment modifier

Concretement, les cellules `1`, `4`, `5` et `7` donnent le sentiment qu'il faut comprendre l'architecture interne avant de pouvoir lancer l'exemple.

#### 2. Le notebook est heterogene et ressemble a un script decoupe en cellules

Signaux visibles :

- cellule markdown vide (`2`)
- cellule de debug backend (`23`)
- imports repetes (`matplotlib.pyplot` est importe plusieurs fois)
- commentaires anciens ou redondants
- alternance entre logique "notebook" et logique "script historique"

Pour un debutant, cela brouille le message principal : "quelles sont les 3 ou 4 etapes essentielles ?"

#### 3. Les parametres importants ne sont pas clairement separes des parametres experts

Aujourd'hui, le notebook expose tres tot :

- le nom du dataset
- le repertoire de sortie
- tous les flags d'affichage
- les details du Simplex
- les details du Metropolis-Hastings

Le probleme n'est pas qu'ils soient la. Le probleme est qu'ils sont tous au meme niveau.

En pratique, un debutant devrait voir d'abord un petit bloc "a modifier si besoin" :

- dataset
- annee
- LPM
- mode rapide / mode complet

Le reste devrait etre soit cache dans des helpers, soit regroupe dans une section "parametres avances".

#### 4. Les options d'affichage sont contradictoires

Les cellules `12` et `13` configurent l'affichage puis le reconfigurent tout de suite apres :

- `figure_save = True`, puis `False`
- `figure_close = False`
- changement implicite entre logique de sauvegarde et logique inline

Pour un debutant, il est tres difficile de savoir :

- si les figures seront seulement affichees
- si elles seront aussi sauvegardees
- dans quel repertoire final regarder

#### 5. La cellule finale censee montrer les resultats ne fait pas vraiment le travail didactique attendu

La cellule `33` annonce :

> "Resulting concentration chronicles of tracers and models"

Mais en pratique :

- `display_concentration_times(...)` est appelee sans `plot=True`
- et surtout `display.directory` a ete modifie dans la boucle de calibration de la cellule `27`

Resultat :

- le repertoire de travail n'est plus le repertoire racine des resultats
- la fonction va chercher les sorties dans un sous-arbre qui n'est pas celui attendu
- la figure finale la plus pedagogique n'est pas vraiment produite / visible dans le notebook

C'est un point important, car c'est justement la figure que le lecteur debutant attend a la fin.

#### 6. La cellule finale qui imprime le repertoire est trompeuse

La cellule `35` affiche `display.directory`, mais cette variable a ete mutee pendant la calibration. Le chemin affiche n'est donc plus un "results root" simple a comprendre ; c'est le dernier sous-dossier manipule par la boucle.

Pour un debutant, cela rend la navigation dans les sorties moins intuitive.

#### 7. Les figures de fonction objectif n'indiquent pas ou se trouvent les parametres calibres

La cellule `31` appelle :

```python
ss.objective_function_display()
```

Or l'outil de trace supporte deja un argument `lpm_results` pour superposer les points calibres. Cette information n'est pas utilisee ici.

Du point de vue pedagogique, il manque donc la reponse a la question naturelle :

> "Dans cette carte de fonction objectif, ou tombe la solution estimee ?"

## 2. Notebook `examples/natural/ploemeur_temporal/exemple_ploemeur_temporal.ipynb`

### Points positifs

- Le notebook a une vraie structure narrative.
- Les sections "scientific context", "what you should expect" et "data overview" vont dans la bonne direction.
- La figure "observations only" est une bonne entree en matiere.

### Points qui restent problematiques

#### 1. La partie la plus utile pour un debutant arrive trop tard

Avant de voir clairement les donnees et les resultats, le lecteur passe par :

- le root detection boilerplate
- les imports
- l'impression complete du YAML
- la validation Pydantic
- le dump complet des modeles de configuration

Pour un utilisateur debutant, c'est beaucoup d'infrastructure avant la premiere intuition scientifique.

Je pense qu'il faudrait inverser le rythme :

1. voir les donnees
2. comprendre ce qui va etre ajuste
3. lancer
4. interpreter
5. seulement ensuite montrer la structure interne du YAML si necessaire

#### 2. Le notebook duplique une bonne partie de la logique du lanceur

La cellule `24` contient une fonction `run_calibration(...)` assez longue, avec des details de calibration et de configuration qui ne sont pas indispensables dans un notebook d'introduction.

Cette duplication a deux effets negatifs :

- elle augmente fortement la quantite de code a lire
- elle rend plus difficile l'identification de ce qui est "important a comprendre" par rapport a ce qui est seulement "necessaire pour executer"

#### 3. La cellule de fin n'affiche pas explicitement les bonnes figures

La cellule `28` fait :

- une liste des PNG
- puis affiche les `2` premiers PNG trouves

Ce n'est pas assez didactique. Le notebook devrait afficher explicitement :

- la figure de donnees
- la figure d'ajustement temporel
- la figure de synthese des parametres

Sinon le lecteur peut finir sur une figure secondaire ou arbitraire.

#### 4. Le lien entre "donnees" et "resultats" reste perfectible

La figure de chroniques temporelles montre bien les observations et des courbes modele, mais :

- il n'y a pas de resume visuel unique du type "donnees observees vs enveloppe des modeles calibres"
- on affiche des spaghetti plots de plusieurs courbes, ce qui reste moins lisible qu'une mediane + bandes de credibilite
- la mise en page reste fixe en `2x2`, ce qui laisse un panneau vide pour `3` traceurs

#### 5. Le notebook lui-meme est plus propre que le script, mais l'exemple global reste incoherent sur les figures

Le notebook respecte `figures.concentrations_2d: false`.

En revanche, le lanceur `scripts/launcher_temporal.py` appelle quand meme :

```python
lpm_results.display_concentrations_dist(...)
```

meme quand `concentrations_2d` est desactive.

Effet concret observe avec la config courante :

- `58` figures de concentrations 2D par LPM
- `3` LPM
- donc `174` figures 2D qui dominent completement les sorties

Cela explique en grande partie l'impression "il y en a trop".

## 3. Audit des figures actuelles

## 3.1 Ce qui ne marche pas bien visuellement

### 1. Les titres utilisent des noms internes et non des titres de lecture

Exemples observes :

- `reachable_cfc11-2010_9_cfc113-2010_9`
- `objfun_of_dirac_double_0`
- `exp_shifted`

Ces titres sont utiles pour le developpement ou pour le nommage des fichiers, mais pas pour l'interpretation.

Un titre de lecture devrait ressembler a quelque chose comme :

- "Concentrations atteignables et observation - CFC11 vs CFC113"
- "Fonction objectif selon mu1 et mu2"
- "Ajustement temporel - exp_shifted"

### 2. Les etiquettes d'axes exposent des cles internes

Exemple tres visible sur le cas temporal :

- `cfc11_2005.435616438356_0`
- `cfc12_2005.435616438356_1`

Pour un debutant, ces etiquettes sont presque illisibles.

Il faut convertir ces noms internes en etiquettes utilisateur :

- `CFC11 (2005.44)`
- `CFC12 (2005.44)`
- ou mieux, eviter ces figures par defaut

### 3. Les legendes sont soit absentes, soit trop generiques

Problemes observes :

- certaines figures de type `hist_scatter` n'affichent pas la legende alors que des couches differentes existent
- des legendes du type `Metropolis_Hastings` n'expliquent pas le role visuel de la couche
- certaines figures gagneraient a distinguer clairement `donnees`, `espace atteignable`, `echantillons calibres`, `meilleur modele`

### 4. La hierarchie typographique est trop agressive

Les titres sont souvent enormes, tres gras, et prennent trop de place par rapport au contenu.

Effets visibles :

- une partie du titre domine l'image
- l'oeil ne sait pas ce qui est important
- sur certaines figures, la zone utile parait secondaire par rapport au texte

### 5. La palette et les conventions de couleurs sont peu pedagogiques

Problemes typiques :

- usage de colormap type `jet`, tres agressive pour lire une fonction objectif
- meme couleur rouge employee pour des usages differents selon les figures
- pas de convention stable pour distinguer donnees, modele, reference et posterior

### 6. Certaines figures montrent "trop de choses", mais pas la bonne chose

Exemples :

- les `58` figures `concentrations2D_*` du cas temporal
- les paires de parametres ou de concentrations produites par defaut

Ces figures ont une utilite de diagnostic expert, mais elles noient le message principal pour un debutant.

## 3.2 Ce qui manque aujourd'hui

### 1. Pour `ploemeur`, il manque une vraie figure "donnees vs modeles"

Le besoin formule est tres juste. Il manque une figure qui reponde visuellement a :

> "Ou se trouvent les donnees observees par rapport a l'espace des concentrations produites par le modele, et ou tombent les modeles calibres ?"

La figure la plus didactique serait, pour les trois paires de traceurs :

- fond clair : espace atteignable
- points plus fonces : echantillons calibres
- marqueur tres visible : observation
- optionnel : meilleur estimateur ou mediane posterior

Cela expliquerait en une image :

- ce qui est faisable
- ce qui est retenu par la calibration
- a quel point les donnees sont bien reproduites

### 2. Pour les cartes de fonction objectif, il manque le repere des solutions estimees

Les cartes de fonction objectif sont interessantes, mais elles ne montrent pas encore :

- la meilleure solution sur la grille
- les echantillons calibres
- le meilleur modele retenu

Pour un lecteur, la question la plus naturelle est :

> "Le minimum estime par la calibration se situe ou dans ce paysage ?"

Aujourd'hui, la figure ne repond pas clairement a cette question.

### 3. Pour le cas temporal, il manque une figure de synthese plus stable que les spaghetti plots

La figure de chroniques est utile, mais un debutant comprendrait mieux avec :

- la mediane du modele
- une bande `50 %`
- une bande `90 %`
- les observations superposees

Cela serait plus lisible que `10` courbes individuelles.

## Quantification des sorties observees

Avec les configurations actuelles :

- `ploemeur` produit environ `22` PNG
- `ploemeur_temporal` produit environ `198` PNG

Repartition observee :

- `ploemeur` : `3` figures reachable, `6` figures de parametres, `3` figures de concentrations 2D, `5` figures autour de la fonction objectif
- `ploemeur_temporal` : par LPM, `1` figure de chroniques, `4` a `6` figures de parametres, `58` figures de concentrations 2D, `2` a `3` figures de type objectif

Cette repartition n'est pas adaptee a une premiere prise en main.

## Propositions d'evolution

## 1. Repenser les notebooks en mode "parcours debutant"

### Cible pour `ploemeur`

Je proposerais un notebook en `5` blocs :

1. `But de l'exemple`
2. `Parametres a modifier`
3. `Chargement des donnees`
4. `Calibration`
5. `Comment lire les resultats`

Avec une annexe optionnelle :

6. `Diagnostics avances`

Le bloc `Parametres a modifier` ne devrait contenir que :

- dataset
- LPM
- resolution rapide / complete
- repertoire de sortie

Le reste devrait etre cache dans des helpers.

### Cible pour `ploemeur_temporal`

Je proposerais aussi un parcours en `5` blocs :

1. `Contexte et jeu de donnees`
2. `Configuration minimale`
3. `Apercu des observations`
4. `Lancement de la calibration`
5. `Interpretation des figures`

La validation YAML detaillee et les dumps complets de config pourraient aller dans une section "pour aller plus loin".

## 2. Definir un jeu de figures par defaut beaucoup plus reduit

### Jeu de figures recommande pour `ploemeur`

Je garderais par defaut :

1. `01_data_and_model_space.png`
2. `02_parameter_posteriors.png`
3. `03_objective_function_with_estimates.png`
4. `04_results_summary.png`

Et je releguerais en mode avance :

- les paires exhaustives de parametres
- les paires exhaustives de concentrations
- les coupes secondaires de la fonction objectif

### Jeu de figures recommande pour `ploemeur_temporal`

Par LPM, je garderais par defaut :

1. `01_observations_overview.png`
2. `02_temporal_fit.png`
3. `03_parameter_summary.png`

En option seulement :

- les paires de concentrations 2D
- les nuages de parametres exhaustifs
- les figures de diagnostic de type expert

## 3. Ajouter les deux figures didactiques manquantes

### Figure A. `Ploemeur - donnees vs espace atteignable vs posterior`

Contenu propose :

- `3` panneaux : `CFC11 vs CFC12`, `CFC11 vs CFC113`, `CFC12 vs CFC113`
- fond gris clair : ensemble des concentrations atteignables
- points couleur principale : echantillons calibres
- etoile noire : observation
- halo ou croix orange : meilleur modele

Ce serait probablement la figure la plus utile du notebook `ploemeur`.

### Figure B. `Fonction objectif avec parametres estimes`

Contenu propose :

- fond : carte ou contours de la fonction objectif
- petit nuage : echantillons calibres
- point distinct : meilleur point retenu
- optionnel : croix blanche au minimum de la grille

Objectif :

- relier la geometrie de la fonction objectif a la solution produite

## 4. Rendre les figures plus lisibles

### Regles simples a appliquer

- utiliser des titres interpretabiles et non les noms de fichiers
- ecrire les axes avec nom de traceur, unite et date lorsque c'est utile
- reduire nettement la taille des titres
- utiliser une palette stable : donnees, posterior, reference, optimum
- afficher des legendes explicites et courtes
- retirer les sous-graphiques vides
- preferer `constrained_layout` ou une mise en page equivalente

### Conventions visuelles recommandees

- donnees observees : noir
- espace atteignable : gris clair
- echantillons calibres : bleu
- meilleur modele / estimateur : orange
- fonction objectif : colormap perceptuelle sobre, pas `jet`

## 5. Mieux separer "mode debutant" et "mode expert"

Aujourd'hui, les memes notebooks essaient de faire a la fois :

- de l'introduction
- du diagnostic detaille
- du debuggage
- de la reproductibilite technique

Je recommande de separer clairement :

- un chemin principal tres court
- une annexe ou section avancee

Concretement :

- les cellules de debug sortent du flux principal
- les dumps complets de config deviennent optionnels
- les figures exhaustives deviennent des options desactivees par defaut

## Priorisation suggeree

## Priorite haute

- simplifier le debut des deux notebooks
- corriger le flux final de `ploemeur` pour produire une vraie figure finale interpretable
- ajouter la figure "donnees vs modeles" pour `ploemeur`
- ajouter les marqueurs des parametres estimes sur la fonction objectif
- reduire drastiquement les figures par defaut dans le cas temporal

## Priorite moyenne

- harmoniser les titres, axes, legendes et couleurs
- remplacer les spaghetti plots par mediane + enveloppes sur le temporal
- faire afficher explicitement les bonnes figures de fin dans les notebooks

## Priorite basse mais utile

- aligner davantage les notebooks sur des helpers communs pour eviter la duplication
- ajouter un mini README pour `examples/natural/ploemeur`
- nommer les sorties avec une numerotation pedagogique (`01_`, `02_`, `03_`)

## Conclusion

Le fond scientifique des exemples est bon, mais la mise en scene pedagogique n'est pas encore au niveau pour un debutant.

Le besoin principal n'est pas d'ajouter plus de contenu ; c'est au contraire de :

- montrer moins de choses
- montrer les bonnes choses
- mieux nommer ce qui est montre
- relier explicitement les figures aux questions que se pose le lecteur

Si tu veux, l'etape suivante logique serait de transformer cette note en plan d'action concret, fichier par fichier, avec une proposition de nouvelle table des cellules pour chaque notebook et une proposition de set de figures cible.
