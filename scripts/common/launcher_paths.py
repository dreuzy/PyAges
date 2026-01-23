# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Helper functions for launcher output paths.
"""


def results_directory(gp, dataset_name):
    """
    Purpose
    -------
    Build the base results directory for a dataset.

    Parameters
    ----------
    gp : module
        global_parameters module.
    dataset_name : str
        Dataset identifier used to name the output folder.

    Returns
    -------
    str
        Full output path for results/test_cases/<dataset_name>.
    """
    base = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS, "test_cases")
    return gp.results_directory(base, dataset_name)
