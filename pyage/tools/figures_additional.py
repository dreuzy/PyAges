# -*- coding: utf-8 -*-
"""
Created on Mon May 24 17:03:47 2021

@author: Jean-Raynald de Dreuzy
"""

import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


def figure_init(xlab=None, ylab=None, figname=None, figsize=(6, 4)):
    """
    Initialise une figure et un axe avec un style homogène.
    Retourne fig, ax pour un usage orienté objet.
    """
    fig, ax = plt.subplots(figsize=figsize)

    ax.set_xlabel(xlab, fontsize=16, fontweight="bold")
    ax.set_ylabel(ylab, fontsize=14, fontweight="bold")
    ax.tick_params(axis="x", labelsize=14)
    ax.tick_params(axis="y", labelsize=14)
    ax.grid(True)
    ax.set_title(figname, fontsize=22, fontweight="bold")

    return fig, ax


def figure_close(filename=None):
    """Save and close the current figure when a target filename is provided."""
    if filename is not None:
        plt.savefig(filename, dpi=300)
        plt.close()


def cmap_white_jet():
    """Colormap jet with lowest values white instead of blue"""
    k = 4
    # set upper part: 4 * 256/4 entries
    upper = mpl.cm.jet(np.arange(256))
    # set lower part: 1 * 256/4 entries
    # - initialize all entries to 1 to make sure that the alpha channel (4th column) is 1
    lower = np.ones((int(256 / k), 4))
    # - modify the first three columns (RGB):
    #   range linearly between white (1,1,1) and the first color of the upper colormap
    for i in range(3):
        lower[:, i] = np.linspace(1, upper[0, i], lower.shape[0])
    # combine parts of colormap
    cmap = np.vstack((lower, upper))
    # convert to matplotlib colormap
    cmap = mpl.colors.ListedColormap(cmap, name="myColorMap")
    return cmap


def hist_scatter(
    histo=False,
    histox=None,
    histoy=None,
    histolegend="",
    scatter=False,
    scatterx=None,
    scattery=None,
    scatterlegend="",
    refx=None,
    refy=None,
    reflegend="",
    namex=None,
    namey=None,
    namefig=None,
    directory=None,
    file=None,
):
    """Histogram and scatter plot"""
    # Initialization of figure
    figure_init(xlab=namex, ylab=namey, figname=namefig)
    minix = math.inf
    maxix = -math.inf
    miniy = math.inf
    maxiy = -math.inf
    # Histogram
    if histo:
        plt.hist2d(histox, histoy, bins=50, cmap=cmap_white_jet(), label=histolegend)
        plt.colorbar()
        minix = min(minix, min(histox))
        maxix = max(maxix, max(histox))
        miniy = min(miniy, min(histoy))
        maxiy = max(maxiy, max(histoy))
    # Scatter
    if scatter:
        plt.scatter(scatterx, scattery, marker="+", c="r", s=40, label=scatterlegend)
        minix = min(minix, min(scatterx))
        maxix = max(maxix, max(scatterx))
        miniy = min(miniy, min(scattery))
        maxiy = max(maxiy, max(scattery))
    # Reference
    if refx is not None:
        plt.scatter(refx, refy, marker="o", c="r", s=150, label=reflegend)
        minix = min(minix, refx)
        maxix = max(maxix, refx)
        miniy = min(miniy, refy)
        maxiy = max(maxiy, refy)
    # Figure limits
    if minix != maxix:
        plt.xlim(minix, maxix)
    if miniy != maxiy:
        plt.ylim(miniy, maxiy)
    # Figure Management
    if directory is not None:
        if file is None:
            raise ValueError("file must be provided when directory is set")
        figure_close(filename=Path(directory) / file)
