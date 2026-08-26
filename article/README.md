# Couche de reproductibilité du manuscrit visant PyAge v1.0

> **Identité de version.** `v1.0` désigne ici la cible du manuscrit et de sa
> future archive, pas une version logicielle déjà publiée. La version bêta
> citable reste `0.1.0b1`. Tant que `requested_v1.0_tag` vaut `null` dans les
> manifestes, chaque calcul est identifié par son commit Git et son
> environnement enregistrés ; aucun DOI futur ne doit être anticipé.

Ce répertoire est une couche d'accès aux calculs du manuscrit. Il ne contient
ni copie du code scientifique de `pyage`, ni copie des données distribuées de
`data_core`, ni lien symbolique. Les résultats historiques restent à leur
emplacement canonique sous `results/` et sont décrits par les manifestes de cas.

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

`check` ne lance aucun code scientifique. `postprocess` exige que les chaînes
ou sorties brutes existent déjà et refuse de les créer ou de les prolonger.
`run` est la seule action autorisée à lancer un calcul complet et affiche un
avertissement de durée avant exécution. Les campagnes MCMC sont toujours
écrites dans un nouveau dossier horodaté sous `results/article_reproductions/`
(ou `results/robustness/reproductions/`) afin de ne pas réutiliser ni écraser
les résultats canoniques.

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
