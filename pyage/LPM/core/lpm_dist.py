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
import matplotlib.pyplot as plt         # Plots
import numpy as np                      # Arrays
import os
import pandas as pd                     # Tables-Arrays

import global_parameters as gp
import tools.figures_additional as figadd
import tools.dist_hist as dist_hist
from pathlib import Path

from IPython.display import display




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
        self.__dist = pd.DataFrame(columns = self.__lpm_template.get_param_names() + ['obj_function'] + c_names)


    def dist(self):
        """
        Return the current distribution dataframe.
        """
        return self.__dist


    def validate(self):
        """
        Validate that the distribution has the expected columns.

        Raises
        ------
        ValueError
            If required columns are missing from the distribution dataframe.
        """
        expected = set(self.__lpm_template.get_param_names() + ["obj_function"] + list(self.__c_names))
        missing = expected.difference(self.__dist.columns)
        if missing:
            raise ValueError(f"Missing distribution columns: {sorted(missing)}")
            
            
    def dist_append(self, params, obj_function=-1, param_in_bounds=None, concentrations=None):
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
        
        row={}
        for t in self.__lpm_template.p:
            row[t]=[params[t]]
        row['obj_function']=[obj_function]
        if param_in_bounds != None : 
            row['param_in_bounds']=[param_in_bounds]
        if concentrations != None :
            for elt, i in zip(self.__c_names, range(len(concentrations))):
                row[elt]=[concentrations[i]] 
        if self.__dist.empty: 
            self.__dist = pd.DataFrame.from_dict(row,orient='columns')
        else:
            self.__dist = pd.concat([self.__dist,pd.DataFrame.from_dict(row,orient='columns')]) 


    def dist_append_array(self, params, obj_function=-1, param_in_bounds=None, concentrations=None):
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
        params_dic={}; k=0
        for t in self.__lpm_template.p:
            params_dic[t]=params[k]; k=k+1
        self.dist_append(params_dic,obj_function=obj_function,param_in_bounds=param_in_bounds,concentrations=concentrations)
        

    def append(self, other): 
        """
        Concatenate another LpmDist distribution into this one.

        Parameters
        ----------
        other : LpmDist
            Another instance to merge into this distribution.
        """
        #concat self.__dist=self.__dist.append(other.__dist,ignore_index=True)
        if self.__dist.empty: 
            self.__dist = other.__dist
        else:
            self.__dist=pd.concat([self.__dist,other.__dist],ignore_index=True)

        
        
    
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
        t_grid, pdf_array, pdf_colname = self._init_pdf_storage(lpm_number, array_resolution)
        lpm_statistics = pd.DataFrame(index=range(lpm_number), columns=self.__lpm_template.moments_name())
        lpm_list = []
        for i in range(1, lpm_number + 1):
            option = "random_each" if "span" in time_span_mode else "random_line"
            test, line = self.__lpm_template.load_lpm_from_dist(self.__dist, option=option, rng=rng)
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
        self.__dist=pd.DataFrame(data=array_results,columns=column_names)
        
            
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
            lpm.p[key]=self.__dist.loc[imin][key]
        return True, lpm
     

    def display_points_alone(self): 
        """
        Plot a simple scatter of the first two parameters.
        """
        x=[]
        for key in self.__lpm_template.p:
            x.append(self.__dist[key])
        if len(x)==2: 
            plt.scatter(x[1][1:600],x[0][1:600],c='black',s=3,marker='.')
         
            
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
        plt.scatter(self.__dist[keyx], self.__dist[keyy], marker='+', c = 'red', s=10, label="model")
        

    def display_parameters_dist(self, self_method="", lpm_reference=None, bins=30, lpm_2nd=None, lpm_2nd_method="", directory=None, display_text=False):
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
        # Shows histogram of the parameters
        if display_text:
            print("DISTRIBUTION OF PARAMETERS")
        for key in self.__lpm_template.p:
            self._plot_param_histogram(
                key,
                self_method,
                lpm_reference,
                lpm_2nd,
                lpm_2nd_method,
                directory,
            )
        
        # 2D plots parameter/obj-function
        if display_text:
            print("OBJECTIVE FUNCTION")
        for key in self.__lpm_template.p:
            self._plot_obj_vs_param(
                key,
                self_method,
                lpm_reference,
                lpm_2nd,
                lpm_2nd_method,
                directory,
            )
            
        # 2D plots between parameters
        if display_text:
            print("PARAMETERS")
        if len(self.__lpm_template.p) >= 2:
            names = list(self.__lpm_template.p.keys())
            for i in range(len(self.__lpm_template.p)):
                self._plot_param_pair(
                    names,
                    i,
                    self_method,
                    lpm_reference,
                    lpm_2nd,
                    lpm_2nd_method,
                    directory,
                )


    def display_parameters_dist_comp_apriori(self, lpm_reference=None, bins=30, lpm_2nd=None, lpm_2nd_method="", directory=None, display_text=False, prior=""):
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
        # Shows histogram of the parameters
        if display_text:
            print("DISTRIBUTION OF PARAMETERS")
        for key in self.__lpm_template.p:
            self._plot_param_histogram_apriori(
                key,
                lpm_reference,
                lpm_2nd,
                lpm_2nd_method,
                directory,
                prior,
            )


    def display_concentrations_dist(self, self_method="", concentrations_reference=None, lpm_2nd=None, lpm_2nd_method="", directory=None):
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
        # Loop other successive concentrations
        for i in range(len(self.__c_names)):
            i1 = (i + 1) % len(self.__c_names)
            self._plot_concentration_pair(
                i,
                i1,
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
        stats_name=self.__lpm_template.moments_name()
        stats_value=np.zeros([self.__dist.shape[0],len(stats_name)])
        # Loop over all stored lpms
        for ind in self.__dist.index:
            [test,line]=self.__lpm_template.load_lpm_from_dist(self.__dist,option="line",line_no=ind)
            stats_value[ind]=self.__lpm_template.moments()
        # Concatenates frame
        self.__dist=pd.concat([self.__dist,pd.DataFrame(stats_value,columns=stats_name)],axis=1)
        return self


    def _init_pdf_storage(self, lpm_number, array_resolution):
        """
        Prepare PDF storage arrays for a selection of LPMs.

        Returns
        -------
        tuple
            (t_grid, pdf_array, pdf_colname) for PDF assembly.
        """
        t_grid = gp.arange_n(0, 70, array_resolution - 1)
        pdf_array = np.empty((lpm_number + 1, array_resolution))
        pdf_array[0, :] = t_grid
        return t_grid, pdf_array, ["t"]


    def _plot_param_histogram(
        self,
        key,
        self_method,
        lpm_reference,
        lpm_2nd,
        lpm_2nd_method,
        directory,
    ):
        """
        Plot a histogram for one parameter, with optional overlays.
        """
        values = np.asarray(self.__dist[key].tolist(), dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return
        figadd.figure_init(xlab=key, ylab="Count", figname=self.__lpm_template.name)
        binwidth = self.__lpm_template.get_param_range(key) / 100
        if not np.isfinite(binwidth) or binwidth <= 0:
            return
        bins = np.arange(
            min(max(values) / 2, self.__lpm_template.get_p_min(key)),
            self.__lpm_template.get_p_max(key) + binwidth,
            binwidth,
        )
        if bins.size < 2:
            return
        plt.hist(
            values,
            density=True,
            bins=bins,
            histtype="barstacked",
            label=self_method,
        )
        if lpm_reference is not None:
            plt.axvline(lpm_reference.p[key], c="k", linewidth=2.0, label="reference")
        if lpm_2nd is not None:
            values_2nd = np.asarray(lpm_2nd.__dist[key].tolist(), dtype=float)
            values_2nd = values_2nd[np.isfinite(values_2nd)]
            if values_2nd.size > 0:
                plt.hist(
                    values_2nd,
                    density=True,
                    bins=bins,
                    histtype="barstacked",
                    label=lpm_2nd_method,
                )
        plt.xlim(self.__lpm_template.get_p_min(key), self.__lpm_template.get_p_max(key))
        plt.legend()
        if directory is not None:
            figadd.figure_close(filename=os.path.join(directory, "comp_" + key))


    def _plot_obj_vs_param(
        self,
        key,
        self_method,
        lpm_reference,
        lpm_2nd,
        lpm_2nd_method,
        directory,
    ):
        """
        Plot objective function values against a parameter.
        """
        figadd.figure_init(xlab=key, ylab="obj_function", figname=self.__lpm_template.name)
        plt.scatter(
            self.__dist[key].tolist(),
            self.__dist["obj_function"].tolist(),
            marker="x",
            c="blue",
            s=10,
            label=self_method,
        )
        if lpm_reference is not None:
            plt.axvline(lpm_reference.p[key], c="k", linewidth=2.0, label="reference")
        if lpm_2nd is not None:
            plt.scatter(
                lpm_2nd.__dist[key],
                lpm_2nd.__dist["obj_function"],
                marker="+",
                c="red",
                s=10,
                label=lpm_2nd_method,
            )
        plt.legend()
        if directory is not None:
            figadd.figure_close(filename=os.path.join(directory, "objfunction_" + key))


    def _plot_param_pair(
        self,
        names,
        index,
        self_method,
        lpm_reference,
        lpm_2nd,
        lpm_2nd_method,
        directory,
    ):
        """
        Plot a pairwise parameter scatter/histogram comparison.
        """
        i1 = (index + 1) % len(self.__lpm_template.p)
        if lpm_2nd is None:
            histo = False
            histox = None
            histoy = None
        else:
            histo = True
            histox = lpm_2nd.__dist[names[index]]
            histoy = lpm_2nd.__dist[names[i1]]
        scatter = True
        scatterx = self.__dist[names[index]].tolist()
        scattery = self.__dist[names[i1]].tolist()
        if len(scatterx) == 0:
            scatterx = None
            scattery = None
        if lpm_reference is None:
            refx = None
            refy = None
        else:
            refx = lpm_reference.p[names[index]]
            refy = lpm_reference.p[names[i1]]
        figadd.hist_scatter(
            histo=histo,
            histox=histox,
            histoy=histoy,
            histolegend=lpm_2nd_method,
            scatter=scatter,
            scatterx=scatterx,
            scattery=scattery,
            scatterlegend=self_method,
            refx=refx,
            refy=refy,
            reflegend="reference",
            namex=names[index],
            namey=names[i1],
            namefig=self.__lpm_template.name,
            directory=directory,
            file="comp2D_" + names[index] + "_" + names[i1],
        )


    def _plot_param_histogram_apriori(
        self,
        key,
        lpm_reference,
        lpm_2nd,
        lpm_2nd_method,
        directory,
        prior,
    ):
        """
        Plot parameter histogram with an apriori distribution overlay.
        """
        values = np.asarray(self.__dist[key].tolist(), dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return
        figadd.figure_init(xlab=key, ylab="Count", figname=self.__lpm_template.name)
        binwidth = self.__lpm_template.get_param_range(key) / 100
        if not np.isfinite(binwidth) or binwidth <= 0:
            return
        bins = np.arange(
            min(max(values) / 2, self.__lpm_template.get_p_min(key)),
            self.__lpm_template.get_p_max(key) + binwidth,
            binwidth,
        )
        if bins.size < 2:
            return
        temp = plt.hist(
            values,
            density=True,
            bins=bins,
            histtype="barstacked",
            label="MH",
        )
        rescaling = (prior.MHapriori_para[key][2, 0] - prior.MHapriori_para[key][2 - 1, 0]) / (
            temp[1][2] - temp[1][2 - 1]
        )
        rescaling = 1 / rescaling
        rescaling = np.mean(temp[0] != 0) / np.mean(prior.MHapriori_para[key][:, 1] != 0)
        rescaling = np.mean(temp[0][temp[0][:] != 0]) / np.mean(
            prior.MHapriori_para[key][prior.MHapriori_para[key][:, 1] != 0, 1]
        )
        plt.plot(prior.MHapriori_para[key][:, 0], prior.MHapriori_para[key][:, 1] * rescaling)
        if lpm_reference is not None:
            plt.axvline(lpm_reference.p[key], c="k", linewidth=2.0, label="reference")
        if lpm_2nd is not None:
            values_2nd = np.asarray(lpm_2nd.__dist[key].tolist(), dtype=float)
            values_2nd = values_2nd[np.isfinite(values_2nd)]
            if values_2nd.size > 0:
                plt.hist(
                    values_2nd,
                    density=True,
                    bins=bins,
                    histtype="barstacked",
                    label=lpm_2nd_method,
                )
        plt.xlim(self.__lpm_template.get_p_min(key), self.__lpm_template.get_p_max(key))
        plt.legend()
        if directory is not None:
            figadd.figure_close(filename=os.path.join(directory, "comp_apriori" + key))


    def _plot_concentration_pair(
        self,
        index,
        index_next,
        self_method,
        concentrations_reference,
        lpm_2nd,
        lpm_2nd_method,
        directory,
    ):
        """
        Plot a pair of concentrations with optional overlays.
        """
        if lpm_2nd is None:
            histo = False
            histox = None
            histoy = None
        else:
            histo = True
            histox = lpm_2nd.__dist[self.__c_names[index]]
            histoy = lpm_2nd.__dist[self.__c_names[index_next]]
        scatter = True
        if self.__c_names[index] in self.__dist:
            scatterx = self.__dist[self.__c_names[index]]
            scattery = self.__dist[self.__c_names[index_next]]
            if concentrations_reference is None:
                refx = None
                refy = None
            else:
                refx = concentrations_reference.cv["concentration"][index]
                refy = concentrations_reference.cv["concentration"][index_next]
            figadd.hist_scatter(
                histo=histo,
                histox=histox,
                histoy=histoy,
                histolegend=lpm_2nd_method,
                scatter=scatter,
                scatterx=scatterx,
                scattery=scattery,
                scatterlegend=self_method,
                refx=refx,
                refy=refy,
                reflegend="reference",
                namex=self.__c_names[index],
                namey=self.__c_names[index_next],
                namefig=self.__lpm_template.name,
                directory=directory,
                file="concentrations2D_" + str(index),
            )
        

    def _write_df(self, frame: pd.DataFrame, file_path, include_index: bool = True) -> None:
        """
        Write a dataframe to a TSV file, ensuring parent directories exist.
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, sep="\t", index=include_index)


    def compute_dist(self):
        """
        Return the current distribution dataframe.
        """
        return self.__dist


    def write_dist(self, file):
        """
        Write the full distribution to disk.

        Parameters
        ----------
        file : str | Path
            Target file path for the distribution table.
        """
        self._write_df(self.compute_dist(), file, include_index=True)


    def _histogram_for_param(self, param_name, nb_bins):
        """
        Compute the histogram for a single parameter.
        """
        values = self.__dist.loc[:, param_name]
        hist, bins = np.histogram(values, bins=nb_bins, density="True")
        return hist, bins


    def _output_path(self, base_file, suffix):
        """
        Build an output path by inserting a suffix before the extension.
        """
        base_path = Path(base_file)
        return base_path.with_name(f"{base_path.stem}_{suffix}{base_path.suffix}")


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
        file_path = Path(file)
        histograms = self.compute_histograms()
        for key, payload in histograms.items():
            out_path = self._output_path(file_path, key)
            self._write_df(
                pd.DataFrame({'val': payload["bins"][:-1], 'hist': payload["hist"]}),
                out_path,
                include_index=False,
            )

        
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
        for key in lpm_target.p : 
            data[key+"_" + "target"] = [lpm_target.p[key]]
            data[key+"_" + "difference"] = [stats.loc['mean'][key] - lpm_target.p[key]]
            data[key+"_" + "rate_mean"] = [stats.loc['mean'][key]/lpm_target.p[key]]
            data[key+"_" + "rate_std"] = [stats.loc['std'][key]/lpm_target.p[key]]
        for col in stats.columns: 
            for row in stats.index :
                data[col+"_"+row] = [stats.loc[row][col]]
    
    
    def write_stats(self, file):
        """
        Write statistics of parameter and objective function distributions.

        Parameters
        ----------
        file : str | Path
            Target file path for the statistics table.
        """
        self._write_df(self.compute_stats(), file, include_index=True)
        
        
    def compute_dist_params(self):
        """
        Compute the multidimensional distribution formed by the parameters.
        """
        values = self.__dist.to_numpy()[:, 0:len(self.__lpm_template.p)]
        names = self.__lpm_template.get_param_names()
        if values.shape[1] != len(names):
            raise ValueError("Mismatch between parameter names and distribution columns.")
        return dist_hist.dist_hist(names, values)


    def computes_and_writes_dist_params(self, file):
        """
        Computes and writes the multidimensional distribution formed by the parameters 
        It is obtained as an histograme and output as a fully functional distribution 
        from which probabilities can be dervived. 
        
        Such a distribution might be used as prior for the Metropholis Hastings algorithm, for example

        Arguments
        ---------
        file : str | Path
        """
        dh = self.compute_dist_params()

        
