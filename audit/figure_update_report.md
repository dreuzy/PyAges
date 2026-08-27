# Rapport de mise à jour des figures PyAges v1.0

Date du contrôle : 26 août 2026  
Commit inspecté : `8b6ea982e3bc2f85a22fa6f72155b4285bc260b3`

## Ajustement final de la Figure 3

La disposition finale reste strictement en 1 × 4 à 165 mm. L'espacement
horizontal entre panneaux a été porté de `0.12` à `0.18` et les ticks ont été
formatés de manière compacte (`0`, `0.5`, `1`). Les données, symboles, tailles
de police et la légende partagée sont inchangés. Les labels extrêmes de deux
panneaux adjacents ne se touchent plus. Le PNG 600 dpi, le PDF vectoriel et le
DOCX principal ont été actualisés.

## Clôture du 27 août 2026 — campagne, figures, Word et archive

La simulation Holten manquante a été exécutée sous
`C:\pyages-runs\article-v1\holten_prior_dirichlet1`, en réutilisant la campagne
Holten canonique en lecture seule. Les 35 chaînes attendues (7 puits × 5
chaînes) sont présentes. Les 49 groupes diagnostiqués passent les seuils
enregistrés : split-Rhat maximal `1.008687`, ESS minimal `909.7`, aucun groupe
en échec. L'intégrité des données scientifiques Holten canoniques est validée
contre leur manifeste.

La Figure C1 a ensuite été générée en PDF vectoriel et PNG 600 dpi, à 165 mm,
avec les libellés `Latent-logit uniform prior` et
`Dirichlet(1,1,1,1) fraction prior`, sans mention `H4`. Les Figures 1, 2, 3, 4
et C1 ont été insérées dans le manuscrit principal à leurs largeurs prévues et
avec des textes alternatifs scientifiques. Le supplément ne contient aucun
dessin et a été copié sans modification.

Livrables Word :

- `C:\Users\dreuzy\Downloads\PyAges_v1.0_revised_v23_figures_updated.docx` ;
- `C:\Users\dreuzy\Downloads\PyAges_v1.0_supplementary_material_v2_figures_updated.docx`.

Le paquet éditorial actualisé contient 87 artefacts vérifiés. La campagne
complète valide 9/9 étapes et l'archive contient 3 046 fichiers vérifiés. Le
bundle Zenodo actualisé contient 3 058 fichiers de charge utile et inclut la
sensibilité Dirichlet comme analyse distincte, sans la substituer aux résultats
Holten canoniques.

Contrôles de clôture : `696 passed, 5 skipped`, contrôles Ruff ciblés réussis,
DOCX valides, bundle Zenodo et ZIP revalidés contre leurs inventaires et
empreintes.

Livrables d'archive :

- `C:\pyages-runs\article-v1-gmd-archive` ;
- `C:\pyages-runs\pyages-0.1.0b1-article-v1-reproduction` ;
- `C:\pyages-runs\pyages-0.1.0b1-article-v1-reproduction.zip`.

## Exécution du 27 août 2026 — post-traitement des sorties finales

Le post-traitement a été exécuté sur la campagne terminée
`C:\pyages-runs\article-v1`. Aucun sampler ni calcul scientifique lourd n'a été
relancé.

| Figure | Résultat | Contrôles |
| --- | --- | --- |
| Figure 1 | réexportée depuis la source Mermaid en SVG, PDF et PNG | PDF vectoriel de 110 mm, Arial incorporé ; PNG 600 dpi |
| Figure 2 | réexportée en 100, 110 et 120 mm ; version finale retenue à 110 mm | 2598 × 1974 px à 600 dpi ; PDF vectoriel de 110 mm avec police incorporée ; libellés et cible contrôlés |
| Figure 3 | réexportée en 1 × 4 et variante 2 × 2 | version finale de 165 mm ; 3897 × 1842 px à 600 dpi ; absence de `H4`, `q10` et `q90` contrôlée |
| Figure 4 | réexportée en six panneaux | 165 mm ; 3897 × 2645 px à 600 dpi ; terminologie `2014–2015-only calibration` contrôlée |
| Figure C1 | non réexportée | les tables `holten_prior_robustness_fractions.csv` et `posterior_summaries_dirichlet1.csv` sont absentes de `C:\pyages-runs` et des emplacements canoniques locaux |

Les sorties C1 n'ont pas été reconstruites depuis une ancienne image et aucune
valeur n'a été complétée manuellement. En conséquence, l'intégration Word
définitive reste suspendue : remplacer seulement les Figures 1–4 laisserait une
ancienne Figure C1 comportant encore la terminologie à supprimer.

## Mise à jour du 27 août 2026 — code de post-traitement préparé

Les fonctions de rendu des Figures 2, 3, 4 et C1 ont été mises à jour sans
lancer de simulation. Elles relisent les chaînes ou tables finales existantes,
appliquent une typographie sans-serif de 8,5 pt minimum, puis exportent des PDF
et PNG à 600 dpi. Les noms historiques sont conservés comme alias pour le
paquet d'article.

