# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Matplotlib runtime helpers for packaged workflows.
"""


def configure_backend(force_inline=False):
    """
    Purpose
    -------
    Configure matplotlib backend depending on environment.

    Returns
    -------
    bool
        True when running inside an IPython kernel.
    """
    import matplotlib

    try:
        from IPython import get_ipython

        ipy = get_ipython()
        if ipy is not None:
            ipy.run_line_magic("matplotlib", "inline")
        if ipy is not None or force_inline:
            try:
                import matplotlib.pyplot as plt

                plt.switch_backend("module://matplotlib_inline.backend_inline")
            except Exception:
                pass
            return True
        matplotlib.use("TkAgg")
        return False
    except Exception:
        matplotlib.use("TkAgg")
        return False


def enable_interactive(plt):
    """
    Purpose
    -------
    Enable interactive mode for long-running scripts.
    """
    plt.ion()


def show_figures(plt, is_interactive):
    """
    Purpose
    -------
    Flush figures in interactive mode.
    """
    if is_interactive:
        plt.show()
