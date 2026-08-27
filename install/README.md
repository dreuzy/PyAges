# Installation environments

`environment.yml` is the qualified Python 3.12 environment for running PyAge,
its examples, and its notebooks. Its direct dependencies are pinned to the
same versions as `constraints.txt`; transitive packages remain selected by
Conda for the current operating system.

PyAge supports Python 3.12 through 3.14. Python 3.12 is retained for the
reference environment because it is the oldest supported interpreter and
therefore exercises the strictest compatibility boundary.

From the repository root, create and activate the environment:

```bash
conda env create -f install/environment.yml
conda activate pyage
```

For normal use, install PyAge in editable mode:

```bash
python -m pip install -e .
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

The optional IDE and media stack is intentionally separate from the reference
environment because it is not required by the package:

```bash
conda install -c conda-forge spyder imageio ffmpeg av imageio-ffmpeg
```

For a published release, the distribution name differs from the import name:

```bash
python -m pip install --pre pyage-groundwater
pyage check
```

The current beta is distributed from the GitHub source tree and is not yet
published on PyPI. The command above becomes available only after a package
release is published. The `--pre` flag is needed for beta and release-candidate
versions. Python code continues to use `import pyage`.
