# PyAge - Documentation Technique Exhaustive

## Table des Matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture des Fichiers](#2-architecture-des-fichiers)
3. [Flux de Simulation Complet](#3-flux-de-simulation-complet)
4. [Fichiers de Paramètres](#4-fichiers-de-paramètres)
5. [Gestion Multi-Puits et Parallélisation](#5-gestion-multi-puits-et-parallélisation)
6. [Classes de Calibration](#6-classes-de-calibration)
7. [Flux de Données](#7-flux-de-données)
8. [Recommandations de Refactoring](#8-recommandations-de-refactoring)

---

## 1. Vue d'Ensemble

### 1.1 Objectif du Projet

PyAge est un système d'inversion bayésienne pour la **datation des eaux souterraines** utilisant des traceurs chimiques (CFC, SF6, tritium, etc.). Il calibre des **Modèles à Paramètres Groupés (LPM)** représentant la distribution des temps de résidence de l'eau dans un aquifère.

### 1.2 Équation Fondamentale

La concentration modélisée d'un traceur à la date `t_obs` est :

```
C_modélisée(t_obs) = ∫₀^∞ C_atm(t_obs - τ) × g(τ) × D(τ) × P(τ) dτ

où:
- C_atm(t) : concentration atmosphérique à la date t (chronique de recharge)
- g(τ)     : PDF du LPM (distribution des temps de résidence)
- D(τ)     : facteur de décroissance radioactive = exp(-τ/τ_decay)
- P(τ)     : facteur de géoproduction = 1 + rate × τ
- τ        : temps de résidence (âge de l'eau)
```

### 1.3 Statistiques du Code

| Métrique | Valeur |
|----------|--------|
| Lignes de code Python | ~10,800 |
| Nombre de fichiers .py | 54 |
| Nombre de classes | 66 |
| Modèles LPM implémentés | 13 |
| Traceurs supportés | 10 |
| Algorithmes de calibration | 4 |

---

## 2. Architecture des Fichiers

### 2.1 Structure Actuelle

```
sources/
│
├── POINT D'ENTRÉE
│   └── sites/ploemeur/scripts/appli_ploemeur.py           # Application principale (700 lignes)
│       ├── SimulationStrategy      # Stratégie globale de simulation
│       ├── ploemeur_one_date       # Traitement d'une date unique
│       ├── selector()              # Configuration des puits (150 lignes !)
│       └── files_years()           # Génération des fichiers par période
│
├── LPM/ (Modèles à Paramètres Groupés)
│   ├── core/LPM_root.py                 # Classe abstraite de base (615 lignes)
│   ├── core/LPM_dist.py                 # Distribution des résultats (465 lignes)
│   ├── LPM_generate.py             # Factory pattern
│   ├── models/ (implementations)
│   ├──   LPM_exp.py              # Exponentiel
│   ├──   LPM_exp_shifted.py      # Exponentiel decale (2 params: mu, shift)
│   ├──   LPM_gamma.py            # Gamma (2 params: k, scale)
│   ├──   LPM_ig.py               # Gaussienne inverse (2 params: mu, sigma)
│   ├──   LPM_ig_shifted.py       # Gaussienne inverse decalee (3 params)
│   ├──   LPM_uniform.py          # Uniforme (2 params: tmin, delta)
│   ├──   LPM_dirac.py            # Dirac simple (1 param: mu)
│   ├──   LPM_dirac_double.py     # Dirac double (3 params)
│   ├──   LPM_dirac_double_1_set.py
│   ├──   LPM_mix_exp_shifted.py  # Melange dirac + exp
│   ├──   LPM_exp_shifted_young.py
│   ├──   LPM_exp_shifted_old.py

### 2.2 Dépendances entre Modules

```
                    ┌─────────────────────────────────┐
                    │       sites/ploemeur/scripts/appli_ploemeur.py         │
                    │   (SimulationStrategy, selector)│
                    └───────────────┬─────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ ploemeur_one_date   │  │ CalibrationMH       │  │ CalibrationSimplex  │
│ (orchestration)     │  │ (MCMC)              │  │ (Nelder-Mead)       │
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────┐
                    │       CalibrationBasis          │
                    │ (cdata, lpm, tracers, obj_func) │
                    └───────────────┬─────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   Concentrations    │  │   LPM (13 types)    │  │ ConvolutionTracers  │
│   (données .txt)    │  │   (core/LPM_root.py)     │  │ (multi-traceurs)    │
└─────────────────────┘  └──────────┬──────────┘  └──────────┬──────────┘
                                    │                        │
                         ┌──────────┴──────────┐             │
                         ▼                     ▼             ▼
              ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐
              │   params.yaml    │  │   params.yaml    │  │  Convolution│
              │   params.yaml │  │   simplex_init  │  │  (Tracer)   │
              └─────────────────┘  └─────────────────┘  └──────┬──────┘
                                                               │
                                              ┌────────────────┼────────────────┐
                                              ▼                ▼                ▼
                                    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
                                    │ tracer.yaml │  │ recharge.csv│  │ Decay/Prod  │
                                    └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 3. Flux de Simulation Complet

### 3.1 Diagramme de Séquence

```
┌──────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  main()  │     │SimulationStrategy │     │ploemeur_one_date│     │CalibrationMH    │
└────┬─────┘     └─────────┬─────────┘     └────────┬────────┘     └────────┬────────┘
     │                     │                        │                       │
     │ SimulationStrategy()│                        │                       │
     │────────────────────>│                        │                       │
     │                     │                        │                       │
     │     execute()       │                        │                       │
     │────────────────────>│                        │                       │
     │                     │                        │                       │
     │                     │ for error in [0.1..0.4]│                       │
     │                     │──┐                     │                       │
     │                     │  │ for option in [span, suc_prior, ...]        │
     │                     │  │──┐                  │                       │
     │                     │  │  │ selector()       │                       │
     │                     │  │  │ → wells, dates   │                       │
     │                     │  │  │                  │                       │
     │                     │  │  │ for well in wells│                       │
     │                     │  │  │──┐               │                       │
     │                     │  │  │  │__execute_parallel()                   │
     │                     │  │  │  │──────────────>│                       │
     │                     │  │  │  │               │                       │
     │                     │  │  │  │               │ for lpm in lpm_types  │
     │                     │  │  │  │               │──┐                    │
     │                     │  │  │  │               │  │ for file in files  │
     │                     │  │  │  │               │  │──┐                 │
     │                     │  │  │  │               │  │  │ ploemeur_one_date()
     │                     │  │  │  │               │  │  │────────────────>│
     │                     │  │  │  │               │  │  │                 │
     │                     │  │  │  │               │  │  │    perform()    │
     │                     │  │  │  │               │  │  │────────────────>│
     │                     │  │  │  │               │  │  │                 │
```

### 3.2 Détail de `ploemeur_one_date.perform()`

```python
def perform(self):
    """Exécute l'interprétation complète pour une date/puits/LPM."""

    # ═══════════════════════════════════════════════════════════════
    # ÉTAPE 1: PRÉPARATION DES DONNÉES
    # ═══════════════════════════════════════════════════════════════
    cdata = self.concentration_preparation()
    # └─> Charge: sites/ploemeur/data/F09_2005_2010
    # └─> Applique erreur relative: cdata.error_affect_from_value(0.1)
    # └─> cdata.cv = DataFrame[element, concentration, error, unit, date]

    # ═══════════════════════════════════════════════════════════════
    # ÉTAPE 2: CALIBRATION AVEC METROPOLIS-HASTINGS
    # ═══════════════════════════════════════════════════════════════
    lpm_results = self.calibration(cdata, self.calstrat_MH)
    # └─> Crée CalibrationBasis(cdata, lpm_type)
    #     └─> LPM_generate(lpm_type) → instance LPM
    #     └─> ConvolutionTracers(tracer_names, dates)
    #         └─> Pour chaque traceur: Convolution(name, date)
    #             └─> Tracer.__init__() → charge YAML + CSV
    #
    # └─> calstrat_MH.perform()
    #     └─> 200,000 itérations MCMC
    #     └─> Retourne LPMDist (distribution des paramètres)
    #
    # └─> Sauvegarde résultats dans:
    #     results/{folder}/{date}/{well}/{lpm}/Metropolis_Hastings/
```

### 3.3 Nombre Total de Simulations

```
Configuration type (apriori_type="double"):
- errors: [0.1, 0.2, 0.3, 0.4]           → 4
- options: ["span", "span_prior", "suc_prior"] → 3
- wells: 10 puits                        → 10
- lpm_types: 7 modèles par puits         → 7
- files: ~11 paires de dates par puits   → 11

Total = 4 × 3 × 10 × 7 × 11 = 9,240 simulations indépendantes
Chaque simulation = 200,000 itérations MCMC
Total itérations = 1.85 milliards
```

---

## 4. Fichiers de Paramètres

### 4.1 Structure Complète des Fichiers

```
sites/ploemeur/data/
├── core_data/LPM_data/
│   ├── exp/
│   │   ├── params.yaml       # mu,0.1,100,year
│   │   ├── params.yaml        # mu,0.2,year
│   │   ├── params.yaml     # mu,uniform,0.1,100,year
│   │   └── params.yaml  # mu,10,year
│   │
│   ├── exp_shifted/
│   │   ├── params.yaml       # mu,0,100,year
│   │   │                    # shift,0,100,year
│   │   ├── params.yaml
│   │   ├── params.yaml
│   │   └── params.yaml
│   │
│   ├── gamma/               # α,0.01,10,1
│   │                        # β,0.01,100,year
│   ├── ig/                  # α,0.01,10,1
│   │                        # β,0.01,100,year
│   ├── ig_shifted/          # α,0.01,10,1
│   │                        # β,0.01,100,year
│   │                        # shift,0,50,year
│   ├── uniform/             # a,0,100,year
│   │                        # b,0,100,year
│   ├── dirac/               # time,0.1,100,year
│   ├── dirac_double/        # time1,0.1,70,year
│   │                        # time2,0.1,70,year
│   │                        # rate,0.01,0.99,1
│   ├── dirac_double_1_set/  # time1,0.1,70,year
│   │                        # time2,0.1,70,year
│   │                        # rate,0.01,0.99,1
│   └── mix_exp_shifted/     # mu,0,100,year
│                            # shift,0,100,year
│                            # time,0.1,100,year
│                            # rate,0.01,0.99,1

core_data/tracer_data/
├── cfc11/
│   ├── cfc11.yaml          # unit: pptv, recharge: true
│   └── recharge.csv         # date,concentration (1940-2025)
├── cfc12/
├── cfc113/
├── sf6/
├── 3H/                      # decay_time: 12.32 (demi-vie tritium)
├── kr85/
├── 14C/                     # decay_time: 8267, geoproduction
├── 39Ar/
├── Li/                      # geoproduction_rate
└── NO3/
```

### 4.2 Format Détaillé des Fichiers
**Note**: les fichiers `params.yaml`, `params.yaml`, `params.yaml` et `params.yaml` ont ?t? remplac?s par un unique `params.yaml` par mod?le LPM. Le chargement est centralis? dans `sources/data_io/lpm_params.py` et utilis? par `LPM_root` et `calibration_Metropolis_Hastings`.

#### params.yaml (Parametres LPM)ètres)
```
# Format: YAML (voir exemple)é
model: exp_shifted
parameters:
  - name: mu
    bounds: [0.0, 100.0]
    init: 10.0
    step: 1.0
    prior:
      type: uniform
      min: 0.0
      max: 100.0
```

**Chargement** (`core/LPM_root.py:119-145`):
```python
def __load_bounds(self):
    params = load_params(self.name, data_dir)
    bounds = get_bounds(params)
    for name, (pmin, pmax) in bounds.items():
        self.__p_min[name] = pmin
        self.__p_max[name] = pmax
        self.__u[param_name] = df.iloc[i, 3]
```

#### params.yaml (Pas d'incr?ment MCMC)
Les pas MCMC sont d?finis par `step` dans `params.yaml`.

**Chargement** (`calibration_Metropolis_Hastings.py`):
```python
params = load_params(lpm.name, data_dir)
steps = get_steps(params)
```
#### params.yaml (Distributions a priori)
Les a priori sont d?finis dans le champ `prior` de chaque param?tre.

**Chargement** (`calibration_Metropolis_Hastings.py`):
```python
params = load_params(lpm.name, data_dir)
priors = get_priors(params)
```
#### tracer.yaml (Configuration traceur)
```yaml
# Unité de mesure
unit: pptv  # pptv, TU, pmC, mol/l

# Chronique de recharge
recharge: true           # true = charger recharge.csv
recharge_constant: 0.0   # utilisé si recharge: false

# Décroissance radioactive (optionnel)
decay_time: 12.32        # τ_decay en années (3H: 12.32, 14C: 8267)

# Géoproduction (optionnel)
production_rate: 0.001   # taux de production in-situ

# Plage temporelle
datemin: 1940.0
datemax: 2025.0
```

#### recharge.csv (Chronique atmosphérique)
```csv
# En-tête avec métadonnées (lignes commençant par #)
# Tracer: CFC-11
# Unit: pptv
# Source: NOAA/ESRL Global Monitoring Division
date,concentration
1940.0,5.5
1940.5,5.7
1941.0,6.0
...
2025.0,220.3
```

---

## 5. Gestion Multi-Puits et Parallélisation

### 5.1 Configuration des Puits (selector())

**État actuel** (`sites/ploemeur/scripts/appli_ploemeur.py:527-674`):

```python
def selector(well_select, error=0.03):
    wells = []; datess = []; errors = []; lpm_types = []

    if "F09" in well_select:
        wells.append("F09")
        datess.append("2005_2024")
        errors.append(error)
        lpm_types.append(["exp_shifted", "ig_shifted", "ig",
                         "dirac_double_1_set", "gamma", "uniform", "exp"])

    if "F11" in well_select:
        wells.append("F11")
        datess.append("2004_2024")
        # ... même structure répétée 10 fois

    return wells, datess, errors, lpm_types
```

**Problème**: 150 lignes de code répétitif, difficile à maintenir.

### 5.2 Génération des Fichiers par Période

```python
def files_years(well, dates, option, breakups=[]):
    """
    Génère la liste des fichiers de données selon l'option choisie.

    Options:
    - "all": Toutes les années cumulées [2005_2006, 2005_2007, ..., 2005_2024]
    - "suc": Années successives [2005_2006, 2006_2007, ..., 2023_2024]
    - "span": Grandes périodes avec breakups [2005_2012, 2012_2024]
    - "suc_prior": Comme "suc" mais avec a priori de "span"
    """
    start, end, sampling_years = periods_years(well, dates, option, breakups)

    files = []
    for k in range(len(start)):
        # Crée le fichier de sélection: F09_2005_2010
        files.append(ploemeur_data_selection(well, dates, start[k], end[k]))
    return files
```

**Exemple pour F09 avec option="suc" et breakups=[2012]**:
```
Années échantillonnées: [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2024]

Fichiers générés:
- F09_2005_2006
- F09_2006_2007
- F09_2007_2010
- F09_2010_2013
- F09_2013_2014
- ...
- F09_2021_2024
```

### 5.3 Parallélisation avec Multiprocessing

```python
def __execute_parallel(self, well, dates, lpm_types, ...):
    """Exécution parallèle sur toutes les combinaisons lpm×dates."""

    # 1. Créer toutes les instances de simulation
    pod_parallel = []
    for lpm in lpm_types:           # 7 modèles
        for well_date in files:      # ~11 fichiers
            pod = ploemeur_one_date(...)
            pod_parallel.append(pod)  # Total: ~77 instances

    # 2. Exécution parallèle
    if self.parallel:
        pool = mp.Pool(self.proc_nb)  # cpu_count() processus
        for i in range(len(pod_parallel)):
            pool.apply_async(perform, args=(pod_parallel, i))
        pool.close()
        pool.join()
    else:
        for pod in pod_parallel:
            pod.perform()

# Fonction proxy pour multiprocessing
def perform(pod, i):
    pod[i].perform()
```

### 5.4 Données Partagées vs Spécifiques

| Données | Scope | Partage |
|---------|-------|---------|
| Configuration simulation | Global | Partagée (constante) |
| Paramètres LPM (params.yaml) | Par type LPM | Partagée en lecture |
| Chroniques traceurs (recharge.csv) | Par traceur | Partagée en lecture |
| Concentrations mesurées | Par puits/période | Spécifique |
| Instance LPM | Par simulation | Spécifique (copiée) |
| Résultats MCMC | Par simulation | Spécifique (fichiers séparés) |

### 5.5 Architecture des Résultats

```
results/
└── ploemeur_apriori_double_0.1span/    # {folder}_{error}{option}
    └── 2024_01_18-15_30_45/             # {date}-{time}
        ├── F09_2005_2010/               # {well}_{start}_{end}
        │   ├── exp_shifted/             # {lpm_type}
        │   │   ├── concentrations.txt   # Données d'entrée copiées
        │   │   └── Metropolis_Hastings/
        │   │       ├── parameters_calibration.txt
        │   │       ├── results_calibration.txt
        │   │       ├── lpm_dist_calibrated.txt    # Distribution complète
        │   │       ├── lpm_stats_calibrated.txt   # Statistiques
        │   │       ├── trajectory.png             # Convergence MCMC
        │   │       └── *.png                      # Figures diverses
        │   ├── ig_shifted/
        │   ├── gamma/
        │   └── ...
        ├── F09_2010_2013/
        ├── F11_2004_2011/
        └── ...
```

---

## 6. Classes de Calibration

### 6.1 Hiérarchie des Classes

```
CalibrationExploration (calibration_exploration.py)
│   └── Exploration systématique sur grille (ParamSysSampling)
│
CalibrationBasis (calibration_basis.py)
│   ├── Attributs:
│   │   ├── cdata: Concentrations (données mesurées)
│   │   ├── lpm: LPM instance (modèle à calibrer)
│   │   └── tracers: ConvolutionTracers
│   └── Méthodes:
│       └── objective_function(params) → Σ((modèle-données)/erreur)²
│
├── CalibrationSimplex (calibration_simplex.py)
│   │   ├── Méthodes:
│   │   │   ├── Simplex: scipy.optimize.minimize (Nelder-Mead)
│   │   │   ├── Simplex_init_multiples: N initialisations aléatoires
│   │   │   └── forward_uncertainty_quantification: Perturbation des erreurs
│   │   └── Retourne: LPMDist (quelques solutions)
│   │
│   └── CalibrationMetropolisHastings (calibration_Metropolis_Hastings.py)
│       ├── Composants:
│       │   ├── Prior: Distributions a priori (parametric/empirical)
│       │   ├── MH_step: Tailles d'incrément
│       │   └── MH_Trajectory: Suivi de convergence
│       ├── Paramètres:
│       │   ├── nstep: 200,000 (itérations totales)
│       │   ├── burn_in: 0.2 (20% d'échauffement)
│       │   ├── nskip: 10 (sauvegarde 1 sur 10)
│       │   └── lpm_number: 5,000 (modèles pour affichage)
│       └── Retourne: LPMDist (distribution complète)
```

### 6.2 Algorithme Metropolis-Hastings Détaillé

```python
def perform(self):
    """Algorithme MCMC complet."""

    # ═══════════════════════════════════════════════════════════════
    # INITIALISATION
    # ═══════════════════════════════════════════════════════════════
    rng = np.random.default_rng(seed=12345)

    # Charger paramètres depuis fichiers
    self.MH_step.prepare(self.lpm)   # params.yaml
    self.prior.load(self.lpm)        # params.yaml

    # Initialiser paramètres
    if self.prior.option:
        self.prior.param_init(self.lpm)  # Depuis prior
    else:
        self.lpm.param_init()            # Valeurs par défaut

    params = self.lpm.get_parameters_to_array()
    log_p, obj_func, conc = __log_posterior_eval(params)

    # Structure de stockage
    n_saved = (nstep - burn_in * nstep) // nskip
    array_results = np.zeros((n_saved, n_params + 1 + n_tracers + 1))

    # ═══════════════════════════════════════════════════════════════
    # BOUCLE MCMC PRINCIPALE
    # ═══════════════════════════════════════════════════════════════
    nsuccess = 0
    line = 0

    for i in range(nstep):  # 200,000 itérations

        # Perturbation gaussienne des paramètres
        params_new = params + rng.normal(0, delta)  # delta depuis params.yaml

        # Évaluation du posterior pour les nouveaux paramètres
        log_p_new, obj_func_new, conc_new = __log_posterior_eval(params_new)

        # Critère d'acceptation Metropolis-Hastings
        if log_p_new >= log_p:
            accept = True
        else:
            u = rng.uniform(0, 1)
            accept = (np.log(u) < log_p_new - log_p)

        # Mise à jour si accepté
        if accept:
            params = params_new
            log_p = log_p_new
            obj_func = obj_func_new
            conc = conc_new
            nsuccess += 1

        # Stockage (après burn-in, tous les nskip pas)
        if i >= burn_in * nstep and i % nskip == 0:
            array_results[line] = np.concatenate([
                params,           # Paramètres du modèle
                [obj_func],       # Fonction objectif
                conc,             # Concentrations calculées
                [1.0]             # Poids (pour analyses pondérées)
            ])
            line += 1

    # ═══════════════════════════════════════════════════════════════
    # POST-TRAITEMENT
    # ═══════════════════════════════════════════════════════════════
    success_rate = nsuccess / nstep  # Idéalement 0.23-0.45

    lpm_results = LPMDist(self.lpm, tracer_names)
    lpm_results.fill_np_array(array_results, column_names)

    return lpm_results
```

### 6.3 Calcul du Log-Posterior

```python
def __log_posterior_eval(params, data_c, data_error):
    """
    Évalue log P(modèle|données) ∝ log P(données|modèle) + log P(modèle)
    """
    log_proba = 0.0

    # Vérifier que les paramètres sont dans les bornes
    if not param_within_bounds(params):
        return -np.inf, np.inf, []

    # Mettre à jour le LPM avec les nouveaux paramètres
    lpm.set_param_from_array(params)

    # ─────────────────────────────────────────────────────────────
    # LIKELIHOOD: P(données|modèle)
    # ─────────────────────────────────────────────────────────────
    if likelyhood_option:
        # Calculer concentrations modélisées via convolution
        model_c = tracers.convolution(lpm, prepare=True)

        # Fonction objectif: Σ((modèle - données) / erreur)²
        obj_func = sum(((model_c - data_c) / data_error) ** 2)

        # Log-likelihood gaussien: -1/2 × Σ((m-d)/σ)²
        log_proba -= 0.5 * obj_func
    else:
        obj_func = 0.0
        model_c = []

    # ─────────────────────────────────────────────────────────────
    # PRIOR: P(modèle)
    # ─────────────────────────────────────────────────────────────
    if prior.option:
        log_prior = np.log(prior.evaluate(lpm, params))
        log_proba += log_prior

    return log_proba, obj_func, model_c
```

---

## 7. Flux de Données

### 7.1 De la Mesure au Modèle

```
┌─────────────────────────────────────────────────────────────────┐
│                    DONNÉES MESURÉES                             │
│  ori_ploemeur_F09_2005_2024.txt                                 │
│  ┌─────────┬───────────────┬───────┬──────┬────────────┐        │
│  │ element │ concentration │ error │ unit │ date       │        │
│  ├─────────┼───────────────┼───────┼──────┼────────────┤        │
│  │ cfc11   │ 278.1         │ 0.0   │ pptv │ 2005.436   │        │
│  │ cfc12   │ 661.1         │ 0.0   │ pptv │ 2005.436   │        │
│  │ cfc113  │ 99.9          │ 0.0   │ pptv │ 2005.436   │        │
│  └─────────┴───────────────┴───────┴──────┴────────────┘        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│            Concentrations.error_affect_from_value(0.1)          │
│            error = 0.1 × concentration                          │
│  ┌─────────┬───────────────┬───────┬──────┬────────────┐        │
│  │ element │ concentration │ error │ unit │ date       │        │
│  ├─────────┼───────────────┼───────┼──────┼────────────┤        │
│  │ cfc11   │ 278.1         │ 27.8  │ pptv │ 2005.436   │        │
│  │ cfc12   │ 661.1         │ 66.1  │ pptv │ 2005.436   │        │
│  │ cfc113  │ 99.9          │ 10.0  │ pptv │ 2005.436   │        │
│  └─────────┴───────────────┴───────┴──────┴────────────┘        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MODÈLE LPM                                   │
│  exp_shifted: g(τ) = (1/μ) × exp(-(τ-shift)/μ) pour τ ≥ shift   │
│  Paramètres: μ = 30 ans, shift = 5 ans                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONVOLUTION                                  │
│  Pour chaque traceur (cfc11, cfc12, cfc113):                    │
│                                                                 │
│  C_mod(t_obs) = ∫ C_atm(t_obs - τ) × g(τ) × decay(τ) dτ         │
│                                                                 │
│  Discrétisation: Simpson sur 200 points                         │
│  τ ∈ [0, t_obs - datemin]                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                FONCTION OBJECTIF                                │
│                                                                 │
│  J = √[ Σᵢ ((Cᵢ_mod - Cᵢ_data) / σᵢ)² / n ]                     │
│                                                                 │
│  Exemple avec 3 traceurs:                                       │
│  J = √[ ((250-278)/28)² + ((650-661)/66)² + ((95-100)/10)² / 3] │
│  J = √[ 1.0 + 0.025 + 0.25 / 3 ] = 0.65                         │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Chronique de Recharge et Décroissance

```python
def get_concentration(self, date, time):
    """
    Calcule la concentration tenant compte de:
    - La chronique atmosphérique
    - La décroissance radioactive
    - La géoproduction in-situ

    Paramètres:
        date: année d'observation (ex: 2010.5)
        time: temps de résidence τ (ex: 25 ans)
    """
    # Date de recharge = quand l'eau est entrée dans l'aquifère
    date_recharge = date - time  # 2010.5 - 25 = 1985.5

    # Concentration atmosphérique à la date de recharge
    C_atm = self.__recharge_chronicle_interp(date_recharge)

    # Décroissance radioactive
    if self.decay_time > 0:
        decay_factor = np.exp(-time / self.decay_time)
    else:
        decay_factor = 1.0

    # Géoproduction in-situ
    if self.production_rate > 0:
        production_factor = 1.0 + self.production_rate * time
    else:
        production_factor = 1.0

    return C_atm * decay_factor * production_factor
```

**Exemple avec Tritium (3H)**:
```
Observation: date = 2010, time = 25 ans
Date recharge: 1985
C_atm(1985) = 150 TU (pic post-nucléaire)
τ_decay = 12.32 ans (demi-vie / ln2)

decay_factor = exp(-25 / 12.32) = 0.131
C_final = 150 × 0.131 = 19.7 TU
```

---

## 8. Recommandations de Refactoring

### 8.1 Problème Principal: selector()

**État actuel**: 150 lignes de code répétitif dans `sites/ploemeur/scripts/appli_ploemeur.py:527-674`

**Solution proposée**: Configuration YAML externe

```yaml
# sites/ploemeur/data/wells_config.yaml

defaults:
  lpm_types: ["exp_shifted", "ig_shifted", "ig", "dirac_double_1_set",
              "gamma", "uniform", "exp"]
  tracers: ["cfc11", "cfc12", "cfc113"]
  breakups: [2012]

wells:
  F09:
    dates: "2005_2024"
    # Hérite des defaults

  F11:
    dates: "2004_2024"
    # Surcharge possible:
    # lpm_types: ["exp_shifted", "ig_shifted"]

  F34:
    dates: "2004_2015"
    breakups: []  # Pas de breakup

  F38:
    dates: "2006_2020"

  F38b:
    dates: "2006_2011"
    breakups: []
    tracers: ["cfc11", "cfc12"]  # Traceurs spécifiques

  PE:
    dates: "2005_2020"

  MF1:
    dates: "2004_2020"

  MF4:
    dates: "2006_2017"
    breakups: []

  PZ2:
    dates: "2009_2024"
    breakups: []

  PSR1:
    dates: "2009_2024"
    breakups: []
```

**Nouvelle fonction selector()**:

```python
def selector(well_select: list[str], error: float = 0.03) -> tuple:
    """Charge la configuration depuis YAML."""
    import yaml
    from pathlib import Path

    config_path = Path(__file__).parent / "sites" / "ploemeur" / "data" / "wells_config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    defaults = config.get("defaults", {})
    wells_cfg = config["wells"]

    wells, datess, errors, lpm_types = [], [], [], []

    for well_name in well_select:
        if well_name not in wells_cfg:
            continue

        well = wells_cfg[well_name]
        wells.append(well_name)
        datess.append(well["dates"])
        errors.append(error)
        lpm_types.append(well.get("lpm_types", defaults["lpm_types"]))

    return wells, datess, errors, lpm_types
```

**Bénéfices**:
- 150 lignes → 20 lignes
- Configuration modifiable sans toucher au code
- Facilite l'ajout de nouveaux sites

### 8.2 Séparation Données/Code/Application

```
pyage/                          # Nouveau nom du projet
├── pyage/                      # Package Python (bibliothèque)
│   ├── __init__.py
│   ├── lpm/                    # Modèles LPM
│   ├── tracer/                 # Traceurs
│   ├── convolution/            # Convolution
│   ├── calibration/            # Calibration
│   └── core/
│       ├── config.py           # Chargement YAML
│       ├── simulation.py       # Classe Simulation générique
│       └── exceptions.py       # Exceptions personnalisées
│
├── applications/               # Applications spécifiques
│   ├── ploemeur/
│   │   ├── config.yaml         # Configuration simulation
│   │   ├── wells.yaml          # Configuration puits
│   │   └── run.py              # Point d'entrée
│   └── fontainebleau/
│       └── ...
│
├── data/                       # Données (séparées du code)
│   ├── tracers/                # Chroniques (globales)
│   │   ├── cfc11/
│   │   └── ...
│   ├── sites/
│   │   ├── ploemeur/
│   │   │   ├── concentrations/ # Mesures par puits
│   │   │   └── lpm_params/     # Paramètres LPM
│   │   └── fontainebleau/
│   └── lpm_defaults/           # Paramètres LPM par défaut
│
└── tests/
    ├── unit/
    ├── integration/
    └── regression/
```

### 8.3 Tests de Non-Régression

**Avant tout refactoring**, créer des tests qui capturent le comportement actuel:

```python
# tests/regression/test_capture_golden.py

import json
import numpy as np
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden_references"

class TestCaptureGolden:
    """Capture les sorties actuelles comme références."""

    def test_capture_convolution(self):
        """Capture les résultats de convolution pour chaque combinaison."""
        from convolutions.convolution import Convolution
        from LPM.LPM_generate import LPM_generate

        test_cases = [
            ("exp_shifted", "cfc11", 2010),
            ("ig_shifted", "cfc12", 2015),
            ("dirac_double_1_set", "kr85", 2010),
        ]

        for lpm_type, tracer, date in test_cases:
            lpm = LPM_generate(lpm_type)
            conv = Convolution(name=tracer, date=date)
            result = conv.convolution(lpm)

            # Sauvegarder comme référence
            golden_file = GOLDEN_DIR / f"conv_{lpm_type}_{tracer}_{date}.json"
            with open(golden_file, "w") as f:
                json.dump({
                    "lpm_type": lpm_type,
                    "lpm_params": dict(lpm.p),
                    "tracer": tracer,
                    "date": date,
                    "result": float(result)
                }, f, indent=2)

    def test_capture_selector(self):
        """Capture la configuration de selector()."""
        from appli_ploemeur import selector

        all_wells = ["F09", "F11", "F34", "F38", "PE", "MF1", "MF4", "PZ2", "PSR1"]
        results = {}

        for well in all_wells:
            wells, datess, errors, lpm_types = selector([well], error=0.03)
            if wells:
                results[well] = {
                    "dates": datess[0],
                    "lpm_types": lpm_types[0]
                }

        golden_file = GOLDEN_DIR / "selector_config.json"
        with open(golden_file, "w") as f:
            json.dump(results, f, indent=2)
```

**Exécution**:
```bash
# Phase 1: Capturer les références (AVANT refactoring)
python -m pytest tests/regression/test_capture_golden.py -v

# Phase 2: Vérifier après refactoring
python -m pytest tests/regression/test_regression.py -v
```

---

## Conclusion

Ce document fournit une analyse exhaustive du projet PyAge, couvrant:

1. **Architecture complète** avec tous les flux de données
2. **Tous les fichiers de paramètres** et leur format
3. **Gestion multi-puits** avec parallélisation
4. **Algorithmes de calibration** détaillés
5. **Recommandations concrètes** pour le refactoring

Les prochaines étapes prioritaires sont:
1. Créer les tests de non-régression
2. Extraire la configuration des puits dans `wells_config.yaml`
3. Séparer données/code/applications
4. Ajouter un système de logging
