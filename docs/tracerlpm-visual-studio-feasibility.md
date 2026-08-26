# Faisabilité d’un lanceur TracerLPM autonome sous Visual Studio

> **Statut : étude de conception archivée.** La preuve de concept décrite ici a
> depuis été réalisée. Le guide opérationnel actuel est
> `validation/tracerlpm/README.md`; ce document conserve le raisonnement et les
> contraintes étudiés avant l’implémentation.

> La première partie restitue l’étude de conception menée avant la preuve de
> concept : à ce stade historique, aucun projet Visual Studio, code COM ou
> classeur automatisé n’avait encore été créé. La section 13 consigne le
> résultat obtenu ensuite.

## 1. Objectif et indépendance

Le futur lanceur doit constituer un répertoire complètement indépendant de
PyAge. Il ne doit :

- importer aucun module Python de PyAge ;
- écrire dans aucun répertoire scientifique de PyAge ;
- connaître aucune classe LPM de PyAge ;
- contenir aucune transformation scientifique propre à PyAge.

Son unique responsabilité sera de piloter une distribution locale et figée de
TracerLPM, d’injecter des cas tabulaires, de déclencher le calcul Excel et
d’exporter des résultats tabulaires accompagnés d’un journal technique.

L’échange avec PyAge se fera exclusivement par fichiers CSV/JSON et manifestes.

## 2. État de l’environnement et de TracerLPM

L’environnement inspecté contient Excel 16.0 sous Windows. Aucun classeur,
installateur ou add-in TracerLPM n’a été trouvé localement dans les emplacements
de projet et dossiers utilisateur usuels.

Le manuel USGS indique que TracerLPM version 1 repose sur :

- un classeur Excel interactif utilisant VBA ;
- `TracerLPMfunctions_32_v_1.xll` et
  `TracerLPMfunctions_64_v_1.xll` ;
- des fonctions fermées écrites en C++ avec Visual Studio 2010 et le SDK XLL
  Excel 2010 ;
- une structure de feuilles et de cellules dont la stabilité est nécessaire au
  fonctionnement des macros.

Le manuel précise que le XLL placé à côté du classeur est normalement enregistré
et chargé à l’ouverture ; sinon il doit être ajouté manuellement dans Excel.
Les macros doivent être autorisées.

La page USGS actuelle fournit clairement le rapport, mais la recherche menée
n’a pas permis d’identifier un téléchargement officiel actif et vérifiable de la
distribution binaire. La première condition de faisabilité est donc d’obtenir
le classeur et les XLL depuis une source autorisée, puis d’en calculer les hashes.

Références :

