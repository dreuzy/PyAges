# -*- coding: utf-8 -*-
"""
Calibration core: common utilities and base behavior for LPM calibration.

Defines the shared preparation flow (LPM + tracers + errors + sampling),
the objective function used during calibration, and standardized outputs.
"""

import os

from calibration.utils.systematic_sampling import ParamSysSampling, SystematicSampling
from calibration.utils.objective_functions import L2_norm_diff
import global_parameters as gp                         
import LPM.LPM_generate as LPM_generate                                        
import convolution.convolution_tracers as convolution_tracers      
import concentrations.concentrations as co 

from pathlib import Path

def folder_prior_posterior(file, stageup=-5, folder_prior=""): 
    """Return the folder used to store posterior distributions for reuse as priors.

    Parameters
    ----------
    file : str or Path
        Reference path used to locate the root folder.
    stageup : int, optional
        Number of parent levels to traverse (default = -5).
        Example: -1 = parent, -2 = grand-parent, etc.
    folder_prior : str, optional
        Optional subfolder under ``prior_distributions``.

    Returns
    -------
    Path
        Existing or newly created folder path.
    """
    file_path = Path(file).resolve()
    
    # on remonte de |stageup| niveaux
    try:
        folder_root = file_path.parents[abs(stageup) - 1]
    except IndexError:
        raise ValueError(f"stageup={stageup} remonte trop haut pour {file_path}")
    
    # sous-dossier prior_distributions
    folder_root = folder_root / "prior_distributions"
    folder_root.mkdir(parents=True, exist_ok=True)

    # sous-dossier optionnel folder_prior
    if folder_prior:
        folder_root = folder_root / folder_prior
        folder_root.mkdir(parents=True, exist_ok=True)
    
    return folder_root


def file_prior_posterior(file_ploemeur, error_concentrations, lpm_type): 
    """Build a posterior filename stem from the case settings.

    Parameters
    ----------
    file_ploemeur : str
        Base identifier for the case.
    error_concentrations : float
        Error level used in the calibration.
    lpm_type : str
        LPM model identifier.

    Returns
    -------
    str
        Filename stem (without extension).
    """
    return file_ploemeur + "_err_" + str(error_concentrations) + "_lpm_" + lpm_type


