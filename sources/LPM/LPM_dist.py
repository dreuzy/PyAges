# -*- coding: utf-8 -*-
"""
Created on Sun May 23 21:53:11 2021

@author: dreuzy
"""

import copy
import matplotlib.pyplot as plt         # Plots
import numpy as np                      # Arrays
import os
import pandas as pd                     # Tables-Arrays

import global_parameters as gp
import tools.figures_additional as figadd
import tools.dist_hist as dist_hist

from IPython.display import display




class LPMDist:
    """  
    Distribution of parameter values

    General Organization, a row for each simulation of number "i"
        parameters 
        value of objective function
        concentration obtained with those sets of parameters

    Attributes, public
    ----------

    Attributes, private
    ----------
    __lpm_template : LPM (instance of class)
        template distribution
    __c_names : vector of str
        element names corresponding to concentrations
    __dist : dataframe
        distribution of results
        
    Methods 
    -------
    dist_append(self,params,optim_fun,concentrations)
        Appends solution to the results list
    """

    def __init__(self,lpm,c_names):
        """ 
        Constructor for the distribution of parameters
        """
        self.__lpm_template = lpm
        self.__c_names = c_names
        self.__dist = pd.DataFrame(columns = self.__lpm_template.get_param_names() + ['obj_function'] + c_names)
            
            
    def dist_append(self,params,obj_function=-1,param_in_bounds=None,concentrations=None):
        """ 
        Appends full simulation to results
        
        Arguments
        ---------
        params: dictionary
            params[t_name]=t_value
        obj_function: float
            value of objective function
        concentrations: vector
            Concentrations in a vector format
        param_in_bounds: bool 
            Are parameters within bounds
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


    def dist_append_array(self,params,obj_function=-1,param_in_bounds=None,concentrations=None):
        """ 
        Appends full simulation to results
        
        Arguments
        ---------
        params: vector
            params[k]=value
        optim_fun: float
            value of objective function
        concentrations: vector
            Concentrations in a vector format
        """
        params_dic={}; k=0
        for t in self.__lpm_template.p:
            params_dic[t]=params[k]; k=k+1
        self.dist_append(params_dic,obj_function=obj_function,param_in_bounds=param_in_bounds,concentrations=concentrations)
        

    def append(self,other): 
        """ 
        Concatenation of self with other
        
        Arguments
        ---------
        other: LPMDist
            the other instance of the class to concatenate
        """
        #concat self.__dist=self.__dist.append(other.__dist,ignore_index=True)
        if self.__dist.empty: 
            self.__dist = other.__dist
        else:
            self.__dist=pd.concat([self.__dist,other.__dist],ignore_index=True)

        
        
    
    def get_selection(self,lpm_number,span_or_suc,array_resolution=1000):
        """
        Gets selection of lpm from results

        Parameters
        ----------
        lpm_number : int
            Number of lpm to select (redundancies possible)
            The default is 10.
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
        # Storage strucutre of the pdfs
        pdf_array=np.empty((lpm_number+1,array_resolution))
        pdf_array[0,:]=gp.arange_n(0,70,array_resolution-1) # Between 0 and 70 years (#JR1: 70 years->generalize)
        pdf_colname=[]; pdf_colname.append('t')
        # Storage strucutre of the pdf statistics
        lpm_statistics = pd.DataFrame(index=range(lpm_number),columns=self.__lpm_template.moments_name())
        # List of lpms (as lpms)
        lpm_list=[]
        # Loop on the lpm_number models 
        for i in range(1,lpm_number+1):
            # Selects line and updates lpm parameters accordingly 
            if "span" in span_or_suc:
                option = "random_each"
            else : 
                option = "random_line"
            [test,line]=self.__lpm_template.load_lpm_from_dist(self.__dist,option=option,rng=rng)
            if test == True : 
                lpm_list.append(copy.deepcopy(self.__lpm_template))
                # Computes and stores pdfs
                pdf_val=self.__lpm_template.pdf(pdf_array[0,:])
                pdf_array[i,:]=pdf_val
                pdf_colname.append('p'+str(line))
                # Computes and sores moments
                lpm_statistics.iloc[i-1] = self.__lpm_template.moments()
            else: 
                pdf_colname.append('p')
        pdf=pd.DataFrame(pdf_array.T, columns=pdf_colname)
        return lpm_list, pdf, lpm_statistics

        
    def fill_np_array(self,array_results,column_names):
        """
        fills self.dist with array_results        

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
        Returns lpm giving the smallest objective function 
        """
        lpm = copy.deepcopy(self.__lpm_template)
        if self.__dist.shape[0] == 0: 
            return False, None
        imin = self.__dist.idxmin(axis=0, skipna=True)
        for key in lpm.p: 
            lpm.p[key]=self.__dist.loc[imin][key]
        return True, lpm
     

    def display_points_alone(self): 
        x=[]
        for key in self.__lpm_template.p:
            x.append(self.__dist[key])
        if len(x)==2: 
            plt.scatter(x[1][1:600],x[0][1:600],c='black',s=3,marker='.')
         
            
    def display_param_vs_param(self,keyx,keyy): 
        """
        Displays param[keyy] versus param[keyy]

        Parameters
        ----------
        keyx : str
            Name of parameter for the absciss
        key2 : str
            Name of parameter for the ordinate

        """
        plt.scatter(self.__dist[keyx], self.__dist[keyy], marker='+', c = 'red', s=10, label="model")
        

    def display_parameters_dist(self,self_method="",lpm_reference=None,bins=30,lpm_2nd=None,lpm_2nd_method="",directory=None,display_text=False) :
        """ 
        Display distribution of parameters of the lpm
        """
        # Shows histogram of the parameters
        if display_text : print("\033[1m"+"DISTRIBTUTION OF PARAMETERS"+"\033[0m")
        for key in self.__lpm_template.p:
            figadd.figure_init(xlab=key,ylab="Count",figname=self.__lpm_template.name)
            binwidth = self.__lpm_template.get_param_range(key)/100
            # First histogram
            plt.hist(self.__dist[key].tolist(), density=True, bins=np.arange(min(max(self.__dist[key].tolist())/2,self.__lpm_template.get_p_min(key)), self.__lpm_template.get_p_max(key) + binwidth, binwidth), histtype='barstacked',label=self_method)
            # Second histogram
            if lpm_reference != None : plt.axvline( lpm_reference.p[key], c='k', linewidth=2.0, label="reference")
            # Vertical line at the place of the reference model
            if lpm_2nd != None : plt.hist(lpm_2nd.__dist[key], density=True, bins=np.arange(min(max(self.__dist[key].tolist())/2,self.__lpm_template.get_p_min(key)), self.__lpm_template.get_p_max(key) + binwidth, binwidth), histtype='barstacked',label=lpm_2nd_method)            
            plt.xlim(self.__lpm_template.get_p_min(key),self.__lpm_template.get_p_max(key))
            plt.legend()
            if directory != None : figadd.figure_close(filename=os.path.join(directory,'comp_'+key))
        
        # 2D plots parameter/obj-function
        if display_text : print("\033[1m"+"OBJECTIVE FUNCTION"+"\033[0m")
        for key in self.__lpm_template.p:
            figadd.figure_init(xlab=key,ylab='obj_function',figname=self.__lpm_template.name)
            plt.scatter(self.__dist[key].tolist(), self.__dist['obj_function'].tolist(), marker='x', c = 'blue', s=10, label=self_method)
            # Vertical line at the place of the reference model
            if lpm_reference != None : plt.axvline( lpm_reference.p[key], c='k', linewidth=2.0, label="reference")
            # Second scatter plot
            if lpm_2nd != None : plt.scatter(lpm_2nd.__dist[key], lpm_2nd.__dist['obj_function'], marker='+', c = 'red', s=10, label=lpm_2nd_method)
            plt.legend()
            if directory != None : figadd.figure_close(filename=os.path.join(directory,'objfunction_'+key))
            
        # 2D plots between parameters
        if display_text : print("\033[1m"+"PARAMETERS"+"\033[0m")
        if len(self.__lpm_template.p) >= 2 :
            # Name of parameters
            names=[]
            for key in self.__lpm_template.p:
                names.append(key)
            for i in range(len(self.__lpm_template.p)):
                i1 = (i + 1) % len(self.__lpm_template.p)
                # Histogram
                if lpm_2nd == None : histo=False; histox=None; histoy=None
                else : histo=True; histox=lpm_2nd.__dist[names[i]]; histoy=lpm_2nd.__dist[names[i1]]
                # Scatter
                scatter=True;scatterx=self.__dist[names[i]].tolist(); scattery=self.__dist[names[i1]].tolist()
                if len(scatterx)==0: scatterx=None; scattery=None; 
                # Reference
                if lpm_reference == None : refx=None; refy=None
                else: refx=lpm_reference.p[names[i]];refy=lpm_reference.p[names[i1]]
                # Main function 
                figadd.hist_scatter(histo=histo,histox=histox,histoy=histoy,histolegend=lpm_2nd_method,
                                    scatter=scatter,scatterx=scatterx,scattery=scattery,scatterlegend=self_method,
                                    refx=refx,refy=refy,reflegend="reference",namex=names[i],namey=names[i1],
                                    namefig=self.__lpm_template.name,directory=directory,
                                    file='comp2D_'+names[i]+'_'+names[i1])


    def display_parameters_dist_comp_apriori(self,lpm_reference=None,bins=30,lpm_2nd=None,lpm_2nd_method="",directory=None,display_text=False,prior="") :
        """ 
        Display distribution of parameters of the lpm
        """
        # Shows histogram of the parameters
        if display_text : print("\033[1m"+"DISTRIBTUTION OF PARAMETERS"+"\033[0m")
        for key in self.__lpm_template.p:
            figadd.figure_init(xlab=key,ylab="Count",figname=self.__lpm_template.name)
            binwidth = self.__lpm_template.get_param_range(key)/100
            # First histogram
            temp=plt.hist(self.__dist[key].tolist(), density=True, bins=np.arange(min(max(self.__dist[key].tolist())/2,self.__lpm_template.get_p_min(key)), self.__lpm_template.get_p_max(key) + binwidth, binwidth), histtype='barstacked',label="MH")
            # Second histogram for a priori
            rescaling=(prior.MHapriori_para[key][2,0]-prior.MHapriori_para[key][2-1,0])/(temp[1][2]-temp[1][2-1])
            rescaling = 1 / rescaling
            rescaling = np.mean(temp[0]!=0)/np.mean(prior.MHapriori_para[key][:,1]!=0)
            rescaling = np.mean(temp[0][temp[0][:]!=0]) / np.mean(prior.MHapriori_para[key][prior.MHapriori_para[key][:,1]!=0,1])
            plt.plot(prior.MHapriori_para[key][:,0],prior.MHapriori_para[key][:,1]*rescaling)
            if lpm_reference != None : plt.axvline( lpm_reference.p[key], c='k', linewidth=2.0, label="reference")
            # Vertical line at the place of the reference model
            if lpm_2nd != None : plt.hist(lpm_2nd.__dist[key], density=True, bins=np.arange(min(max(self.__dist[key].tolist())/2,self.__lpm_template.get_p_min(key)), self.__lpm_template.get_p_max(key) + binwidth, binwidth), histtype='barstacked',label=lpm_2nd_method)            
            plt.xlim(self.__lpm_template.get_p_min(key),self.__lpm_template.get_p_max(key))
            plt.legend()
            if directory != None : figadd.figure_close(filename=os.path.join(directory,'comp_apriori'+key))        


    def display_concentrations_dist(self,self_method="",concentrations_reference=None,lpm_2nd=None,lpm_2nd_method="",directory=None) :
        """ 
        Displays concentrations
            2D plots between concentrations
            Loop other the concentrations stored successively in vector
        
        Arguments
        ---------
        self_method: str
            calibration method used
        concentrations_reference: class Concentrations
            Reference concentrations (e.g. tartget values)
        lpm_2nd: LPMdist
            Comparison with antoher distribution of parameter values
        lpm_2nd_method: str
            Calibration method whith which 2nd distribution has been obtained
        directory: str
            Directory in which figure should be stored
        """        
        # Loop other successive concentrations
        for i in range(len(self.__c_names)):
            i1 = (i + 1) % len(self.__c_names)
            # Histogram
            if lpm_2nd == None : 
                histo=False
                histox=None
                histoy=None
            else:  
                histo=True
                histox=lpm_2nd.__dist[self.__c_names[i]]
                histoy=lpm_2nd.__dist[self.__c_names[i1]]
            # Scatter
            scatter=True
            uu=self.__dist
            vv=self.__c_names[i]
            if self.__c_names[i] in self.__dist : 
                scatterx=self.__dist[self.__c_names[i]]
                scattery=self.__dist[self.__c_names[i1]]
                # Reference
                if concentrations_reference == None : 
                    refx=None
                    refy=None
                else: 
                    refx=concentrations_reference.cv['concentration'][i]
                    refy=concentrations_reference.cv['concentration'][i1]
                # Main function 
                figadd.hist_scatter(histo=histo,histox=histox,histoy=histoy,histolegend=lpm_2nd_method,
                                scatter=scatter,scatterx=scatterx,scattery=scattery,scatterlegend=self_method,
                                refx=refx,refy=refy,reflegend="reference",
                                namex=self.__c_names[i],namey=self.__c_names[i1],namefig=self.__lpm_template.name,
                                directory=directory,file='concentrations2D_'+str(i))


    def stats_distribution(self): 
        """
        Adds to each of the stored distribution several characteristics
            Mean, Standard Deviation, Quantiles
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
        

    def write_dist(self,file):
        """ 
        Outputs distribution in a file
                    
        Arguments
        ---------
        file: str
            file name in which distribution is stored
        """     
        self.__dist.to_csv(file,sep='\t')


    def write_histograms(self,file): 
        """
        Writes for each of the parameters the histogram
        """
        nb_bins = 100
        for key in self.__lpm_template.p : 
            uu = self.__dist.loc[:,key]
            hist, bins = np.histogram(self.__dist.loc[:,key], bins=nb_bins, density='True')
            # hist_dataframe = pd.DataFrame(columns = self.__lpm_template.get_param_names() + ['obj_function'] + c_names)
            pd.DataFrame({'val': bins[:-1],'hist': hist}).to_csv(file[:-4]+'_'+key+file[-4:],sep='\t',index=False)

        
        
    def get_stats(self):
        """ 
        Gets statsitics of parameter and obj_function distributions
                    
        Arguments
        ---------
        """  
        return self.__dist.describe()
        
    
    def get_stats_line(self,lpm_target,data): 
        """ 
        Gets statsitics of parameter and comparison with target
                    
        Arguments
        ---------
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
    
    
    def write_stats(self,file):
        """ 
        Writes statsitics of parameter and obj_function distributions
                    
        Arguments
        ---------
        file: str
            file name in which distribution is stored
        """  
        self.get_stats().to_csv(file,sep='\t')
        
        
    def computes_and_writes_dist_params(self,file): 
        """
        Computes and writes the multidimensional distribution formed by the parameters 
        It is obtained as an histograme and output as a fully functional distribution 
        from which probabilities can be dervived. 
        
        Such a distribution might be used as prior for the Metropholis Hastings algorithm, for example

        Arguments
        ---------
        file: str
        """
        values = self.__dist.to_numpy()[:,0:len(self.__lpm_template.p)]
        lpm = self.__lpm_template
        names = self.__lpm_template.param_names()
        if values.shape[1] != len(names) : 
            print("Pb in computes_and_writes_dist_params")
        dh = dist_hist.dist_hist(names,values)

        