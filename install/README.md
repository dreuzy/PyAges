Install

Create the conda environment:

```
conda env create -f install/environment.yml
```

Activate it and install PyAge (enables the `pyage` CLI):

```
conda activate pyage
pip install -e .
```

Notes:
- Extra tools in the environment (e.g., `jupyter`, `spyder`, `ffmpeg`, `imageio`)
  are optional and used for notebooks, plotting, or media exports.
