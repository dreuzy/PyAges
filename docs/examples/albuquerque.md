# Albuquerque field example

The Albuquerque example uses a 2007 public-supply-well dataset containing
tritium, carbon-14, and CFC-113. It illustrates a mixed young/old groundwater
system and includes both a two-age starter configuration and a local
shape-free model with an explicitly bounded old bin.

## Run

The canonical single-date configuration is:

```bash
pyage run examples/natural/albuquerque/exemple_albuquerque.yaml
```

The shape-free variant is:

```bash
pyage run examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml
```

The second command uses
`examples/natural/albuquerque/data_lpm/shapefree_n_oldbin/params.yaml`, whose
five age-bin edges end at 120 years. Those example-specific bounds are a model
choice, not a universal bound for Albuquerque groundwater.

## Interpretation limits

The bundled measurements include zero-valued uncertainty fields. PyAge applies
the workflow's error handling before calibration, but a scientific reuse must
replace placeholder or imputed uncertainties with justified analytical error
models. A successful optimizer or MCMC chain does not by itself establish that
the binary or shape-free LPM is hydrogeologically unique.

The data provenance and USGS TracerLPM reference are recorded in
{doc}`../reference/data-provenance`.
