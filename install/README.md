# Installation environments

`environment.yml` is the reference Python 3.12 environment for running PyAge
and its notebooks. Runtime dependency bounds mirror `pyproject.toml`; conda is
used for the scientific stack, then pip installs the local package.

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
python -m pip install -e ".[dev,docs]"
```

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

The `--pre` flag is needed for beta and release-candidate versions. Python code
continues to use `import pyage`.
