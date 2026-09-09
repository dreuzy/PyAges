# Albuquerque example

This folder mirrors the structure of `examples/natural/ploemeur` and provides a runnable
starter example for the Albuquerque site. The bundled dataset contains several
Albuquerque sample snapshots (`SSW_*.txt`); the default example uses
`SSW_2007.txt`.

## Example 2 — Albuquerque public supply well (New Mexico, USA)

This example reproduces a real case from the USGS TracerLPM report
(Techniques and Methods 4-F3). It corresponds to a public-supply well tapping
the main Rio Grande aquifer in Albuquerque (New Mexico, USA).

### Hydrogeologic context

The well captures a deep aquifer dominated by old water (thousands to tens of
thousands of years), with a variable contribution of younger water driven by
vertical gradients induced by seasonal pumping. Tracer measurements indicate a
strongly mixed age structure:

- **14C** -> signature of the old component
- **3H and CFCs** -> signature of the young component

The simultaneous presence of these tracers requires binary mixing, since a
single-age model cannot reproduce the observed concentrations.

The data come from 2007-2009 sampling campaigns under the USGS NAWQA program
(Transport of Anthropogenic and Natural Contaminants to supply wells).

### Objective

This example illustrates:

- identification of mixed young/old water
- the effect of pumping on age distributions
- joint calibration of multiple environmental tracers

It serves as a demonstrator for testing whether the code can reproduce a
realistic age distribution in a stratified hydrogeologic system.

### Models to calibrate

The interpretation relies on a **Binary Mixing Model — Dispersion + Dispersion**
(BMM-DM-DM), with:

- a young component modeled by a dispersion model (DM)
- an old component modeled by a dispersion model (DM)
- a mixing fraction to be estimated

Typical parameters adjusted:

- mean age of the young component
- mean age of the old component
- dispersion parameters
- mixing fraction
- unsaturated-zone transit time (optional)

### Scientific reference

Jurgens, Boehlke & Eberts (2012) — *TracerLPM: An Excel Workbook for Interpreting
Groundwater Age Distributions from Environmental Tracer Data*, USGS Techniques
and Methods 4-F3.

## Files

- `exemple_albuquerque.yaml`: YAML configuration for the single-date workflow.
- `exemple_albuquerque_shapefree.yaml`: shape-free single-date variant using a local `data_lpm`.
- `exemple_albuquerque_shapefree_multichain.yaml`: reproducible exploratory
  five-chain profile; it audits computation and convergence diagnostics but is
  not yet a validated site interpretation.
- `exemple_albuquerque.ipynb`: Notebook version of the workflow.
- `data/SSW_2007.txt`: default single-date dataset used by the example.
- `data/SSW_*.txt`: additional Albuquerque sample snapshots.
- `data_lpm/shapefree_n_oldbin/params.yaml`: example-specific 5-bin shape-free configuration with an LPM-defined old-bin maximum age.

## Run

```bash
pyages run examples/natural/albuquerque/exemple_albuquerque.yaml
```

Shape-free open-old-bin variant:

```bash
pyages run examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml
```

Exploratory shape-free multi-chain characterization:

```bash
pyages run examples/natural/albuquerque/exemple_albuquerque_shapefree_multichain.yaml
```

The multi-chain profile deliberately preserves pooled output even when a
diagnostic misses its gate. Its `missing_error_rel: 0.01` and 120-year maximum
support are provisional assumptions. See the rendered Albuquerque example
documentation for the measurements and reference evidence still needed before
this can become a field qualification.
