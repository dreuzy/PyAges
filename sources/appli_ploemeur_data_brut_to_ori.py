# -*- coding: utf-8 -*-
"""
Created on Tue Jun  8 14:55:45 2021

@author: Jean-Raynald de Dreuzy
"""

import os
import pandas as pd

import global_parameters as gp
import ploemeur.appli_ploemeur_tools as appli_ploemeur_tools 

wells=["F34","MF4","F38b","F13","F11","F38","F22","PE","MF1","F28","F09","PZ2","PSR1"]
# wells=["F11"]

for well in wells: 
    directory = appli_ploemeur_tools.ploemeur_data_folder()
    file_name=well+"_brut.txt"
    print(file_name)
    df = pd.read_table(os.path.join(directory,file_name),header=None)
    # Gets Tracer Name
    tracer=[]
    for col in df.columns: 
        if col >=1 : 
            tracer_name=df[col][0]
            tracer.append('cfc'+tracer_name[4:])
    # Creates pandas dataframe
    conc = pd.DataFrame(columns = ['element','concentration','error','unit','date'])
    
    k=0
    tracer_dates=[]
    for row in df.iterrows():
        tracer_val=[]
        tracer_temp=[]
        if k>=2: 
            date=df[0][k]
            temp=date.split('/')
            datef=float(temp[2])+(30*(float(temp[1])-1)+float(temp[0]))/365
            tracer_dates.append(datef)
            for i in range(0,3):
                # Select row
                if(float(df[i+1][k])>0):
                    tracer_val.append(float(df[i+1][k]))
                    tracer_temp.append(tracer[i])
            for j in range(len(tracer_val)): 
                # Appends row
                # print(tracer_temp[j],'\t',tracer_val[j],'\t',0,'\t','pptv','\t',datef)
                error = 0.0
                # if tracer_temp[j] == "cfc12": 
                #     error = 0.6 * tracer_val[j]
                # else: 
                #     error = 0.03 * tracer_val[j]
                conc=pd.concat([conc if not conc.empty else None,pd.DataFrame({'element': tracer_temp[j],'concentration':tracer_val[j],\
                                                   'error':error,'unit':0,'date':datef},index=[0])], ignore_index=True)
        k=k+1
    
    conc.to_csv(os.path.join(directory,"ori_ploemeur_"+well+"_"+str(int(min(tracer_dates)))+"_"+str(int(max(tracer_dates)))+".txt"),sep='\t', index = False)
            