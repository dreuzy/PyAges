Install

Create the conda environment:

```
conda env create -f install/environment.yml
```

`install/environment.yml` includes `conda-forge` because media-related optional
packages such as `imageio-ffmpeg` are not available on `defaults` alone.

Activate it and install PyAge (enables the `pyage` CLI):

```
conda activate pyage
pip install -e .
```

Notes:
- Extra tools in the environment (e.g., `jupyter`, `spyder`, `ffmpeg`, `imageio`)
  are optional and used for notebooks, plotting, or media exports.
