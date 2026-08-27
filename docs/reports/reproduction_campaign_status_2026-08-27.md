# État de la reproduction de l'article au 27 août 2026

## Conclusion

Les deux couches de preuve sont désormais distinguées explicitement :

| Couche | Commande | Résultat observé | Rôle |
| --- | --- | --- | --- |
| inventaire historique | `python article/run_case.py check <cas>` | **0/6** preuves historiques disponibles localement | comparaison et traçabilité des campagnes des 20–22 août ; ce n'est pas le contrôle de la nouvelle campagne |
| campagne fraîche | `python -m scripts.reproduce_article validate --output C:\pyages-runs\article-v1` | **9/9** étapes valides, 87 artefacts du paquet et 3 046 fichiers d'archive vérifiés | contrôle canonique de présence, statut d'exécution et empreintes de la campagne complète |

L'échec des six anciens contrôles ne signifie donc pas que la nouvelle campagne
a échoué. Il signifie que le checkout ne contient pas les répertoires
`results/` et les versions de scripts auxquels les anciens manifestes font
référence.

L'historique reste utile pour comparer ancien et nouveau, expliquer une dérive
et conserver la généalogie des nombres publiés. Il n'est plus nécessaire comme
entrée, initialisation ou condition de réussite de la campagne fraîche. Il ne
faudrait exiger un contrôle historique à 6/6 que pour revendiquer la
récupération exacte, octet par octet, des campagnes antérieures.

## Fond du problème

Les anciens manifestes lient trois choses indissociables : un chemin sous
`results/`, une version précise du code et des empreintes SHA-256. Or :

1. `results/` est volontairement exclu de Git et les anciennes chaînes,
   pilotes, sorties Excel et certains manifestes ne sont pas présents dans ce
   checkout ;
2. les scripts scientifiques ont évolué depuis les anciens calculs, donc leurs
   empreintes ne peuvent plus correspondre aux manifestes historiques ;
3. recalculer aujourd'hui produit une nouvelle identité de campagne. Remplacer
   les anciennes empreintes par celles du code courant falsifierait la
   provenance au lieu de réparer l'historique ;
4. la commande `run_case.py check` était présentée trop largement, ce qui
   mélangeait disponibilité de l'ancien dépôt de résultats et validité de la
   nouvelle reproduction.

La correction saine consiste à conserver les manifestes historiques
immuables, à qualifier leur contrôle d'« inventaire historique », et à valider
la campagne fraîche avec son propre manifeste et ses propres empreintes.

## Ce qui a réellement été refait

La campagne externe `C:\pyages-runs\article-v1`, actualisée le 27 août 2026 à
08:42 CEST, contient les neuf étapes enregistrées avec un code retour nul. Le
manifeste conserve le commit d'exécution propre à chaque étape ; la préparation
du paquet et de l'archive a été faite au commit
`1d056705ca7e44d85c5522082bc4087f4c42f310`.

| Volet | Preuve fraîche | Interprétation |
| --- | --- | --- |
| vérification forward | 270 cas, sorties présentes | le résumé archivé conserve `measured_not_yet_qualified` ; le contrat ajouté ensuite qualifie 270/270 cas aux grilles 1×, 0,5× et 0,25× |
| PyAges–TracerLPM | 480 cas appariés ; 480 succès PyAges et 480 succès TracerLPM | campagne Excel externe refaite et enregistrée |
| shifted exponential | 19 cas | campagne fraîche exécutée ; diagnostics et chaînes présents |
| Holten H4 | 7 puits | campagne fraîche exécutée ; diagnostics et chaînes présents |
| Sensibilité Holten Dirichlet(1,1,1,1) | 7 puits × 5 chaînes | campagne distincte exécutée ; split-Rhat maximal 1,008687 et ESS minimal 909,7 |
| Ploemeur shifted exponential | 4 calibrations | campagne fraîche exécutée ; diagnostics et chaînes présents |
| Ploemeur IG physique | 6 ensembles | campagne fraîche exécutée ; diagnostics et chaînes présents |
| paquet éditorial | 87 artefacts | toutes les empreintes du manifeste de paquet sont valides |
| archive locale | 3 046 fichiers | tailles et empreintes du manifeste d'archive sont valides |