- [publication USGS TracerLPM](https://pubs.usgs.gov/publication/tm4F3) ;
- [manuel PDF, notamment l’annexe B](https://pubs.usgs.gov/tm/4-f3/pdf/tm4-F3.pdf).

## 3. Interprétation de « faire tourner TracerLPM à partir de Visual Studio »

Trois approches sont possibles.

### 3.1 Client C#/.NET pilotant Excel par COM — recommandée

Une application console C# créée avec Visual Studio contrôle une instance Excel
installée localement via `Microsoft.Office.Interop.Excel` : ouverture du
classeur, chargement du XLL, écriture des cellules, appel éventuel de macros,
recalcul, lecture des cellules de sortie et fermeture.

C’est l’approche la moins intrusive : elle utilise le moteur original sans
réécrire les fonctions TracerLPM.

Microsoft documente officiellement le pilotage d’Excel depuis Visual C# et le
recalcul complet via l’Interop :

- [automatiser Excel depuis Visual C#](https://learn.microsoft.com/en-us/previous-versions/office/troubleshoot/office-developer/automate-excel-from-visual-c) ;
- [`CalculateFullRebuild`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.office.interop.excel._application.calculatefullrebuild) ;
- [mécanismes de recalcul Excel](https://learn.microsoft.com/en-us/office/client-developer/excel/excel-recalculation).

### 3.2 Add-in VSTO

Un add-in Visual Studio chargé dans Excel pourrait ajouter une interface dédiée.
Cette option couple davantage le lanceur à l’installation d’Office, complexifie
le déploiement et risque d’interagir avec le VBA existant. Elle n’est pas
justifiée pour un benchmark en lot.

### 3.3 Réécriture ou appel direct des fonctions XLL

Un XLL est une DLL spéciale appelée par Excel, et non une bibliothèque générale
garantissant une API externe stable. L’appeler directement depuis .NET ou
réécrire les fonctions C++ demanderait le code source, les signatures et le SDK
approprié. Cela ne constituerait plus une exécution indépendante du TracerLPM
original.

Cette approche est rejetée pour l’étude initiale. Microsoft rappelle qu’un XLL
est un add-in natif C/C++ destiné à Excel :
[documentation XLL](https://learn.microsoft.com/en-us/office/client-developer/excel/creating-xlls).

## 4. Architecture future du répertoire autonome

Le répertoire ne devrait pas se trouver dans le package `pyage`. Deux options
sont acceptables :

- dépôt Git séparé, préférable pour une indépendance stricte ;
- répertoire frère de `pyage`, ignoré par le packaging Python.

Nom proposé : `tracerlpm-vs-runner/`.

```text
tracerlpm-vs-runner/
  README.md
  LICENSES.md
  SECURITY.md
  TracerLpmRunner.sln
  src/
    TracerLpmRunner.Cli/
    TracerLpmRunner.Core/
  tests/
    TracerLpmRunner.UnitTests/
    TracerLpmRunner.IntegrationTests/
  schemas/
    cases.schema.json
    results.schema.json
    runner-config.schema.json
  config/
    workbook-map.example.json
  samples/
    cases.example.csv
  scripts/
    inspect-environment.ps1
  vendor/
    README.md
    .gitignore
  work/
    .gitignore
  output/
    .gitignore
```

Le classeur et le XLL ne doivent pas être ajoutés au dépôt tant que leur licence
de redistribution n’a pas été vérifiée. `vendor/README.md` expliquera comment
les fournir localement et quels noms/hashes sont attendus.

## 5. Contrats de fichiers

### 5.1 Configuration du lanceur

Le fichier de configuration technique contient uniquement :

- chemin du classeur modèle ;
- chemin du XLL ;
- hash attendu des deux fichiers ;
- visibilité d’Excel ;
- timeout ;
- langue/région attendue ;
- chemin de la cartographie des feuilles/cellules ;
- noms de macros explicitement autorisées.

### 5.2 Cas d’entrée

Un cas reçoit un identifiant stable et des valeurs déjà exprimées dans les
conventions TracerLPM :

- modèle ;
- paramètres ;
- date d’observation ;
- fonction d’entrée tabulée ;
- traceur et unité ;
- options techniques nécessaires au classeur.

Le lanceur ne convertit pas des paramètres PyAge. Cette transformation appartient
au benchmark comparatif, pas au produit autonome.

### 5.3 Résultats

Chaque résultat doit contenir :

- identifiant du cas ;
- concentrations lues ;
- cellules sources ;
- état de calcul Excel ;
- messages d’erreur Excel ;
- durée ;
- versions et hashes ;
- statut `success`, `timeout`, `excel_error`, `macro_error` ou `invalid_output`.

## 6. Cycle d’exécution proposé

1. Valider les fichiers et leurs hashes.
2. Vérifier que le bitness du processus, d’Excel et du XLL est compatible.
3. Copier le classeur modèle dans un répertoire de travail unique.
4. Démarrer une nouvelle instance Excel contrôlée par le lanceur.
5. Désactiver les alertes interactives compatibles avec un traitement sûr.
6. Charger ou vérifier le XLL.
7. Ouvrir la copie du classeur.
8. Vérifier les noms de feuilles, plages et cellules sentinelles.
9. Injecter un seul cas.
10. Lancer seulement les macros autorisées si elles sont nécessaires.
11. Forcer un recalcul complet et attendre la fin avec timeout.
12. Lire et valider les sorties.
13. Exporter le résultat et le journal avant le cas suivant.
14. Fermer le classeur sans altérer le modèle original.
15. Quitter Excel et libérer les objets COM dans l’ordre inverse.

Le mode initial doit traiter un seul cas par processus Excel. Un mode batch ne
sera envisagé qu’après vérification de l’absence d’état résiduel entre cas.

## 7. Cartographie du classeur

La cartographie des cellules ne doit pas être codée en dur dans les classes C#.
Un fichier versionné séparé doit décrire :

- version/hash du classeur concerné ;
- feuilles requises ;
- cellules d’entrée ;
- cellules de sortie ;
- cellules sentinelles et formules attendues ;
- macros ;
- ordre des opérations.

Les plages nommées sont préférables si elles existent et sont stables. Sinon,
les adresses A1 doivent être accompagnées de sentinelles permettant de détecter
un décalage de structure plutôt que d’écrire silencieusement au mauvais endroit.

Le manuel indique que les feuilles `Samples`, `TracerInput`,
`TracerTracerOutput`, `TimeSeriesOutput`, `LPM_AgeDistribution` et plusieurs
feuilles cachées participent aux workflows. Leur cartographie exacte ne peut pas
être établie sans le classeur réel.

## 8. Contraintes de sécurité et d’exploitation

### 8.1 Macros

Le lanceur ne doit jamais réduire globalement la sécurité Excel ni modifier les
paramètres de confiance de l’utilisateur. Le classeur doit provenir d’une source
vérifiée, être hashé, et idéalement résider dans un emplacement de confiance
dédié configuré manuellement.

Seules les macros listées dans la configuration sont appelées. Les dialogues et
événements à l’ouverture doivent être inventoriés lors du pilote.

### 8.2 Exécution interactive

Excel COM est une application de bureau. Microsoft déconseille son automatisation
dans un service Windows ou un contexte serveur non interactif en raison des
dialogues, blocages et problèmes de profil utilisateur.

Le lanceur est donc conçu pour :

- une machine Windows dédiée ;
- une session utilisateur interactive ;
- une seule exécution à la fois ;
- aucun service web ou exécuteur CI headless au départ.

Pour un scénario RPA réellement non surveillé, les contraintes de licence
Microsoft 365 et d’activation doivent également être vérifiées :
[Microsoft 365 unattended RPA](https://learn.microsoft.com/en-us/microsoft-365-apps/licensing-activation/overview-unattended).

### 8.3 Gestion des processus

Le lanceur ne doit jamais terminer tous les processus `EXCEL.EXE`. Il doit
conserver l’identité de l’instance créée et ne nettoyer que cette instance après
avoir tenté une fermeture COM normale.

## 9. Compatibilité et risques principaux

| Risque | Probabilité | Impact | Mesure proposée |
|---|---|---|---|
| Distribution TracerLPM introuvable ou non redistribuable | Élevée actuellement | Bloquant | Obtenir une copie autorisée et vérifier la licence |
| XLL 2010 incompatible avec Excel 16 actuel | Moyenne | Bloquant | Test manuel minimal avant tout développement |
| Mismatch 32/64 bits | Moyenne | Bloquant | Détection préalable et build `x64`/`x86` explicite |
| Macros bloquées | Élevée au premier lancement | Bloquant | Emplacement de confiance dédié, pas de baisse globale de sécurité |
| Dialogues invisibles | Moyenne | Élevé | Mode Excel visible pendant le pilote, timeout et captures de diagnostic |
| Cellules déplacées selon la version | Moyenne | Élevé | Cartographie par hash et cellules sentinelles |
| État résiduel entre cas | Moyenne | Moyen | Un cas par instance pendant la qualification |
| Objets COM non libérés | Moyenne | Moyen | Discipline stricte de cycle de vie et test de fuite de processus |
| Paramètres régionaux décimaux/dates | Moyenne | Élevé | Écrire des valeurs numériques, pas des chaînes localisées |
| Recalcul incomplet | Moyenne | Élevé | `CalculateFullRebuild`, attente de fin et cellules sentinelles |

## 10. Plan de faisabilité en étapes

### Étape 0 — acquisition

- obtenir le classeur et le XLL 64 bits ;
- vérifier provenance, licence, signatures éventuelles et hashes ;
- archiver le manuel correspondant exactement à cette version.

### Étape 1 — qualification manuelle

- ouvrir le classeur dans Excel actuel ;
- charger le XLL ;
- activer les macros de façon contrôlée ;
- reproduire un exemple fourni par l’USGS ;
- vérifier qu’une sauvegarde et réouverture conservent les calculs.

Critère d’arrêt : ne pas développer de lanceur si cette étape échoue.

### Étape 2 — inspection du classeur

- inventorier feuilles visibles/cachées, noms définis, macros nécessaires,
  cellules d’entrée et sortie ;
- créer la première cartographie versionnée ;
- sélectionner un cas PFM simple sans optimisation.

### Étape 3 — preuve de concept Visual Studio

- application console C# minimale ;
- ouverture d’une copie du classeur ;
- lecture d’une cellule sentinelle ;
- écriture du cas PFM ;
- recalcul ;
- export d’une concentration ;
- fermeture sans processus Excel résiduel.

### Étape 4 — robustesse

- erreurs typées ;
- timeouts ;
- validation des schémas ;
- tests x64 ;
- journaux reproductibles ;
- répétition du même cas et comparaison bit à bit ou avec tolérance.

### Étape 5 — lot limité

- import CSV de quelques cas forward ;
- un cas par instance, puis expérimentation prudente du batch ;
- comparaison des résultats répétés ;
- documentation de la procédure opérateur.

## 11. Tests du futur lanceur

### Tests unitaires sans Excel

- validation des schémas ;
- hashes ;
- sélection x86/x64 ;
- lecture de configuration ;
- validation et sérialisation des résultats ;
- refus des macros non autorisées.

### Tests d’intégration avec Excel

- ouverture/fermeture sans fuite ;
- détection d’un XLL absent ;
- détection d’un mauvais classeur ;
- cas PFM connu ;
- recalcul complet ;
- timeout contrôlé ;
- répétabilité sur dix exécutions ;
- conservation intacte du classeur modèle.

Ces tests doivent être marqués comme Windows/Excel uniquement et ne pas faire
partie d’une CI générique.

## 12. Verdict de faisabilité

La solution Visual Studio la plus raisonnable est un client console C#/.NET
pilotant Excel par COM. Elle peut rester entièrement indépendante de PyAge et
préserver le moteur TracerLPM original.

La faisabilité est toutefois **conditionnelle**, pas encore démontrée :

1. la distribution exécutable officielle n’est pas disponible localement ;
2. la compatibilité du XLL Visual Studio/Excel 2010 avec l’Excel 16 installé doit
   être testée ;
3. la cartographie des cellules et macros exige l’inspection du classeur réel ;
4. l’exécution doit initialement rester interactive et locale.

La prochaine action utile n’est donc pas d’écrire du code : c’est d’obtenir la
distribution exacte, de la qualifier manuellement et de figer son hash. Si ce
test réussit, une preuve de concept Visual Studio limitée à un cas PFM est un
investissement proportionné.

## 13. Mise à jour après qualification et preuve de concept

La distribution x64 a été qualifiée le 16 août 2026 sur Microsoft 365 Apps for
enterprise 64 bits, version 2607, build 16.0.20228.20158.

Résultats :

- installation MSI x64 réussie ;
- XLL 64 bits chargé et fonctionnel ;
- contrôles ActiveX utilisables avec autorisation explicite pour la session ;
- cas officiel PFM/EMM exécuté sans erreur de cellule ;
- optimisation PEM avec Solver reproduisant le résultat officiel ;
- contournement nécessaire sur Excel français, car le VBA recherche
  `Solver Add-In` au lieu de `Complément Solveur` ;
- résultats numériques identiques sur trois processus Excel indépendants.

Un runner autonome .NET 8 x64 est désormais conservé dans le dépôt PyAge sous
`validation/tracerlpm`, tout en restant indépendant du package Python. Il valide les hashes, copie le
classeur, crée sa propre instance Excel, configure le cas officiel, exécute les
événements VBA, recalcule, lit 61 couples PFM et 61 couples EMM, compare leurs
empreintes et exporte un résultat JSON.

Le passage final retourne `success`. Une limite d'exploitation subsiste : Excel
reste parfois actif après `Application.Quit()`. Le POC attend dix secondes puis
termine uniquement le PID qu'il a créé, après avoir fermé le classeur sans
sauvegarde. Aucun processus Excel ne subsiste après l'exécution.

Le verdict passe donc de « faisabilité conditionnelle non démontrée » à
**preuve de concept réussie avec contournements documentés**. Le contrat d'entrée
est désormais exclusivement YAML. Les prochaines extensions sont la comparaison
point par point avec PyAge, les tolérances numériques justifiées et les tests
d'intégration automatisés des chemins d'erreur.
