# TracerLPM Runner — preuve de concept Visual Studio

Ce projet Windows pilote TracerLPM dans Excel depuis une application .NET 8 x64. Toutes les entrées sont en YAML, conformément aux configurations de PyAge. Le runner configure le classeur par ses contrôles ActiveX, exécute les macros nécessaires, lit les séries calculées et produit des rapports JSON, CSV et Markdown.

Le runner est autonome par rapport à PyAge : il ne dépend d'aucun code Python et n'en modifie aucun fichier.

Le protocole de comparaison scientifique est décrit dans
[`docs/pyage-tracerlpm-targeted-comparison.md`](../../docs/pyage-tracerlpm-targeted-comparison.md).
Le runner reste un adaptateur externe : les conversions PyAge et la logique de
comparaison ne doivent pas être ajoutées au code COM.

## État de la preuve de concept

Le parcours suivant est qualifié sur cette machine avec Excel Microsoft 365 64 bits :

- ouverture automatisée d'une copie du classeur TracerLPM ;
- chargement de Solver et du XLL TracerLPM 64 bits ;
- choix de l'échantillon, de deux modèles et des axes par leur libellé ;
- exécution des événements VBA attendus ;
- lecture de 61 couples pour chacun des deux modèles ;
- comparaison facultative avec des empreintes numériques SHA-256 ;
- configuration, cartographie et scénarios entièrement pilotés en YAML.

Cela démontre la faisabilité technique du pilotage de TracerLPM depuis une application Visual Studio. Ce n'est pas encore une qualification exhaustive de tous les modèles, classeurs et parcours Solver.

## Classeur quatre traceurs pour la validation

Le mode `--target` fabrique une copie isolée contenant les quatre traceurs naturels
retenus pour la comparaison : `CFC-11`, `CFC-12`, `CFC-113` et `SF6`. Il ne modifie
jamais le classeur qualifié indiqué dans la configuration source.

```powershell
.\src\TracerLpmRunner\bin\Release\net8.0-windows\TracerLpmRunner.exe `
  --config .\config\runner-config.local.yaml `
  --target C:\TracerLPM-Test\working\TracerLPM_V_1_0_FourTracers.xlsm
```

La préparation choisit explicitement les historiques `Northern Hemisphere` du
classeur TracerLPM. Elle appelle la routine VBA native `RetrieveTracerData` pour
l'interpolation. La grille est bornée à l'année 1800 : les concentrations des CFC
et du SF6 sont nulles avant cette date, de sorte que cette borne accélère la
préparation sans tronquer une entrée atmosphérique non nulle.

Après création, calculer le SHA-256 du nouveau classeur et le reporter dans une
configuration locale distincte, sur le modèle de
`config/runner-config.four-tracer.local.yaml`. Le hash verrouille exactement le
classeur utilisé pour les campagnes d'inversion.

## Arborescence

```text
config/
  runner-config.example.yaml modèle de configuration locale
  runner-config.local.yaml configuration locale non versionnée
  workbook-map.yaml        mapping versionné du classeur Excel
samples/
  cases.yaml               exemple qualifié, commenté
  cases-usgs-example1.yaml matrice PFM/EMM, EPM/PEM, DM/BMM
src/TracerLpmRunner/       application console C#
work/                      copies de travail, une par exécution
output/                    rapports par cas et consolidés
```

## Prérequis

- Windows avec Excel desktop 64 bits ;
- SDK .NET 8 pour compiler, ou l'exécutable déjà compilé ;
- Solver disponible dans Excel ;
- XLL TracerLPM 64 bits installé au chemin configuré ;
- macros et ActiveX autorisés pour le classeur selon la politique Office locale.

La copie qualifiée du classeur contient le contournement local pour Excel français : dix références VBA à `Solver Add-In` ont été remplacées par `Complément Solveur`.

## Compiler

Depuis `C:\codes\pyage\validation\tracerlpm` :