Cette validation est volontairement technique : elle démontre que les étapes
ont réussi, que les fichiers attendus existent et que les deux livrables
protégés par empreintes sont intègres. Elle ne transforme pas automatiquement
une mesure en conclusion scientifique. Chaque sortie conserve son propre
statut de qualification.

## Points restant distincts de la validation technique

- La sensibilité Holten au prior Dirichlet (`holten_prior_dirichlet1`) est
  désormais une étape distincte de la campagne complète. Ses chaînes,
  diagnostics, tables et Figure C1 sont archivés, sans remplacer les résultats
  Holten canoniques.
- Le seuil forward est maintenant défini et testé. Il n'est pas réinjecté dans
  la campagne archivée : une exécution externe distincte qualifie les 270 cas
  aux trois résolutions requises. Voir
  {doc}`forward_qualification_2026-08-27`.
- L'archive vérifiée est une archive locale. Elle n'est pas encore un dépôt
  externe immuable avec URL pérenne ou DOI.
- Le bundle et son brouillon de métadonnées sont prêts pour revue, mais le DOI
  Zenodo doit encore être réservé puis injecté avant publication.

## Corrections apportées par ce ré-audit

- `article/run_case.py check` annonce maintenant qu'il contrôle uniquement les
  preuves historiques et son verdict parle de disponibilité historique.
- `scripts.reproduce_article validate` fournit le contrôle canonique de la
  campagne fraîche, vérifie les étapes, puis recalcule les empreintes du paquet
  et de l'archive.
- La validation isolée d'une archive fonctionne désormais avec
  `python -m scripts.build_reproduction_archive --validate-only <archive>`,
  sans imposer des arguments de construction inutiles.
- La campagne complète inclut maintenant le cas Dirichlet comme sensibilité
  distincte et conserve explicitement la séparation avec Holten canonique.
- Le constructeur du dépôt Zenodo exige maintenant une archive dont le `scope`
  confirme la présence de la sensibilité Holten avant dépôt.

## État des commentaires et de la documentation

La documentation de code publique, les exemples de configuration et les pages
Sphinx disposent de tests de dérive. La recherche des marqueurs `TODO`,
`FIXME`, `XXX`, `HACK` et `#JR` ne trouve plus de note interne non résolue dans
le périmètre audité. Les deux `TODO` restants sont intentionnels : ils sont
injectés par `pyages/cli/templates/lpm_template.py` dans un squelette que
l'utilisateur doit précisément compléter.

Les rapports du 26 août ne sont pas supprimés ni réécrits : un bandeau les
identifie comme photographies historiques et renvoie vers ce rapport courant.
La documentation technique est donc cohérente et construit sans avertissement.
Elle n'est toutefois pas encore publiée : le DOI Zenodo doit être réservé et le
brouillon de métadonnées doit être relu avant la reconstruction finale avec ce
DOI.

## Reste à faire hors figures et manuscrit

1. Stabiliser les changements dans un commit propre pour le dépôt définitif.
2. Réserver le DOI Zenodo, relire créateurs, affiliations et DOI de l'article,
   puis reconstruire le bundle avec `--doi`.
3. Publier le ZIP et conserver les révisions d'exécution consignées étape par
   étape.

## Contrôles techniques de clôture

| Contrôle | Résultat |
| --- | --- |
| six inventaires historiques | 0/6, avec verdict explicite `HISTORICAL EVIDENCE UNAVAILABLE` |
| validation de la campagne fraîche | réussite : 9/9 étapes, 87 artefacts, 3 046 fichiers archivés |
| validation autonome de l'archive | réussite : 3 046 fichiers |
| suite Python complète | 696 passed, 5 skipped |
| tests ciblés du contrat forward après durcissement final | 14 passed |
| `ruff check .` | réussite |
| format des six fichiers Python de l'implémentation forward | réussite, 6/6 fichiers conformes |
| Sphinx HTML strict, 71 sources | réussite |
| Sphinx `linkcheck` strict | réussite |

Le contrôle de format de tout le dépôt signale encore 13 fichiers modifiés
dans des chantiers parallèles. Ils n'ont pas été repris ici afin de respecter
le périmètre de l'implémentation forward, l'exclusion des figures et du
manuscrit, et de ne pas concurrencer des actions déjà engagées.

Les rapports datés du 26 août restent utiles comme photographie de l'état
antérieur, mais leurs conclusions sur l'absence de campagne fraîche et de
paquet ont été dépassées par les faits ci-dessus.
