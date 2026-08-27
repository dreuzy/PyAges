# Installation environments

PyAges deliberately records two different environments.

`environment.yml` is the Python 3.12 baseline for reproducing the historical
article campaign. Its recorded scientific core is Python 3.12, NumPy 2.1.2,
SciPy 1.14.1, pandas 2.2.3, and Matplotlib 3.10.8. It is not the PyAges 1.0 user
environment and does not retroactively qualify the archived campaign on newer
dependencies. It records the direct environment, not the exact historical
platform-specific transitive solve. Create it from the repository root and
install PyAges without changing those dependencies with:

```bash
conda env create -f install/environment.yml
conda activate pyages-article-reproduction
python -m pip install --no-deps -e .
```

`constraints.txt` is the separately qualified candidate baseline for the
future PyAges 1.0 user/development environment. It pins SciPy 1.18.1 and is
exercised by CI on Python 3.12, 3.13, and 3.14. Create a normal virtual
environment, then install PyAges with:

```bash
python -m pip install -c install/constraints.txt -e .
```

For development, documentation, tests, and release checks, install the declared
extras instead:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

Omit `-c install/constraints.txt` only when deliberately testing newer direct
dependencies against the compatibility ranges declared in `pyproject.toml`.
The constraints qualify direct dependencies; they are not a bit-for-bit lock
of platform-specific transitive packages.

The package metadata accepts SciPy 1.14.1 through the 1.18 series on Python
3.12 and 3.13. Python 3.14 requires SciPy 1.16.1 or newer because 1.14.1 has no
CPython 3.14 wheel. CI tests both these lower boundaries and the user pin. The
versions and wheel availability can be checked in the official PyPI records
for [SciPy 1.14.1](https://pypi.org/project/scipy/1.14.1/),
[SciPy 1.16.1](https://pypi.org/project/scipy/1.16.1/), and
[SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/).

The optional IDE and media stack is intentionally separate from the reference
environment because it is not required by the package:

```bash
conda install -c conda-forge spyder imageio ffmpeg av imageio-ffmpeg
```

The distribution, import package, and CLI share the same `pyages` name. No
PyAges distribution is currently published on PyPI; after a beta or release
candidate is uploaded, install it with:

```bash
python -m pip install --pre pyages
pyages check
```

The `--pre` flag is needed for beta and release-candidate versions. Python code
continues to use `import pyages`.