```powershell
dotnet build .\TracerLpmRunner.sln -c Release -p:Platform=x64
```

L'exécutable est créé ici :

```text
src\TracerLpmRunner\bin\x64\Release\net8.0-windows\TracerLpmRunner.exe
```

## Appeler le runner

Le runner accepte exclusivement YAML en entrée :

```powershell
.\src\TracerLpmRunner\bin\x64\Release\net8.0-windows\TracerLpmRunner.exe `
  --config .\config\runner-config.local.yaml `
  --cases .\samples\cases.yaml
```

Depuis Visual Studio, ouvrir `TracerLpmRunner.sln`, choisir la cible `x64`, puis définir les arguments de débogage :

```text
--config C:\codes\pyage\validation\tracerlpm\config\runner-config.local.yaml --cases C:\codes\pyage\validation\tracerlpm\samples\cases.yaml
```

Le code de sortie vaut `0` si tous les cas sont conformes, `1` en cas d'erreur ou de résultat invalide, et `2` n'est pas utilisé actuellement. Les résultats sont également écrits sur la sortie standard.

## Format des cas YAML

```yaml
- case_id: modesto-pfm-emm
  sample: PSW-1-17/08/2004
  model1: PFM
  model2: EMM
  x_axis: 3H/3Ho
  y_axis: SF6
  expected_model1_sha256: 2E14DA49ACB873C833A0FDFEBD23C26D6483498A7643C7B3DB3A90AB93946FB8
  expected_model2_sha256: 2834E84BFD505DEA2E0CC04EBC7A72FF1C756D50AC5ED14B2D10A7E8E71EECC3
```

YAML accepte les commentaires et suit la convention `snake_case` déjà utilisée par PyAge. Les extensions `.yaml` et `.yml` sont acceptées. L'identifiant, l'échantillon, les deux modèles et les deux axes sont obligatoires. Les deux hashes attendus sont facultatifs. Sans hash attendu, une série calculée est acceptée mais son empreinte reste enregistrée dans le rapport. Les libellés doivent correspondre aux valeurs proposées par le classeur, sans tenir compte des majuscules/minuscules.

## Configuration principale

Copier `config/runner-config.example.yaml` vers `config/runner-config.local.yaml`, puis renseigner les chemins locaux. Le fichier local contient :

- `workbook_path` et `xll_path` : fichiers réellement utilisés ;
- `workbook_sha256` et `xll_sha256` : empreintes impératives avant exécution ;
- `workbook_map_path` : cartographie adaptée à cette version précise du classeur ;
- `work_root` : répertoire des copies temporaires de travail ;
- `output_root` : répertoire des rapports ;
- `excel_visible` : affiche ou masque Excel ;
- `timeout_seconds` : délai maximal du recalcul Excel.

Les chemins relatifs fournis sur la ligne de commande sont résolus depuis le répertoire courant. Les chemins contenus dans la configuration actuelle sont absolus.

## Cartographie du classeur

`config/workbook-map.yaml` sépare le code C# de la structure interne d'Excel. Il décrit les feuilles, les noms des contrôles ActiveX, les macros d'événement et les plages à lire. Son `workbook_sha256` doit être identique à celui de la configuration : une autre version du classeur est refusée tant qu'une cartographie explicite n'a pas été créée et qualifiée.

Les plages `outputRanges.model1` et `outputRanges.model2` représentent les deux emplacements de modèles sur la feuille de sortie, pas des modèles PFM/EMM codés en dur. La cartographie actuelle n'est valide que pour le classeur dont elle porte le hash.

## Rapport produit

Chaque fichier `output/<runId>.json` contient notamment :

- `status` : `success` ou `invalid_output` ;
- les paramètres réellement demandés ;
- le nombre de points de chaque série ;
- les hashes des valeurs numériques calculées ;
- le résultat de la comparaison avec les hashes attendus ;
- les coordonnées de l'échantillon ;
- le hash du classeur et du XLL ;
- le chemin de la copie de travail et le PID Excel détenu ;
- les valeurs `x` et `y` de tous les points des deux séries.

