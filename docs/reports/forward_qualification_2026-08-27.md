# Qualification numérique forward du 27 août 2026

## Décision

Le contrat de qualification forward est désormais explicite, versionné et
exécutable. Avec les réglages de grille par défaut et avec les deux réglages
plus stricts, **270/270 cas passent**. Le verdict multi-résolution est
`qualified`.

Cette exécution valide l'implémentation dans le répertoire externe
`C:\pyages-runs\forward-qualification-v1`. Elle ne réécrit pas la campagne
`article-v1` ni son archive : celles-ci restent des preuves figées dont le
résumé forward porte encore l'ancien statut `measured_not_yet_qualified`.
L'intégration au livrable de publication devra être faite par une nouvelle
campagne propre, pas par modification rétroactive des empreintes.

## Contrat version 1

Pour chaque historique d'entrée, on définit

\[
C_\mathrm{scale}=\max_t |C_\mathrm{entrée}(t)|.
\]

Les cinq historiques actuels ont une amplitude voisine de 100 unités.

Pour une concentration significative,

\[
\max(|C_\mathrm{PyAges}|,|C_\mathrm{ref}|)
\ge 10^{-3} C_\mathrm{scale},
\]

le cas passe si la différence relative symétrique absolue est inférieure ou
égale à `5e-4`, soit **0,05 %** :

\[
\left|
\frac{2(C_\mathrm{PyAges}-C_\mathrm{ref})}
{|C_\mathrm{PyAges}|+|C_\mathrm{ref}|}
\right| \le 5\times10^{-4}.
\]

Sous cette frontière, le cas est proche de zéro et passe si

\[
|C_\mathrm{PyAges}-C_\mathrm{ref}|
\le 2\times10^{-5} C_\mathrm{scale}.
\]

Chaque résultat doit aussi être fini, non négatif à la tolérance d'arrondi
près et ne pas dépasser l'amplitude de l'entrée. Le verdict global exige que
**tous** les cas passent ; aucune moyenne ne peut masquer un échec individuel.
Les valeurs sont définies sous `forward_qualification` dans
`validation/tracerlpm/benchmark/configs/campaign.yaml`.

## Pourquoi ces seuils en première passe

La frontière à `1e-3` de l'amplitude isole les sorties dont la petite valeur
rend un pourcentage instable : elle place 33 cas sur 270 dans le régime absolu.
Le plafond relatif de `5e-4` laisse une marge d'environ 2,3 sur le maximum
observé à la grille par défaut (`2,14993e-4`). Le plafond absolu de `2e-5` de
l'amplitude laisse une marge d'environ 1,8 sur le maximum proche de zéro.

Ces marges restent discriminantes : les grilles volontairement relâchées de
facteurs 2 et 4 échouent respectivement sur 12 et 24 cas. Il s'agit donc d'une
première barrière de non-régression numérique, pas d'une incertitude physique
ni d'une borne d'erreur universelle. Toute modification future doit augmenter
la version du contrat, être décidée avant la campagne correspondante et être
réévaluée sur l'étude multi-résolution complète.

## Résultats multi-résolution

Les facteurs inférieurs à 1 resserrent la tolérance de construction de la
grille. Le facteur 1 et les grilles plus strictes conditionnent le verdict. Les
facteurs plus lâches sont volontairement informatifs : leur échec montre que
le test sait détecter une résolution devenue insuffisante.

| Facteur de grille | Requis | Cas conformes | Échecs | Statut |
| ---: | --- | ---: | ---: | --- |
| 4 | non | 246 | 24 | `failed_qualification` |
| 2 | non | 258 | 12 | `failed_qualification` |
| 1 | oui | 270 | 0 | `qualified` |
| 0,5 | oui | 270 | 0 | `qualified` |
| 0,25 | oui | 270 | 0 | `qualified` |

Au réglage par défaut :

- 237 cas sont dans le régime significatif et 33 dans le régime proche de
  zéro ;
- l'écart relatif symétrique significatif maximal vaut `2.14993e-4`, soit
  **0,0215 %** ;
- l'écart absolu proche de zéro maximal vaut `1.09216e-3` ;
- le cas le plus proche de sa limite consomme 54,6 % du budget autorisé.

Le maximum relatif brut de 8 % observé auparavant correspond à environ
`0,01310` contre `0,01419`. Il est correctement évalué dans le régime absolu :
son écart de `0,001092` reste inférieur au seuil d'environ `0,002`.

## Traçabilité

- base Git au moment de l'essai :
  `6be608508110009ed98be07d1cc8672f7479533b` avec arbre de travail non propre ;
- SHA-256 du `case_results.csv` au facteur 1 :
  `33DB81C2551AE9D86D361E53BDB0D12C9CE6F22E5DCE0C408392B8163B8E4628` ;
- SHA-256 du résumé multi-résolution :
  `F24341DADB2DC568F415E2CB3CDADD9EE818AD64189D1702ED7F7B22ADD50C28` ;
- SHA-256 du tableau de convergence :
  `5309485D2D625F8048A0199161461C9D3826320F84748E337F06EA6E0F5CDADE`.

L'arbre non propre interdit de traiter ce dossier comme l'archive finale de
publication. Les résultats numériques sont reproductibles et couverts par les
tests ; la prochaine campagne exécutée depuis un commit propre devra les
incorporer au paquet et à l'archive immuable.