class CalibrationCore(SystematicSampling): 
    """Shared calibration behavior for LPM models.

    This class defines the common preparation flow (LPM, tracers, errors,
    convolution setup) and provides helpers for objective evaluation and
    standardized outputs. Concrete calibration methods are implemented in
    subclasses.
    """

    def __init__(self,cdata,LPM_type,display_options=gp.display_options(),directory_lpm=gp.directory_lpm_data,
                 nmodels=1000,objfunc=True,reachconc=True):
        """Initialize a calibration core container (requires ``prepare()``).

        Parameters
        ----------
        cdata : Concentrations
            Target concentrations and sampling dates.
        LPM_type : str
            LPM model identifier (e.g. exp, ig, gamma).
        display_options : display_options
            Output settings for files and plots.
        directory_lpm : str
            Directory containing LPM data files.
        nmodels : int, optional
            Number of models used in sampling and objective evaluation.
        objfunc : bool, optional
            Whether to enable objective-function sampling.
        reachconc : bool, optional
            Whether to compute reachable concentrations.
        """
        
        self.cdata = cdata
        self.lpm_type = LPM_type
        self.directory_lpm = directory_lpm
        self.nmodels = nmodels
        self.objfunc = objfunc
        self.reachconc = reachconc
        self.display_options = display_options

        # Will be initialized in prepare()
        self.lpm = None
        self.tracers = None
        self._prepared = False

    def prepare(self):
        """Initialize LPM, tracers, errors, and sampling infrastructure."""
        # Initiation of the LPM structure (not the targeted parameters)
        self.lpm = LPM_generate.LPM_generate(self.lpm_type, self.directory_lpm)
        # Initiation of the tracer_chemicals corresponding to the data sampled
        self.tracers = convolution_tracers.ConvolutionTracers(
            names=self.cdata.cv.iloc[:, 0],
            date=self.cdata.cv["date"],
        )
        # Definition of errors (if error == 0, takes mean chronicle value)
        self.cdata.error_affect_from_mean(self.tracers.mean_value(self.cdata.cv["date"].mean()))
        # Preparation of convolution
        self.tracers.convolution_prepare(self.lpm.name)
        # Init SystematicSampling
        SystematicSampling.__init__(
            self,
            self.lpm_type,
            self.cdata.names(),
            date=self.cdata.cv["date"],
            cdata=self.cdata,
            nmodels=self.nmodels,
            objfunc=self.objfunc,
            reachconc=self.reachconc,
            display_options=self.display_options,
        )
        self._prepared = True

    def _ensure_prepared(self):
        """Raise if ``prepare()`` has not been called."""
        if not self._prepared:
            raise RuntimeError(
                "CalibrationCore.prepare() must be called before using this method."
            )
    
    
    def objective_function(self, param, data_c, data_error, conc=False):
        """Compute the objective value for a set of model parameters.

        The metric uses squared differences normalized by the measurement
        errors (Tarantola, 2005).

        Parameters
        ----------
        param : array-like
            Parameter values (order follows the LPM definition).
        data_c : array-like
            Target concentrations.
        data_error : array-like
            Target concentration errors.
        conc : bool, optional
            If True, also return modeled concentrations.

        Returns
        -------
        float or list
            Objective value, or ``[objective, concentrations]`` when ``conc``
            is True.
        """
        self._ensure_prepared()
        # Modification of parameters in lpm
        self.lpm.set_param_from_array(param)
        # Concentration computed (this function without dataframe for performance issues)
        model_c = self.tracers.convolution(self.lpm,prepare=True,opt=True)
        # Squared difference
        #JRBUG
        if any(data_error==0):         
            print("error concentration errors not defined")
            print(data_error)
            print(self.lpm.name)
        #JRBUG
        diff = sum(L2_norm_diff(data_c, model_c, data_error))
        # diff = sum(np.square((model_c-data_c)/data_error))
        if conc: 
            return [diff,model_c]
        else: 
            return diff
    

    def display_concentrations(self):
        """Display observed and modeled concentrations for the current LPM."""
        self._ensure_prepared()
        self.lpm.display()
        self.cdata.display()
        concentration_computed = self.tracers.convolution(self.lpm,return_type="concentrations_set",prepare=False)
        concentration_computed.display()
        print("J=",self.cdata.sqrt_quadratic_mean_diff(concentration_computed))
  
        
    def display_lpms(self,display_options,lpm_results,lpm_reference=None):
        """Display calibrated LPM results and optional reference comparisons.

        Parameters
        ----------
        display_options : display_options
            Output configuration for figures and text.
        lpm_results : LPMDist
            Calibration results container.
        lpm_reference : LPM, optional
            Reference LPM for comparison.
        """
        self._ensure_prepared()
        #JR: Should it be different
        if self.method == "Simplex" or self.method == "Simplex_init_multipes": 
            # Comparison of parameters
            if display_options.text and lpm_reference != None : 
                [exist,lpm]=lpm_results.get_best_lpm()
                if exist: lpm.display_parameters(lpm_reference)
        if self.method == "forward_uncertainty_quantification" or self.method == "Metropolis_Hastings" :
            # Distribution of parameters
            if display_options.figure : 
                lpm_results.display_parameters_dist(self_method=self.method,lpm_reference=lpm_reference,bins=100,directory=self.display_options.directory)


    def write_calibrated_lpm(self,lpm_results,file_prior="none",folder_prior=""): 
        """Write calibrated LPM outputs and optional prior distributions.

        Parameters
        ----------
        lpm_results : LPMDist
            Calibration results to serialize.
        file_prior : str, optional
            File stem for prior/posterior storage.
        folder_prior : str, optional
            Subfolder for prior storage.
        """ 
        self._ensure_prepared()
        # Writes calibration parameters and efficiencty results
        base_dir = Path(self.display_options.directory)
        self.write_parameters(base_dir / "parameters_calibration.txt")
        self.write_results(base_dir / "results_calibration.txt")
        # Writes distribution of "best" lpm
        if self.method != "Simplex" : 
            lpm_results.write_dist(base_dir / "lpm_dist_calibrated.txt")
            lpm_results.write_histograms(base_dir / "lpm_histo_calibrated.txt")
            lpm_results.write_stats(base_dir / "lpm_stats_calibrated.txt")
            lpm_results.computes_and_writes_dist_params(
                base_dir / "lpm_param_dist_calibrated.txt"
            )
        if self.method == "Metropolis_Hastings" : 
            prior_dir = folder_prior_posterior(
                self.display_options.directory, stageup=-5, folder_prior=folder_prior
            )
            lpm_results.write_histograms(prior_dir / f"{file_prior}.txt")
        # Writes "best" lpm
        # [exist,lpm]=lpm_results.get_best_lpm()
        # if exist: lpm.write(os.path.join(self.display_options.directory,"lpm_calibrated.txt"),open_file=True)


    def write_results(self,file_name):
        """Write scalar calibration results to a text file.

        Parameters
        ----------
        file_name : str or Path
            Output file path.
        """
        data={}
        # Generic results for all calibration methods
        data['time_perform'] = self.time_perform
        # Specific results to this calibration method
        self.write_results_spec(data)
        # Writing in file
        file_path = Path(file_name)
        with file_path.open("w") as handle:
            for key, val in data.items():
                handle.write(f"{key}\t{val}\n")
        
