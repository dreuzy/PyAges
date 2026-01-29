# -*- coding: utf-8 -*-
"""
Legacy entrypoints for Ploemeur helpers.

This module now re-exports dataset helpers from ``sites.ploemeur.observations.ploemeur``.
"""

from pyage.observations.loader import build_observation_file, load_observation_concentrations
from sites.ploemeur.observations import ploemeur as ploemeur_obs

__all__ = [
    "ploemeur_data_folder",
    "ploemeur_brut_folder",
    "ploemeur_ori_folder",
    "ploemeur_results_folder",
    "ploemeur_file_ori",
    "ploemeur_concentrations_ori",
    "ploemoeur_concentrations_ori",
]


def ploemeur_data_folder():
    return ploemeur_obs.ploemeur_data_folder()


def ploemeur_brut_folder():
    return ploemeur_obs.ploemeur_brut_folder()


def ploemeur_ori_folder():
    return ploemeur_obs.ploemeur_ori_folder()


def ploemeur_results_folder(file_root):
    return ploemeur_obs.ploemeur_results_folder(file_root)


def ploemeur_file_ori(well, dates):
    return build_observation_file(ploemeur_obs.ploemeur_ori_folder(), "ori_ploemeur_", well, dates)


def ploemeur_concentrations_ori(well, dates):
    return load_observation_concentrations(
        ploemeur_obs.ploemeur_ori_folder(),
        "ori_ploemeur_",
        well,
        dates,
    )


def ploemoeur_concentrations_ori(well, dates):
    return ploemeur_concentrations_ori(well, dates)

