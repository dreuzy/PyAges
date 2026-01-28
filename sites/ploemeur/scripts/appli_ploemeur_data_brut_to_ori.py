import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
for p in (repo_root, repo_root / "pyage"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# -*- coding: utf-8 -*-
"""
Convert raw Ploemeur tracer tables into normalized "ori_ploemeur" files.

Reads {well}_brut.txt files from the Ploemeur data/brut folder, extracts tracer
values and sampling dates, and writes tab-separated outputs compatible with
downstream calibration workflows.

Outputs (one per well) in data/ori:
    ori_ploemeur_{well}_{min_year}_{max_year}.txt
Columns:
    element, concentration, error, unit, date

Copyright (c) 2021 Jean-Raynald de Dreuzy
Author: Jean-Raynald de Dreuzy
"""

import os
import pandas as pd

from sites.ploemeur.observations import ploemeur as ploemeur_obs

# Wells to process (raw files are expected as {well}_brut.txt in data/brut).
wells = ["F34", "MF4", "F38b", "F13", "F11", "F38", "F22", "PE", "MF1", "F28", "F09", "PZ2", "PSR1"]
# wells=["F11"]

# Convert each raw file to the standardized format.
for well in wells:
    brut_directory = ploemeur_obs.ploemeur_brut_folder()
    ori_directory = ploemeur_obs.ploemeur_ori_folder()
    file_name=well+"_brut.txt"
    print(file_name)
    df = pd.read_table(os.path.join(brut_directory, file_name), header=None)
    # Gets Tracer Name
    tracer=[]
    for col in df.columns: 
        if col >=1 : 
            tracer_name=df[col][0]
            tracer.append('cfc'+tracer_name[4:])
    # Prepare output dataframe in the standardized schema.
    conc = pd.DataFrame(columns = ['element','concentration','error','unit','date'])
    
    k=0
    tracer_dates=[]
    for row in df.iterrows():
        tracer_val=[]
        tracer_temp=[]
        # Data rows start after the two-header lines.
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
                # Append one row per tracer measurement.
                # print(tracer_temp[j],'\t',tracer_val[j],'\t',0,'\t','pptv','\t',datef)
                error = 0.0
                # if tracer_temp[j] == "cfc12": 
                #     error = 0.6 * tracer_val[j]
                # else: 
                #     error = 0.03 * tracer_val[j]
                conc=pd.concat([conc if not conc.empty else None,pd.DataFrame({'element': tracer_temp[j],'concentration':tracer_val[j],\
                                                   'error':error,'unit':0,'date':datef},index=[0])], ignore_index=True)
        k=k+1
    
    # Persist the normalized file with the observed time span in the name.
    conc.to_csv(
        os.path.join(
            ori_directory,
            "ori_ploemeur_"
            + well
            + "_"
            + str(int(min(tracer_dates)))
            + "_"
            + str(int(max(tracer_dates)))
            + ".txt",
        ),
        sep="\t",
        index=False,
    )
            
