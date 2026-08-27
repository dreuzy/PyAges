# Table 1 — écarts nécessitant une décision

Audit en lecture seule du 27 août 2026. Le code et le manuscrit n'ont pas été modifiés.

## Source manuscrit manquante

`PyAge_v1.0_revised_v28_code_audit_sync.docx` n'est présent ni dans `C:\Users\dreuzy\Downloads`, ni dans le dépôt `C:\codes\pyage`, ni dans les dossiers de campagne et archives de reproduction inspectés. La version PyAge la plus récente trouvée dans Downloads est `PyAge_v1.0_revised_v23_figures_updated.docx` (27 août 2026, 09:12:10). Elle n'a pas été utilisée comme substitut.

Conséquence : aucun nom, paramètre, unité, support, formule ou texte explicatif de la Table 1 v28 ne peut recevoir le statut `MATCH`. L'exhaustivité de la table est également indéterminable.

Décision requise : fournir le DOCX v28 exact, puis reprendre la comparaison ligne par ligne. Le gel scientifique de la Table 1 ne peut pas être approuvé sur ce rapport incomplet.

## Métadonnée `rate` du mélange Dirac + exponentielle

La classe `MixExponentialShiftedLpm` déclare correctement `rate` comme sans dimension dans `pyage/lpm/models/mix_exponential_shifted.py`. En revanche, `data_core/data_lpm/mix_exp_shifted/params.yaml` :

- omet le champ `unit` au niveau du paramètre `rate` ;
- déclare `prior.unit: year`, ce qui est dimensionnellement incorrect pour un poids de mélange borné entre 0 et 1.

Décision requise côté code, lors d'une tâche d'édition autorisée : renseigner l'unité dimensionless (`-`) pour le paramètre et son prior. Ce point est une `METADATA ISSUE`, pas une divergence de loi de probabilité.

## Métadonnée `rate` du double Dirac

`DiracDoubleLpm` utilise un poids dimensionless, mais le runtime le représente par une chaîne vide et le YAML omet le champ `unit` au niveau du paramètre, tandis que son prior porte `unit: "-"`.

Décision requise côté code, lors d'une tâche d'édition autorisée : uniformiser explicitement la représentation dimensionless. La précédente incohérence sensible de `mu2` n'existe plus dans le code courant : la classe et le YAML déclarent tous deux `mu2` en années, et les masses sont placées en `mu1` et `mu1+mu2`.

## Exhaustivité de Table 1

Le registre courant contient aussi `DiracDouble1SetLpm` (`dirac_double_1_set`), en plus des 11 familles citées dans le cahier d'audit. Sans la v28, il est impossible de déterminer si ce modèle est volontairement hors Table 1 ou si une ligne manque.

Décision requise : confirmer l'intention éditoriale à partir de la Table 1 v28.

## Conclusion

**Is Table 1 scientifically consistent with the current code? `NO — NOT ASSESSABLE`.** Aucun `SCIENTIFIC MISMATCH` n'a été démontré avec les éléments accessibles, mais `YES` est interdit tant que toutes les lignes ne sont pas comparées à la v28.
