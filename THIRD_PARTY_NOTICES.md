# Third-party dependency notices

PyAges source code is distributed under CeCILL 2.1. The Python and .NET packages
below are dependencies, installed separately by package managers; their code is
not copied into the PyAges source tree or its Python wheel. Each dependency
retains its own copyright and licence terms. Binary distributions of these
projects can also contain separately licensed components; consult the notices
shipped with the exact package artifact being redistributed.

This audit records the direct dependency versions qualified in
`install/constraints.txt` and the NuGet versions declared in project files on
2 September 2026. The dependency declarations in `pyproject.toml`, .NET project
files, and the upstream package artifacts remain authoritative.

| Dependency | Qualified version | Upstream licence metadata |
| --- | --- | --- |
| `numpy` | `2.5.2` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `scipy` | `1.18.1` | BSD licence; additional bundled-component notices apply to binary artifacts |
| `pandas` | `3.0.5` | BSD licence |
| `matplotlib` | `3.11.1` | Python Software Foundation licence |
| `PyYAML` | `6.0.3` | MIT |
| `click` | `8.4.2` | BSD-3-Clause |
| `pydantic` | `2.13.4` | MIT |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause |
| `build` | `1.5.0` | MIT |
| `pip-audit` | `2.10.1` | Apache-2.0 |
| `pytest` | `9.1.1` | MIT |
| `pytest-cov` | `7.1.0` | MIT |
| `pyright` | `1.1.411` | MIT |
| `ruff` | `0.16.4` | MIT |
| `twine` | `7.0.0` | Apache-2.0 |
| `sphinx` | `9.1.0` | BSD-2-Clause |
| `myst-parser` | `5.1.0` | MIT |
| `sphinxcontrib-mermaid` | `2.1.0` | BSD-2-Clause |
| `sphinx-rtd-theme` | `3.1.0` | MIT |
| `openpyxl` | `3.1.5` | MIT |
| `ipython` | `9.16.1` | BSD-3-Clause |
| `jupyterlab` | `4.6.3` | BSD licence |
| `YamlDotNet` | `16.3.0` | MIT |

The direct dependencies use permissive terms and are consumed as external
modules. No incompatible copied or vendored source was identified in the PyAges
source tree during this audit. This inventory should be reviewed whenever a
dependency or its qualified version changes.
