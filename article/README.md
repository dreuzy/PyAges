# Couche de reproductibilité du manuscrit PyAges 1.0

> **Identité de version.** La campagne fraîche utilise la version logicielle et
> le tag exacts `1.0`. Le préflight exige que ce tag pointe sur le commit propre
> exécuté et les manifestes frais enregistrent aussi son SHA Git. Les manifestes
> historiques conservent volontairement `requested_stable_tag: null` : ils
> décrivent des calculs antérieurs et ne doivent pas être réécrits.

Ce répertoire est une couche d'accès aux calculs du manuscrit. Il ne contient
ni copie du code scientifique de `pyages`, ni copie des données distribuées de
`data_core`, ni lien symbolique. Les résultats historiques restent à leur
emplacement canonique sous `results/` et sont décrits par les manifestes de cas.

Les preuves éditoriales sont regroupées sous `article/audit/`. Les instantanés
qui ne décrivent plus l'état courant sont datés sous `article/archive/` ; ils
restent versionnés pour la provenance mais ne constituent pas des instructions
actives.

Pour recalculer l'ensemble avec la version stabilisée, utiliser le lanceur
global et un dossier extérieur au dépôt :

```powershell
$env:PYTHONNOUSERSITE = "1"
python -m scripts.reproduce_article preflight --output C:\pyages-runs\article-1.0
python -m scripts.reproduce_article resume --output C:\pyages-runs\article-1.0 --workers 6
python -m scripts.reproduce_article validate --output C:\pyages-runs\article-1.0
```

Ce parcours est la référence pour une nouvelle archive GMD. Il ne dépend pas
des anciens dossiers `results/HYP-26-0172`; ceux-ci ne servent, le cas échéant,
qu'à une comparaison historique distincte.

Le tag `1.0` doit être annoté, immuable et présent sur `HEAD` avant la campagne
canonique. `--allow-dirty` et `--allow-untagged` sont réservés aux contrôles de
développement et ne doivent jamais être utilisés pour le dépôt final.
Le préflight exige également `PYTHONNOUSERSITE=1` afin qu'aucun paquet Python
installé au niveau utilisateur ne puisse masquer l'environnement qualifié.

| Manuscript section | Case | Main output | Reproduce |
| --- | --- | --- | --- |
| Section 3 / Supplement S1 | `s3_forward_verification` | Supplement S1 | `python article/run_case.py run s3_forward_verification` |
| Section 3.1 / Supplement S2 | `s3_1_tracerlpm` | Table 3, Supplement S2 | `python article/run_case.py run s3_1_tracerlpm` |
| Section 3.2 | `s3_2_shifted_exponential` | Figure 2, Table 4 | `python article/run_case.py run s3_2_shifted_exponential` |
| Section 4.1 | `s4_1_holten` | Figure 3 | `python article/run_case.py run s4_1_holten` |
| Section 4.2 | `s4_2_ploemeur` | Figure 4 | `python article/run_case.py run s4_2_ploemeur` |
| Robustness | `holten_prior_dirichlet1` | Prior-sensitivity figure and tables | `python article/run_case.py run holten_prior_dirichlet1` |

## Interface commune

Depuis la racine du dépôt :

```powershell
python article/run_case.py list
python article/run_case.py check s3_2_shifted_exponential
python article/run_case.py postprocess s3_2_shifted_exponential
python article/run_case.py run s3_2_shifted_exponential
```

Pour redessiner uniquement les figures après une campagne externe terminée,
sans appeler ni prolonger un sampler :

```powershell
python article/common/postprocess_existing.py s3_2_shifted_exponential --campaign-root C:\pyages-runs\article-1.0
python article/common/postprocess_existing.py s4_1_holten --campaign-root C:\pyages-runs\article-1.0
python article/common/postprocess_existing.py s4_2_ploemeur --campaign-root C:\pyages-runs\article-1.0
```

L'option `--output` accepte aussi directement le dossier existant d'un cas.
Pour la sensibilité au prior, fournir en plus `--canonical-holten` si la
campagne Holten canonique se trouve hors de l'arborescence historique.

`check` ne lance aucun code scientifique. `postprocess` exige que les chaînes
ou sorties brutes existent déjà et refuse de les créer ou de les prolonger.
`run` est la seule action autorisée à lancer un calcul complet et affiche un
avertissement de durée avant exécution. Les campagnes individuelles sont
écrites par défaut sous le dossier externe `pyages-article-results` voisin du
dépôt (modifiable par `PYAGES_ARTICLE_RESULTS_DIR`) afin de ne pas réutiliser ni
écraser les résultats canoniques.

Les garde-fous communs sont regroupés sous `article/common/` :

- `postprocess_existing.py` exige toutes les chaînes historiques et n'appelle
  aucun pilote, sampler ou prolongement ;
- `verify_forward.py` résume les lignes forward existantes sans recalculer
  l'opérateur ;
- `run_full.py` impose un nouveau dossier horodaté et refuse explicitement la
  relance non portable du cas TracerLPM/Excel.

Le registre machine-readable est `article/cases.yaml`. Les divergences de
checksum signalées par `check` sont attendues si le code de travail a évolué
depuis le commit du calcul ; elles ne doivent jamais être « corrigées » en
réécrivant rétroactivement un manifeste historique.

Le bilan consolidé de la campagne finale est conservé dans
[`reports/final_article_simulations_status.md`](reports/final_article_simulations_status.md).

## Code Git et archive scientifique

Les résultats volumineux ne doivent pas être ajoutés au dépôt Git. En revanche,
tout résultat nécessaire pour recalculer une figure, une table, un résidu, un
intervalle ou un diagnostic publié doit être présent dans une archive
scientifique immuable et identifiée par une version ou un DOI. Cela inclut les
états retenus de chaque chaîne MCMC, avec les répétitions dues aux rejets, ainsi
que les identifiants de chaîne, seeds, états initiaux, proposals et diagnostics.

Git conserve le code, les configurations, les manifestes de cas et le pointeur
exact vers cette archive. Le manifeste éditorial doit enregistrer, pour chaque
partie externe, son URL pérenne, sa taille et son SHA-256. Les caches, essais
abandonnés et rendus dupliqués qui ne soutiennent aucune affirmation publiée ne
font pas partie des preuves obligatoires.