Le post-processeur accepte désormais soit `--output` pour un cas, soit
`--campaign-root` pour une campagne externe produite par
`scripts.reproduce_article`. Il vérifie la présence des chaînes avant toute
opération et n'appelle aucun sampler.

- Figure 2 : variantes 100, 110 et 120 mm ; alias final réglé sur 110 mm.
- Figure 3 : version finale 1 × 4 à 165 mm et variante de repli 2 × 2.
- Figure 4 : six panneaux à 165 mm et terminologie
  `2014–2015-only calibration`.
- Figure C1 : terminologie explicite des deux priors, sans mention `H4`.
- Figure 1 : source Mermaid réglée sur une police sans-serif de 18 px, soit plus
  de 9 pt à la largeur d'insertion actuelle ; ses exports restent à régénérer.

Les tests de rendu synthétiques passent. Les figures scientifiques et les DOCX
restent à produire lorsque les sorties lourdes seront disponibles.

## Statut initial du 26 août 2026

**Bloqué avant régénération.** Aucun résultat scientifique, aucune figure et
aucun document Word n'ont été modifiés.

Les documents source ont été retrouvés sous Windows :

- `C:\Users\dreuzy\Downloads\PyAges_v1.0_revised_v23_approved_edits.docx`
  (SHA-256 `2E814180F7E619DFCD7446DA517975E49BA765414386BFFBE9BA2E9EA9E3E501`) ;
- `C:\Users\dreuzy\Downloads\PyAges_v1.0_supplementary_material_v2_restructured.docx`
  (SHA-256 `CFCB100D343A3B7C091C2213540B80841C30C73A8C53700C04EFEA4660705B3F`).

Le chemin Linux demandé, `/mnt/data`, n'est pas monté dans cet environnement.

## Figures et scripts contrôlés

| Figure | Script canonique identifié | Données de redessin requises | Résultat |
| --- | --- | --- | --- |
| Figure 2 | `scripts/run_final_shifted_exponential.py` | chaînes finales du cas `(mu, t0) = (10, 30)` et grille `sqrt(J/4)` | absentes |
| Figure 3 | `scripts/run_final_holten_h4.py` | `visser_vs_pyages_h4.csv` ou `posterior_summaries.csv` final | absentes |
| Figure 4 | `scripts/run_ploemeur_shifted_exponential_final.py` | `figure4_prediction_intervals.csv` ou prédictions row-wise finales | absentes |
| Figure C1 | `scripts/run_holten_prior_robustness.py` | `holten_prior_robustness_fractions.csv` et résumés finaux des deux priors | absentes |
| Figure 1 | `docs/figures/figure1_overview.md` et `figure1_overview.svg` | aucune donnée scientifique | source scriptée présente ; non régénérée dans ce lot bloqué |

Les manifestes versionnés pointent vers des artefacts sous
`results/final_article_simulations/` et `results/robustness/`, mais ces
répertoires de campagne ne sont pas présents dans la copie de travail et leurs
artefacts ne figurent pas dans Git. Les artefacts GitHub disponibles sont
limités à la documentation, aux distributions et à la couverture ; aucun
paquet de résultats scientifiques n'y est publié.

Un ancien jeu `C:\Users\dreuzy\results\PyAges\manuscript_figure2` est présent,
mais il provient du lanceur historique à chaîne unique
`scripts/reproduce_manuscript_figure2.py`. Il n'a pas été utilisé, car la
mission exige les cinq chaînes finales convergées.

Les PNG intégrés au DOCX v23 montrent bien les figures finales antérieures,
mais ne constituent pas les tables ou posteriors canoniques nécessaires au
redessin. Les numériser à partir des pixels introduirait des valeurs
approximatives et violerait l'interdiction de modifier les résultats à la main.

## Décisions de mise en page

- Largeur finale de la Figure 2 : **non déterminée** (versions 100/110/120 mm
  non générées).
- Disposition finale de la Figure 3 : **non déterminée** (1 × 4 non régénérée,
  variante 2 × 2 non testée).
- Les contrôles PDF de polices, troncatures et superpositions n'ont pas pu être
  exécutés faute de figures régénérées.

## Livrables Word

Les fichiers suivants n'ont volontairement pas été créés, afin de ne pas
présenter comme mis à jour un document contenant encore les anciennes figures :

- `PyAges_v1.0_revised_v23_figures_updated.docx` ;
- `PyAges_v1.0_supplementary_material_v2_figures_updated.docx`.

## Élément nécessaire pour reprendre

Restaurer le paquet éditorial indiqué dans
`article/reports/final_article_simulations_status.md`, ou au minimum les tables
et posteriors listés ci-dessus, sous leurs chemins canoniques. La reprise pourra
alors être faite en post-traitement uniquement, sans relancer les campagnes
MCMC et sans modifier aucune valeur scientifique.
