# Overview

PyAges estimates groundwater transit-time distributions from environmental
tracer observations. It combines tracer recharge histories, lumped-parameter
models (LPMs), numerical convolution, and calibration workflows in one Python
package.

The supported user interface is the `pyages` command. A typical analysis has
four inputs:

1. a table of tracer concentrations, uncertainties, units, and sampling dates;
2. one or more tracer recharge histories;
3. an LPM family, its mathematical parameter domains, and its calibration ranges;
4. a YAML workflow configuration.

PyAges writes tabular results, optional figures, and a versioned
`result_manifest.json` that records the configuration, inputs, software
environment, Git state, and hashes of generated artifacts.

## Choose a starting point

- Follow {doc}`user-guide/tutorial` for a first complete, inspectable run.
- Use {doc}`user-guide/configuration` when adapting a YAML file to your data.
- Read {doc}`scientific-overview` before interpreting fitted ages or posterior
  uncertainty.
- Consult {doc}`reference/results` for output files and provenance fields.
- Use {doc}`api/index` when calling the supported Python interfaces directly.

## Project status

PyAges `1.0.1` is the current stable maintenance release. Its supported
interfaces are documented in {doc}`reference/public-api` and compatibility is
managed through {doc}`reference/changelog`. The article campaign and its
immutable scientific archive retain the `1.0` identity and exact reviewed
source tag; maintenance releases do not rewrite that archive. Calculations from
an untagged checkout must also report their Git commit. Scientific conclusions
remain conditional on the selected LPM, tracer histories, observation
uncertainties, and validation scope described in {doc}`science/validation`.

The source repository, issue tracker, contribution policy, and security policy
are hosted on [GitHub](https://github.com/dreuzy/PyAges).
