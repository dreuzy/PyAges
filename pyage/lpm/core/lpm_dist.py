# -*- coding: utf-8 -*-
"""
Created on Sun May 23 21:53:11 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Storage and analysis of LPM parameter distributions.
Provides utilities to append simulation results, compute summary statistics,
visualize parameter/concentration distributions, and write outputs to disk.
"""

import copy

import numpy as np  # Arrays
import pandas as pd  # Tables-Arrays

from pyage.config.runtime import arange_n


class LpmDist:
    """
    Distribution of LPM parameter values and derived metrics.

    Each row in the internal dataframe represents one simulation, with
    parameter values, objective function value, and optional concentrations.

    Attributes
    ----------
    __lpm_template : LPM
        Template distribution used to interpret parameter names and moments.
    __c_names : list[str]
        Concentration names corresponding to the stored outputs.
    __dist : pandas.DataFrame
        Storage for parameters, objective function, and concentrations.
    """

    def __init__(self, lpm, c_names):
        """
        Initialize an empty distribution container.

        Parameters
        ----------
        lpm : LPM
            Template model defining parameter names and distributions.
        c_names : list[str]
            Names of the concentration columns to be stored.
        """
        self.__lpm_template = lpm
        self.__c_names = c_names
        self.__dist = pd.DataFrame(
            columns=self.__lpm_template.get_param_names() + ["obj_function"] + c_names
        )

    @property
    def lpm_template(self):
        """Return the model template used to interpret stored samples."""
        return self.__lpm_template

    def dist(self):
        """
        Return the current distribution dataframe.
        """
        return self.__dist

    def get_param_names(self):
        """
        Return the parameter names carried by the template LPM.
        """
        return list(self.__lpm_template.get_param_names())

    def get_concentration_names(self):
        """
        Return the concentration column names stored in the distribution.
        """
        return list(self.__c_names)

    def best_row(self):
        """
        Return the row with the smallest objective function.

        Returns
        -------
        pandas.Series | None
            Best row, or ``None`` when the distribution is empty.
        """
        if self.__dist.empty:
            return None
        if "obj_function" not in self.__dist.columns:
            return self.__dist.iloc[0].copy()
        values = pd.to_numeric(self.__dist["obj_function"], errors="coerce")
        if values.isna().all():
            return self.__dist.iloc[0].copy()
        return self.__dist.loc[values.idxmin()].copy()

    def validate(self):
        """
        Validate that the distribution has the expected columns.

        Raises
        ------
        ValueError
            If required columns are missing from the distribution dataframe.
        """
        expected = set(
            self.__lpm_template.get_param_names()
            + ["obj_function"]
            + list(self.__c_names)
        )
        missing = expected.difference(self.__dist.columns)
        if missing:
            raise ValueError(f"Missing distribution columns: {sorted(missing)}")

    def dist_append(
        self, params, obj_function=-1, param_in_bounds=None, concentrations=None
    ):
        """
        Append one simulation result to the distribution.

        Parameters
        ----------
        params : dict[str, float]
            Parameter values, keyed by parameter name.
        obj_function : float, optional
            Objective function value for this simulation.
        param_in_bounds : bool, optional
            Flag indicating whether parameters were within bounds.
        concentrations : sequence[float], optional
            Concentration values aligned with ``__c_names``.
        """

        row = {}
        for t in self.__lpm_template.p:
            row[t] = [params[t]]
        row["obj_function"] = [obj_function]
        if param_in_bounds is not None:
            row["param_in_bounds"] = [param_in_bounds]
        if concentrations is not None:
            for elt, i in zip(self.__c_names, range(len(concentrations))):
                row[elt] = [concentrations[i]]
        if self.__dist.empty:
            self.__dist = pd.DataFrame.from_dict(row, orient="columns")
        else:
            self.__dist = pd.concat(
                [self.__dist, pd.DataFrame.from_dict(row, orient="columns")]
            )

    def dist_append_array(
        self, params, obj_function=-1, param_in_bounds=None, concentrations=None
    ):
        """
        Append one simulation using a parameter vector.

        Parameters
        ----------
        params : sequence[float]
            Parameter values in the template order.
        obj_function : float, optional
            Objective function value for this simulation.
        param_in_bounds : bool, optional
            Flag indicating whether parameters were within bounds.
        concentrations : sequence[float], optional
            Concentration values aligned with ``__c_names``.
        """
        params_dic = {}
        k = 0
        for t in self.__lpm_template.p:
            params_dic[t] = params[k]
            k += 1
        self.dist_append(
            params_dic,
            obj_function=obj_function,
            param_in_bounds=param_in_bounds,
            concentrations=concentrations,
        )

    def append(self, other):
        """
        Concatenate another LpmDist distribution into this one.

        Parameters
        ----------
        other : LpmDist
            Another instance to merge into this distribution.
        """
        # concat self.__dist=self.__dist.append(other.__dist,ignore_index=True)
        if self.__dist.empty:
            self.__dist = other.__dist
        else:
            self.__dist = pd.concat([self.__dist, other.__dist], ignore_index=True)

    def get_selection(self, lpm_number, time_span_mode, array_resolution=1000):
        """
        Get a selection of LPMs and their PDFs from the distribution.

        Parameters
        ----------
        lpm_number : int
            Number of lpm to select (redundancies possible)
            The default is 10.
        time_span_mode : str
            Selection mode identifier used to pick sampling strategy
            (e.g., contains "span" for span-based sampling).
        array_resolution : int
            Number of time steps for the time resolution of pdf.
            The default is 1000.

        Returns
        -------
        lpm_list : array of lpms
            Selected models
        pdf : dataframe
            corresponding pdfs
        lpm_statistics : dataframe
            corresponding statistics on lpms
        """
        rng = np.random.default_rng(12345)
        t_grid, pdf_array, pdf_colname = self._init_pdf_storage(
            lpm_number, array_resolution
        )
        lpm_statistics = pd.DataFrame(
            index=range(lpm_number), columns=self.__lpm_template.moments_name()
        )
        lpm_list = []
        for i in range(1, lpm_number + 1):
            option = "random_each" if "span" in time_span_mode else "random_line"
            test, line = self.__lpm_template.load_lpm_from_dist(
                self.__dist, option=option, rng=rng
            )
            if test:
                lpm_list.append(copy.deepcopy(self.__lpm_template))
                pdf_array[i, :] = self.__lpm_template.pdf(t_grid)
                pdf_colname.append("p" + str(line))
                lpm_statistics.iloc[i - 1] = self.__lpm_template.moments()
            else:
                pdf_colname.append("p")
        pdf = pd.DataFrame(pdf_array.T, columns=pdf_colname)
        return lpm_list, pdf, lpm_statistics

    def fill_np_array(self, array_results, column_names):
        """
        Fill the distribution from a numeric array.

        Parameters
        ----------
        array_results : np.array
            result values
        column_names : list of str
            column names
        """
        self.__dist = pd.DataFrame(data=array_results, columns=column_names)

    def get_best_lpm(self):
        """
        Return the LPM instance with the smallest objective function.

        Returns
        -------
        tuple[bool, LPM | None]
            (True, lpm) if available, otherwise (False, None).
        """
        lpm = copy.deepcopy(self.__lpm_template)
        if self.__dist.shape[0] == 0:
            return False, None
        imin = self.__dist.idxmin(axis=0, skipna=True)
        for key in lpm.p:
            lpm.p[key] = self.__dist.loc[imin][key]
        return True, lpm

    def display_points_alone(self):
        """
        Plot a simple scatter of the first two parameters.
        """
        from pyage.lpm.distribution_plotting import plot_points

        plot_points(self)

    def display_param_vs_param(self, keyx, keyy):
        """
        Plot one parameter against another.

        Parameters
        ----------
        keyx : str
            Name of parameter for the absciss
        key2 : str
            Name of parameter for the ordinate

        """
        from pyage.lpm.distribution_plotting import plot_parameter_pair

        plot_parameter_pair(self, keyx, keyy)

    def display_parameters_dist(
        self,
        self_method="",
        lpm_reference=None,
        bins=30,
        lpm_2nd=None,
        lpm_2nd_method="",
        directory=None,
        display_text=False,
    ):
        """
        Display distributions and pairwise plots of parameters.

        Parameters
        ----------
        self_method : str, optional
            Label for the current method.
        lpm_reference : LPM, optional
            Reference LPM for vertical reference lines.
        bins : int, optional
            Histogram bin count (currently unused here).
        lpm_2nd : LpmDist, optional
            Secondary distribution to overlay.
        lpm_2nd_method : str, optional
            Label for the secondary distribution.
        directory : str | Path, optional
            Output directory for saved figures.
        display_text : bool, optional
            If True, print section labels to stdout.
        """
        from pyage.lpm.distribution_plotting import display_parameter_distributions

        display_parameter_distributions(
            self,
            self_method,
            lpm_reference,
            bins,
            lpm_2nd,
            lpm_2nd_method,
            directory,
            display_text,
        )

    def display_parameters_dist_comp_apriori(
        self,
        lpm_reference=None,
        bins=30,
        lpm_2nd=None,
        lpm_2nd_method="",
        directory=None,
        display_text=False,
        prior="",
    ):
        """
        Display parameter distributions compared to an apriori distribution.

        Parameters
        ----------
        lpm_reference : LPM, optional
            Reference LPM for vertical reference lines.
        bins : int, optional
            Histogram bin count (currently unused here).
        lpm_2nd : LpmDist, optional
            Secondary distribution to overlay.
        lpm_2nd_method : str, optional
            Label for the secondary distribution.
        directory : str | Path, optional
            Output directory for saved figures.
        display_text : bool, optional
            If True, print section labels to stdout.
        prior : object, optional
            Prior distribution structure used for overlay.
        """
        from pyage.lpm.distribution_plotting import display_parameter_priors

        display_parameter_priors(
            self,
            lpm_reference,
            bins,
            lpm_2nd,
            lpm_2nd_method,
            directory,
            display_text,
            prior,
        )

    def display_concentrations_dist(
        self,
        self_method="",
        concentrations_reference=None,
        lpm_2nd=None,
        lpm_2nd_method="",
        directory=None,
    ):
        """
        Display pairwise concentration distributions.

        Parameters
        ----------
        self_method : str, optional
            Label for the current method.
        concentrations_reference : Concentrations, optional
            Reference concentrations for plotting markers.
        lpm_2nd : LpmDist, optional
            Secondary distribution to overlay.
        lpm_2nd_method : str, optional
            Label for the secondary distribution.
        directory : str | Path, optional
            Output directory for saved figures.
        """
        from pyage.lpm.distribution_plotting import display_concentration_distributions

        display_concentration_distributions(
            self,
            self_method,
            concentrations_reference,
            lpm_2nd,
            lpm_2nd_method,
            directory,
        )

    def stats_distribution(self):
        """
        Add statistics columns to the distribution.

        Statistics include mean, standard deviation, and quantiles from
        ``self.__lpm_template.moments()`` for each stored LPM.
        """
        # Stat names and result structure
        stats_name = self.__lpm_template.moments_name()
        stats_value = np.zeros([self.__dist.shape[0], len(stats_name)])
        # Loop over all stored lpms
        for ind in self.__dist.index:
            [test, line] = self.__lpm_template.load_lpm_from_dist(
                self.__dist, option="line", line_no=ind
            )
            stats_value[ind] = self.__lpm_template.moments()
        # Concatenates frame
        self.__dist = pd.concat(
            [self.__dist, pd.DataFrame(stats_value, columns=stats_name)], axis=1
        )
        return self

    def _init_pdf_storage(self, lpm_number, array_resolution):
        """
        Prepare PDF storage arrays for a selection of LPMs.

        Returns
        -------
        tuple
            (t_grid, pdf_array, pdf_colname) for PDF assembly.
        """
        t_grid = arange_n(0, 70, array_resolution - 1)
        pdf_array = np.empty((lpm_number + 1, array_resolution))
        pdf_array[0, :] = t_grid
        return t_grid, pdf_array, ["t"]

    def compute_dist(self):
        """
        Return the current distribution dataframe (compatibility alias).
        """
        return self.dist()

    def write_dist(self, file):
        """
        Write the full distribution to disk.

        Parameters
        ----------
        file : str | Path
            Target file path for the distribution table.
        """
        from pyage.data_io.lpm_distribution import write_distribution

        write_distribution(self, file)

    def _histogram_for_param(self, param_name, nb_bins):
        """
        Compute the histogram for a single parameter.
        """
        values = self.__dist.loc[:, param_name]
        hist, bins = np.histogram(values, bins=nb_bins, density="True")
        return hist, bins

    def compute_histograms(self, nb_bins=100):
        """
        Compute histograms for each parameter.
        """
        histograms = {}
        for key in self.__lpm_template.p:
            hist, bins = self._histogram_for_param(key, nb_bins)
            histograms[key] = {"bins": bins, "hist": hist}
        return histograms

    def write_histograms(self, file):
        """
        Write one histogram file per parameter.

        Parameters
        ----------
        file : str | Path
            Base output path. Parameter names are inserted into the filename.
        """
        from pyage.data_io.lpm_distribution import write_histograms

        write_histograms(self, file)

    def compute_stats(self):
        """
        Compute statistics of parameter and objective function distributions.
        """
        return self.__dist.describe()

    def get_stats(self):
        """
        Return statistics of parameter and objective function distributions.
        """
        return self.compute_stats()

    def get_stats_line(self, lpm_target, data):
        """
        Append target comparison stats into an output dict.

        Parameters
        ----------
        lpm_target : LPM
            Reference LPM for comparison.
        data : dict
            Output dict to be updated in-place.
        """
        stats = self.get_stats()
        for key in lpm_target.p:
            data[key + "_" + "target"] = [lpm_target.p[key]]
            data[key + "_" + "difference"] = [
                stats.loc["mean"][key] - lpm_target.p[key]
            ]
            data[key + "_" + "rate_mean"] = [stats.loc["mean"][key] / lpm_target.p[key]]
            data[key + "_" + "rate_std"] = [stats.loc["std"][key] / lpm_target.p[key]]
        for col in stats.columns:
            for row in stats.index:
                data[col + "_" + row] = [stats.loc[row][col]]

    def write_stats(self, file):
        """
        Write statistics of parameter and objective function distributions.

        Parameters
        ----------
        file : str | Path
            Target file path for the statistics table.
        """
        from pyage.data_io.lpm_distribution import write_statistics

        write_statistics(self, file)
