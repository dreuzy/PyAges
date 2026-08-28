# Exigences logicielles, matérielles et documentation

## Verdict

`NEEDS AUTHOR INPUT` pour la nomenclature de release et `BLOCKER` pour l'incohérence du gel SciPy. Le reste est `CONFIRMED`.

## Python et version PyAge

- Compatibilité déclarée dans `pyproject.toml`: Python `>=3.12,<3.15`, donc 3.12, 3.13 et 3.14.
- Interpréteur réellement enregistré par les manifests des analyses MCMC de l'article: Python 3.12.4.
- La version logicielle actuelle dans `pyage/_version.py` est `0.1.0b1` et le classificateur est encore «Beta». Elle ne s'identifie pas comme `1.0`/`v1.0`. L'auteur doit décider si «PyAge v1.0» désigne le manuscrit/protocole ou une future version logicielle, puis aligner version, tag et texte ultérieurement.

## Dépendances

Le fichier canonique des plages de compatibilité est `pyproject.toml`:

- NumPy `>=2,<3`;
- SciPy `>=1.13,<2`;
- pandas `>=2.2,<4`;
- Matplotlib `>=3.9,<4`;
- PyYAML `>=6,<7`;
- Click `>=8.3.3,<9`;
- Pydantic `>=2.9,<3`.

Les manifests des campagnes shifted, Holten, prior et Ploemeur enregistrent NumPy 2.1.2, SciPy 1.14.1 et pandas 2.2.3. Le rapport historique forward enregistre aussi Matplotlib 3.10.8.

`install/constraints.txt` est le gel portable prévu pour la reproduction actuelle: NumPy 2.5.2, SciPy 1.18.1, pandas 3.0.5, Matplotlib 3.11.1, PyYAML 6.0.3, Click 8.4.2 et Pydantic 2.13.4, plus les versions des outils de développement/docs/exemples. Le même fichier est copié dans le paquet d'article externe.

`BLOCKER`: `install/environment.yml` épingle SciPy 1.18.0, alors que `install/constraints.txt` et `install/README.md` affirment que les versions directes sont identiques et épinglent SciPy 1.18.1. Il faut choisir et qualifier une seule version avant de figer la section de disponibilité.

Ces fichiers sont des gels de dépendances directes, pas un lock complet des dépendances transitives. L'archive candidate existante contient aussi un `pip freeze`, mais l'audit final de release est volontairement différé.

## Matériel

- Le moteur PyAge et les campagnes article sont CPU-only; aucune dépendance GPU/CUDA et aucun GPU ne sont requis.
- Un seul CPU suffit fonctionnellement. Les campagnes parallélisent les chaînes/cas par processus; le lancement externe a utilisé `--workers 6` pour shifted et TracerLPM. Ploemeur choisit normalement jusqu'à cinq workers/chaînes. Ce sont des choix de débit, pas un minimum matériel.
- Les manifests ne consignent ni modèle de CPU, ni nombre de cœurs physiques, ni mémoire maximale ou typique. Aucune valeur de RAM ne peut être annoncée.
- PyAge seul ne nécessite aucun matériel spécialisé. La reproduction croisée TracerLPM nécessite en revanche Windows, Microsoft Excel 64 bits, le classeur macro qualifié et l'add-in XLL 64 bits. Ce besoin appartient au benchmark externe, pas à la bibliothèque PyAge.

## Manuel utilisateur

Le manuel est la documentation Sphinx/MyST «PyAge documentation», dont la section utilisateur commence à `docs/user-guide/index.md`; les sources sont en Markdown sous `docs/user-guide/`. La construction HTML canonique est `python -m sphinx -b html docs docs/_build/html`.

Les sources `docs/` sont suivies par Git et entrent donc dans le `pyage-source.zip` produit par `scripts/release/build_reproduction_archive.py` via `git archive`. Elles ne sont pas déclarées comme données du wheel dans `pyproject.toml`, et `MANIFEST.in` n'inclut pas explicitement `docs/`; il ne faut donc pas affirmer que le manuel HTML est installé avec le paquet Python. L'archive de reproduction planifiée contient les sources, pas nécessairement un build HTML.

## Licence

`pyproject.toml` déclare `CECILL-2.1`. Le fichier `LICENSE` contient «CeCILL Version 2.1 du 2013-06-21». La version exacte est donc **CeCILL 2.1**.

## Sources de provenance

- `pyproject.toml`, `pyage/_version.py`, `install/constraints.txt`, `install/environment.yml`, `install/README.md`
- manifests sous `C:\pyage-runs\article-v1`
- `scripts/release/build_reproduction_archive.py`
- `docs/index.md`, `docs/user-guide/index.md`, `docs/conf.py`
- `LICENSE`
