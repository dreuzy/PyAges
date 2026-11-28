(external-lpm-plugins)=
# External LPM plugins

This page is the reference for providing a Lumped Parameter Model (LPM) from a
separately installed Python package. Start with
{doc}`external-lpm-quickstart` if you want to create a working plugin first.

## Scope and guarantees

An external plugin keeps its scientific code and parameter schema outside the
PyAges repository. Once installed, users retain the ordinary API:

```python
from pyages.lpm import build_lpm

model = build_lpm("my_model")
```

The plugin mechanism guarantees that PyAges can discover, validate, construct,
and identify an installed provider. It does not qualify the scientific model.

The design has four boundaries:

| Boundary | Responsibility |
| --- | --- |
| Python package | Ships the model code and its tests |
| `params.yaml` | Describes domains, calibration ranges, initial values, steps, priors, labels, and units |
| Entry point | Advertises one public model name and one Python object |
| PyAges | Discovers, validates, constructs, checks, and records provenance |

## Mental model: an installed catalogue entry

An entry point is not a special function and it is not a process running in the
background. It is a small metadata record created when a Python distribution is
installed.

For an LPM plugin, the record contains:

```text
group          public name     Python object to load
pyages.lpms    my_model        pyages_lpm_my_model.model:definition
```

The group is a catalogue shelf. PyAges reads only the `pyages.lpms` shelf. The
public name is passed to `build_lpm()`. The target is equivalent to:

```python
from pyages_lpm_my_model.model import definition
```

The compact `module:object` notation lets PyAges store that address without
importing the module.

Entry points are a standard Python packaging mechanism. They are also used by:

- `pytest`, whose installable plugins advertise themselves in `pytest11`;
- Pygments, which discovers external lexers, styles, filters, and formatters;
- `console_scripts`, which creates installed terminal commands.

See the [PyPA entry-point specification][pypa-entry-points], the
[pytest plugin documentation][pytest-plugins], and the
[Pygments plugin documentation][pygments-plugins].

[pypa-entry-points]: https://packaging.python.org/en/latest/specifications/entry-points/
[pytest-plugins]: https://docs.pytest.org/en/stable/how-to/writing_plugins.html#making-your-plugin-installable-by-others
[pygments-plugins]: https://pygments.org/docs/plugins/

## Package declaration

The plugin declares its advertisement in `pyproject.toml`:

```toml
[project.entry-points."pyages.lpms"]
my_model = "pyages_lpm_my_model.model:definition"
```

The entry-point name is the canonical LPM name. It must use `snake_case` and it
must equal the name passed by the model to `LpmBase`.

The package must also include its YAML file in built distributions:

```toml
[tool.setuptools.package-data]
pyages_lpm_my_model = ["data_lpm/*/params.yaml"]
```

The generated project contains both declarations and comments explaining why
they are needed.

## The public plugin contract

The advertised object is one `LpmDefinition`:

```python
from pathlib import Path

from pyages.lpm.extensions import LpmDefinition

definition = LpmDefinition(
    model_class=MyModelLpm,
    parameter_directory=Path(__file__).parent / "data_lpm",
    api_version=1,
)
```

It answers three questions:

1. Which `LpmBase` subclass should PyAges construct?
2. Where is the root containing `<model-name>/params.yaml`?
3. Which version of the plugin contract does the package implement?

The public contract intentionally contains data only. Plugin authors do not
need to implement a loader, registry class, factory, or lifecycle hook.

`LpmDefinition` and `LpmProvenance` live in `pyages.lpm.extensions`, the small
public module reserved for external-package integration.

## Discovery and loading lifecycle

PyAges separates metadata discovery from code loading:

```text
pyages list lpms
        │
        └── read installed entry-point metadata
            without importing plugin modules

build_lpm("my_model") or pyages check lpm my_model
        │
        ├── reject missing, invalid, or conflicting names
        ├── import only the selected entry point
        ├── validate LpmDefinition
        ├── validate the packaged params.yaml
        └── construct and return the model
```

This lazy boundary matters for reliability. An unused broken plugin does not
prevent unrelated models from running. Listing installed advertisements also
does not execute third-party plugin code.

Loaded definitions are cached within the process. Probability evaluations and
convolution calls go directly to the constructed model; there is no plugin
dispatch inside numerical loops.

## Parameter-directory precedence

PyAges chooses one parameter root in this order:

1. a directory explicitly supplied by the caller or workflow configuration;
2. the directory packaged by the external plugin;
3. the built-in PyAges data directory for a built-in model.

For example:

```python
model = build_lpm(
    "my_model",
    directory_lpm="parameters_for_this_study",
)
```

The effective root must contain:

```text
parameters_for_this_study/my_model/params.yaml
```

The override changes parameter metadata, not model code. Parameter names and
units must still agree with the constructor.

## Choosing a model base

### SciPy-backed continuous model

Inherit from `LpmScipy` when one `scipy.stats` distribution faithfully
represents the probability law. Implement:

- `scipy_dist`;
- the physical parameters and units in `__init__()`;
- `_scipy_params()` to produce SciPy shape arguments, location, and scale;
- `cdf_and_partial_first_moment()` for continuous convolution.

`LpmScipy` supplies `pdf()`, `cdf()`, `cdf_inv()`, `mean()`, and `std()`.

Generate this layout with:

```console
pyages new lpm my_model --layout plugin --base scipy
```

The maintained `examples/templates/external_lpm_plugin_scipy` project shows a
complete `gamma_mean` plugin. Its public `mu` and `shape` parameters are
converted to the shape and scale expected by `scipy.stats.gamma`.

### Custom probability law

Inherit directly from `LpmBase` when the law is custom, discrete, mixed, or not
faithfully represented by a single SciPy distribution. Implement the methods
required by its `ConvolutionStrategy`.

