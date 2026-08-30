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
$env:PYTHONNOUSERSITE = "1"  # PowerShell; use export ...=1 in POSIX shells
python -m pip install --no-deps -e .
```

Keep `PYTHONNOUSERSITE=1` set for the preflight and the complete campaign. This
prevents packages installed in the per-user Python directory from shadowing the
qualified Conda environment. The Windows reproduction wrappers set it
automatically.

`constraints.txt` is the separately qualified baseline for the PyAges 1.0
user/development environment. It pins SciPy 1.18.1 and is
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

The package metadata accepts pandas 2.2 through the 3.x series. The normal CI
matrix exercises the qualified pandas 3 pin from `constraints.txt`. A separate
compatibility job installs pandas 2.2.3, promotes `FutureWarning` to errors, and
repeats the suite with future string inference and Copy-on-Write diagnostics
enabled. The historical article environment remains pinned independently and
is not changed by this compatibility check.

The optional IDE and media stack is intentionally separate from the reference
environment because it is not required by the package:

```bash
conda install -c conda-forge spyder imageio ffmpeg av imageio-ffmpeg
```

The distribution, import package, and CLI share the same `pyages` name. The
stable `1.0.1` distribution is published on
[PyPI](https://pypi.org/project/pyages/1.0.1/) and can be installed with:

```bash
python -m pip install "pyages==1.0.1"
pyages check
```

Use the editable commands above for development or exact source-checkout
qualification. The `--pre` flag is needed only when deliberately installing a
published beta or release-candidate version. Python code continues to use
`import pyages`.
