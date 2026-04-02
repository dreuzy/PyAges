# Notes Sur Le Choix Automatique Du Modele

Statut : sujet ouvert, document de discussion transverse.

Ce document ne propose pas une implementation immediate. Il vise a cadrer une
idee generale : aider automatiquement l'utilisateur a choisir une nature
plausible de modele de distribution des ages, avec Holten comme cas de travail
possible parmi d'autres.

## Objectif

Fournir, a terme, un mecanisme d'aide a la decision sur le choix du modele de
distribution a tester en priorite, sans presenter cette suggestion comme une
verite physique ou comme un remplacement de la calibration.

L'idee n'est pas de "deviner" le bon modele de maniere definitive, mais de :

- reduire l'espace de recherche initial ;
- expliciter les hypotheses suggerees par les donnees ;
- orienter une premiere campagne de calibration ;
- fournir un support pedagogique de discussion scientifique.

## Pourquoi c'est un sujet difficile

Le choix d'un modele de distribution depend souvent de plusieurs niveaux
d'information :

- forme qualitative des chroniques de traceurs ;
- coherence ou tension entre plusieurs traceurs ;
- presence d'une composante jeune, melangee ou ancienne ;
- contexte hydrogeologique du site ;
- comportement des ajustements obtenus sous plusieurs familles de modeles.

Autrement dit, il est peu probable qu'une simple regle unique suffise.

## Premiere piste : un systeme de recommandation plutot qu'un selecteur strict

Une approche raisonnable serait de produire un conseil de type :

- modeles a tester en priorite ;
- modeles plausibles en second rang ;
- modeles peu plausibles compte tenu des observations disponibles.

Cette sortie pourrait etre accompagnee d'arguments lisibles, par exemple :

- "presence probable d'une composante jeune marquee" ;
- "reponse trop etalee pour un Dirac simple" ;
- "signature compatible avec une distribution plus asymetrique" ;
- "discordance entre traceurs suggerant un melange ou une queue ancienne".

## Sources d'information mobilisables

Les recommandations pourraient, plus tard, s'appuyer sur plusieurs briques :

- la comparaison visuelle entre chroniques de recharge et observations ;
- les ages apparents derives des differents traceurs ;
- des indicateurs simples de dispersion entre traceurs ;
- des ajustements rapides sur quelques familles de modeles candidates ;
- des metriques de qualite d'ajustement ;
- des informations contextuelles renseignees par l'utilisateur.

## Niveaux possibles d'automatisation

### Niveau 1 : heuristiques explicites

Le systeme applique des regles simples et transparentes.

Exemples d'idees :

- si plusieurs traceurs indiquent une eau tres jeune, favoriser des modeles a
  masse proche des temps courts ;
- si les traceurs montrent une gamme d'ages large, favoriser des distributions
  etalees ;
- si les traceurs semblent incompatibles avec un modele unimodal simple,
  considerer des modeles melanges ou plus flexibles.

Avantages :

- tres interpretable ;
- facile a discuter scientifiquement ;
- risque de sur-apprentissage faible.

Limites :

- regles parfois trop grossieres ;
- forte dependance a l'expertise metier formalisee a la main.

### Niveau 2 : pre-screening quantitatif

Le systeme lance rapidement plusieurs familles de modeles avec des reglages
simples, puis classe ces familles sur des criteres de compatibilite.

Exemples de criteres :

- adequation aux observations ;
- robustesse des parametres ;
- stabilite des solutions ;
- capacite a reproduire plusieurs traceurs en meme temps.

Avantages :

- base sur des sorties calculees plutot que sur des regles seulement ;
- deja plus proche de la pratique de calibration.

Limites :

- plus couteux ;
- sensible aux reglages du pre-screening ;
- peut biaiser la suite si les criteres sont mal choisis.

### Niveau 3 : systeme hybride

Combiner :

- une lecture heuristique amont,
- une visualisation hors modele,
- puis un pre-screening rapide multi-modeles.

C'est probablement la piste la plus robuste a discuter.

## Ce que l'on pourrait viser dans Holten

Holten est un bon cas pour discuter ce sujet, car :

- plusieurs traceurs sont disponibles ;
- des chroniques locales peuvent changer l'interpretation ;
- des resultats de reference existent deja ;
- plusieurs puits permettent de comparer des signatures distinctes.

Un objectif raisonnable serait d'obtenir, pour chaque puits :

- une recommandation argumentee de familles de modeles a tester ;
- un indicateur de confiance faible, moyen ou fort ;
- un rappel des raisons physiques ou numeriques de cette suggestion ;
- une comparaison a posteriori entre la recommandation initiale et le modele qui
  ajuste effectivement le mieux les observations.

## Questions de fond a discuter

- Sur quelles variables faut-il fonder le conseil :
  observations brutes, ages apparents, ou les deux ?
- Faut-il raisonner puits par puits, ou aussi a l'echelle du site ?
- Comment tenir compte du choix chronique locale vs chronique commune ?
- Comment eviter de sur-vendre une suggestion fragile ?
- Faut-il recommander une famille de modeles ou plusieurs familles classees ?
- Comment mesurer la "bonne" recommandation :
  par le meilleur ajustement, par la robustesse, par l'interpretabilite ?

## Forme possible d'un futur livrable

Plus tard, ce sujet pourrait donner lieu a :

- une note methodologique ;
- une commande de diagnostic amont ;
- une sortie de rapport avant calibration ;
- une comparaison systematique entre recommandation et calibration finale.

## Position recommande a ce stade

Pour l'instant, la bonne posture est :

- documenter le sujet ;
- ne rien automatiser trop vite ;
- commencer par la visualisation hors modele ;
- observer quels motifs ressortent reellement sur Holten ;
- seulement ensuite discuter des regles ou indicateurs a formaliser.

## Conclusion provisoire

Le choix automatique du modele de distribution est une piste utile, mais il
doit etre traite comme un outil d'aide a la discussion scientifique, pas comme
une boite noire de selection definitive. Le cas Holten peut servir de terrain
de travail pertinent pour construire cette reflexion.