A custom continuous model normally provides:

- `pdf()`;
- `cdf()`;
- `cdf_inv()`;
- `mean()`;
- `std()`;
- `cdf_and_partial_first_moment()`.

Generate a complete bounded-power starter with:

```console
pyages new lpm my_model --layout plugin --base root
```

The maintained `examples/templates/external_lpm_plugin` project demonstrates
this path without `scipy.stats`; it implements a bounded power law directly
with NumPy.

## The continuous-convolution primitive

Continuous convolution needs more than the probability density. For each age
`t`, the model returns:

```text
F(t)  = P(T <= t)
M1(t) = E[T 1(T <= t)]
```

through:

```python
cdf, partial_moment = model.cdf_and_partial_first_moment(t)
```

Both results must preserve scalar and array input behavior. The partial moment
must approach the full mean as `t` approaches the upper support or infinity.
An analytical expression is strongly preferred. If numerical integration is
unavoidable, document its accuracy and test difficult parameter ranges.

See {doc}`adding-lpm` for the complete numerical contract shared by built-in
and external models.

(external-lpm-integration-checking)=
## Integration checking

Run:

```console
pyages check lpm my_model
```

The deterministic checker exercises:

- entry-point loading and definition validation;
- YAML presence and parameter agreement;
- initial and midpoint parameter vectors;
- finite scalar and vector results;
- non-negative density and monotone CDF behavior;
- CDF/quantile consistency and normalization;
- finite mean and standard deviation;
- the partial first moment for continuous models;
- the declared convolution-strategy method family;
- production continuous convolution against constant and affine responses.

A warning indicates a non-applicable or advisory probe. A failure produces a
non-zero command status.

This checker catches integration errors. Scientific qualification still needs
distribution-specific tests for exact moments, boundaries, limiting cases,
reference data, and the parameter ranges used in real studies.

## Conflicts and errors

### Duplicate names

If a built-in and an external provider, or two external providers, advertise
the same name, that name becomes unavailable. PyAges reports every provider and
never chooses according to installation order. Other model names remain usable.

### Invalid names

Names outside the canonical `snake_case` form are shown as invalid catalogue
entries and cannot be built.

### Incompatible API versions

PyAges rejects a definition whose `api_version` differs from the supported
version. This produces an actionable compatibility error rather than allowing
an old contract to fail later during calibration.

### Import or definition errors

An import failure is reported only when the affected model is selected. PyAges
also rejects definitions whose model class does not inherit from `LpmBase` or
whose packaged parameter file is missing.

## Provenance and reproducibility

Every factory-built model receives immutable provenance containing:

- the public model name;
- the provider distribution name and version;
- the entry-point target, if external;
- the plugin API version;
- the SHA-256 digest of the exact `params.yaml` used.

Single-date and temporal workflow manifests record this information. An
explicit parameter override therefore changes the recorded YAML digest even
when the package version remains the same.

You can inspect provenance directly:

```python
from pyages.lpm import build_lpm

model = build_lpm("my_model")
print(model.provenance)
```

## Security boundary

Entry-point metadata can be read without importing the target, but building or
checking a plugin executes installed Python code. Install plugins only from
trusted sources and preserve normal Python dependency and release review.

Searching arbitrary directories for `.py` files was deliberately rejected:
it would make execution boundaries, name conflicts, versions, and result
reproduction depend on local filesystem state.

## Development without publication

An editable installation uses the same discovery mechanism as a released
wheel:

```console
python -m pip install -e path/to/pyages-lpm-my-model
pyages check lpm my_model
```

Restart the Python process after changing plugin code or entry-point metadata.
PyAges caches discovery and loaded definitions within one process.

## Maintainer implementation map

The plugin-specific implementation is localized:

| Location | Responsibility |
| --- | --- |
| `pyages/lpm/extensions.py` | Stable public definition and provenance records |
| `pyages/lpm/core/registry.py` | Built-in discovery, entry-point catalogue, conflicts, lazy loading, validation |
| `pyages/lpm/factory.py` | Parameter precedence, construction, and provenance attachment |
| `pyages/lpm/checks.py` | Deterministic integration checker |
| `pyages/cli/templates/_lpm_sources.py` | Documented scientific source and YAML templates |
| `pyages/cli/templates/lpm_template.py` | Rendering and atomic project generation |

Small adapters in the CLI, configuration, and workflows expose these services
and carry the chosen parameter directory and provenance into results. Existing
LPM formulas and convolution loops are unchanged.

The mechanism uses `importlib.metadata` from the Python standard library and
adds no runtime dependency. Discovery happens once per process; the selected
plugin is imported once and its definition is cached.

## Maintained examples and tests

The repository contains two complete reference packages:

| Location | Demonstrates |
| --- | --- |
| `examples/templates/external_lpm_plugin_scipy` | A gamma model backed by `scipy.stats.gamma` through `LpmScipy` |
| `examples/templates/external_lpm_plugin` | A bounded-power model implementing the complete law with NumPy through `LpmBase` |

Both contain real packaging metadata and an entry point, packaged parameters,
exact scientific tests, and an English task-oriented README.

The main test suite covers lazy metadata discovery, single loading, packaged
parameters, explicit overrides, conflicts, API mismatch, CLI generation,
integration checking, workflow provenance, and actual temporary installations
of both maintained examples. Their own scientific tests are run against the
installed packages as part of that boundary test.

## Short summary

```text
author writes model.py + params.yaml + scientific tests
                        │
package installation records one pyages.lpms entry point
                        │
PyAges lists metadata without importing plugin code
                        │
build_lpm("name") loads and validates only that provider
                        │
workflows record provider identity and the exact YAML digest
```

The extension mechanism changes how PyAges finds a model, not how users build
one and not how numerical methods call it.
