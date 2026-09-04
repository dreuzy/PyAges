# Albuquerque field example

The Albuquerque example uses a 2007 public-supply-well dataset containing
tritium, carbon-14, and CFC-113. It illustrates a mixed young/old groundwater
system and includes both a two-age starter configuration and a local
shape-free model with an explicitly bounded old bin.

## Run

The canonical single-date configuration is:

```bash
pyages run examples/natural/albuquerque/exemple_albuquerque.yaml
```

The shape-free variant is:

```bash
pyages run examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml
```

The reproducible exploratory multi-chain profile is:

```bash
pyages run examples/natural/albuquerque/exemple_albuquerque_shapefree_multichain.yaml
```

The second command uses
`examples/natural/albuquerque/data_lpm/shapefree_n_oldbin/params.yaml`, whose
five age-bin edges end at 120 years. Those example-specific bounds are a model
choice, not a universal bound for Albuquerque groundwater.

## What the multi-chain test establishes

The versioned profile runs five independent chains from stratified random
starts. Five pilot chains learn one fixed pooled-within-chain proposal
covariance; their samples are not reused as posterior samples. The production
run keeps 1,999 draws per chain after burn-in and records R-hat, bulk ESS, tail
ESS, MCSE, seeds, starts, acceptance rates, proposal covariance, input hashes,
and the terminal result manifest.

The extensive test also checks that:

- every saved parameter vector stays in the declared latent range;
- stick breaking reconstructs five non-negative fractions summing to one;
- parameters, objective value, and modeled tracer concentrations remain on the
  same joint posterior row;
- representative rows reproduce the stored concentrations through a freshly
  prepared forward problem;
- the posterior fit improves on the model defaults under the declared error
  policy;
- a failed diagnostic gate is reported as `not_qualified`, while the explicitly
  exploratory profile still preserves the pooled samples and all evidence.

Run it separately with:

```bash
python -m pytest -q --run-extensive tests/examples/test_albuquerque_shapefree_multichain_scientific.py
```

This result is intentionally not a fifth member of the publishable four-case
multi-chain qualification archive. It is an exploratory scientific
characterization: its test is complete for the stated numerical and provenance
contracts, but the underlying field assumptions are not yet a validated
Albuquerque reference protocol.

The fixed-seed review run on 2026-09-04 made that boundary observable rather
than hypothetical. It finished normally and wrote 9,995 joint posterior rows,
but its maximum R-hat was about 1.360, its minimum bulk ESS about 11.64, and 10
of 11 monitored quantities missed the deliberately modest diagnostic gates.
The median fitted residuals for tritium and CFC-113 were each below 0.34 of the
imputed standard error, while the carbon-14 residual was about 65.77 standard
errors. The first three latent coordinates also contacted their lower
calibration boundary. The correct status is therefore `not_qualified`.

These descriptive values are not frozen as exact floating-point golden data.
The executable test enforces the qualitative scientific result: valid
fractions and internally consistent computation, explicit diagnostic failure,
good young-tracer fit, and gross failure to reproduce carbon-14 under the
120-year support. Any future change that makes this profile pass should trigger
scientific review of the model and assumptions, not an automatic promotion.

## Interpretation limits

The bundled measurements include zero-valued uncertainty fields. PyAges applies
the profile's provisional 1 % tracer-history-mean fallback before calibration.
A scientific reuse must replace or justify these imputed uncertainties with
analytical and sampling error models. Here, four latent coordinates determine
five fractions constrained to sum to one, while only three tracer observations
enter the likelihood. Proper bounded priors make the posterior finite, but do
not add observational information or establish identifiability.

There is also a direct scientific tension to resolve: the site description
mentions water thousands to tens of thousands of years old, whereas the local
demonstration model closes its old bin at 120 years. Before this profile can
become a reference qualification, a domain expert should therefore validate:

1. the uncertainty assigned to each measurement and any correlations;
2. tracer preprocessing, units, corrections, and sampling date;
3. bin edges and a physically defensible upper support for the old component;
4. an independent reference result, preferably the corresponding TracerLPM
   workbook/output or another archived calculation.

The repository already contains enough material to execute and audit the code:
the three observations, tracer histories, LPM schema, configuration, fixed
random seed, and machine-readable results. It does not currently contain the
four scientific decisions above. Consequently, developer verification can
establish computational consistency, but promotion to a field benchmark
requires substantive hydrogeologic review by the project owner or another
qualified reviewer.

The current shape-free forward calculation is also expensive inside MH: the
review run took about 2,348 seconds on the development machine, of which about
1,636 seconds were production and 712 seconds pilot calculation. Runtime is
not a test threshold and varies by machine. A separate optimization should
precompute each tracer/bin response and prove numerical equivalence before
increasing the chain length or tightening convergence thresholds.

A successful optimizer or MCMC chain does not by itself establish that the
binary or shape-free LPM is hydrogeologically unique.

The data provenance and USGS TracerLPM reference are recorded in
{doc}`../reference/data-provenance`.