Chaque cas produit aussi `<runId>-series.csv`, avec une ligne par point. À la fin du lot, le runner crée `simulation-report-<date>.json`, `.csv` et `.md` : ces trois fichiers consolident les statuts, paramètres, nombres de points, hashes et durées.

L'empreinte d'une série est calculée sur les nombres au format invariant et en double précision, séparés par `|`. Elle sert à détecter une variation exacte du résultat ; elle ne remplace pas une comparaison scientifique avec tolérance.

## Sécurité et isolation

- Le classeur source et le XLL sont validés par SHA-256 avant le lancement.
- Une nouvelle copie du classeur est créée pour chaque cas.
- Le classeur source n'est ni enregistré ni modifié.
- Les macros sont autorisées uniquement dans l'instance Excel créée par le runner.
- Le runner ne modifie pas le Centre de gestion de la confidentialité, le registre, Windows ou les réglages globaux d'Excel.
- La copie de travail est fermée sans sauvegarde.
- Si Excel ne quitte pas après la libération COM, seul le PID créé et détenu par le runner est terminé. Les autres instances Excel ne sont pas ciblées.

Les répertoires `work/` et `output/` ne sont pas purgés automatiquement afin de conserver les éléments d'audit.

## Limites connues et prochaine étape

- L'automatisation dépend d'Excel desktop et n'est ni multiplateforme ni utilisable côté serveur sans Excel.
- Un cas défaillant interrompt actuellement le lot ; aucun rapport JSON d'erreur structuré n'est encore créé.
- La validation par hash exige une égalité bit à bit ; une validation avec tolérances métier reste à ajouter.
- Le mapping actuel couvre le parcours graphique à deux modèles et les plages de sortie qualifiées.
- Les optimisations Solver, les autres configurations du classeur et un jeu de non-régression plus large restent à automatiser.

Les valeurs et l'export CSV sont désormais disponibles. La prochaine étape recommandée est d'ajouter des valeurs de référence indépendantes et des tolérances absolues/relatives définies avec un référent métier, puis d'automatiser le parcours Solver.

## Provenance des exemples

Le cas actuellement automatisé provient du classeur officiel `TracerLPM_V_1_0_Example1`. Les empreintes enregistrées sont des baselines techniques obtenues par répétition sur cette installation, et non des valeurs certifiées dans la publication.

`samples/cases-usgs-example1.yaml` ajoute deux cas de couverture fondés sur les modèles et les données du même classeur : EPM/PEM et DM/BMM-PFM-EMM. Ils ont été exécutés avec succès, avec 61 couples par modèle. Leurs hashes ne sont volontairement pas encore déclarés comme résultats attendus, car une observation locale unique ne suffit pas pour en faire une référence qualifiée.

Les sources USGS décrivent cinq modèles primaires — PFM, EMM, EPM, PEM et DM — ainsi que les mélanges binaires et les parcours tracer–tracer et tracer–temps. Elles fournissent donc la matrice des prochains scénarios, mais pas systématiquement des tables numériques directement exploitables comme résultats de test. Voir le rapport USGS `https://doi.org/10.3133/tm4F3` et la page du laboratoire `https://water.usgs.gov/lab/`.

## Dépannage rapide

- `Hash SHA-256 inattendu` : le classeur ou le XLL n'est pas la version qualifiée ; ne pas mettre à jour le hash sans requalification.
- `Valeur Excel introuvable` : vérifier le libellé dans les listes du classeur ; le message affiche les valeurs disponibles.
- `Complément Excel introuvable` : vérifier Solver et `xll_path`.
- `Recalcul Excel non terminé` : augmenter `timeout_seconds` seulement après avoir contrôlé qu'Excel n'affiche pas une boîte de dialogue.
- `invalid_output` : l'exécution s'est terminée, mais au moins une empreinte ne correspond pas à celle attendue.
