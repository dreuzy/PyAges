"""Four-panel comparison read from the matched-quantile CSV outputs."""
from __future__ import annotations
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image
from pyage.lpm.models.exponential_shifted import ExponentialShiftedLpm
from plot_lpm_distribution_families_matched_quantiles import inverse_gaussian_model

ROOT=Path(__file__).resolve().parents[6]
OUT=ROOT/"results"/"HYP-26-0172"/"figures"/"supporting_information"
LPM_DIR=ROOT/"sites"/"ploemeur"/"params_lpm"
PARAMETERS=OUT/"LPM_distribution_families_matched_quantiles_parameters.csv"
CHECKS=OUT/"LPM_distribution_families_quantile_checks.csv"
SETS=(1,2,4,6); EXP="shifted exponential"; IG="shifted inverse Gaussian"
RED="#d62728"; GREEN="#2ca02c"
FIELDS=["parameter_set","model","shift","mu","lambda","Q1","median","Q3","IQR","mean","variance"]
plt.rcParams.update({"font.family":"sans-serif","font.size":8.4,"axes.labelsize":9.1,
 "axes.titlesize":9.0,"axes.linewidth":1.0,"xtick.labelsize":7.7,
 "ytick.labelsize":7.7,"legend.fontsize":6.5})

def read_parameters():
    if not PARAMETERS.exists() or not CHECKS.exists():
        raise FileNotFoundError("Generate the matched-quantile outputs first")
    rows=[]
    with PARAMETERS.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pair=int(r["pair"])
            if pair in SETS:
                rows.append({"parameter_set":pair,"model":r["model"],"shift":float(r["shift"]),
                 "mu":float(r["mu"]),"lambda":r["lambda"] if r["lambda"]=="not applicable" else float(r["lambda"]),
                 "Q1":float(r["q1"]),"median":float(r["median"]),"Q3":float(r["q3"]),
                 "IQR":float(r["iqr"]),"mean":float(r["mean"]),"variance":float(r["variance"])})
    if len(rows)!=8: raise ValueError(f"Expected 8 rows, found {len(rows)}")
    return rows

def verify(rows):
    grouped={s:{r["model"]:r for r in rows if r["parameter_set"]==s} for s in SETS}
    with CHECKS.open(newline="",encoding="utf-8") as f:
        checks={(int(r["pair"]),r["model"]):r for r in csv.DictReader(f) if int(r["pair"]) in SETS}
    for s,m in grouped.items():
        a,b=m[EXP],m[IG]
        if a["shift"]!=b["shift"] or abs(a["median"]-b["median"])>=.01 or abs(a["IQR"]-b["IQR"])>=.01:
            raise ValueError(f"Unmatched statistics for set {s}")
        for name in (EXP,IG):
            if abs(float(checks[(s,name)]["integral"])-1)>=1e-3: raise ValueError(f"Integral failed for set {s}")

def build_model(r):
    if r["mu"]<=0 or r["shift"]<0: raise ValueError("Invalid parameter")
    if r["model"]==EXP:
        return ExponentialShiftedLpm(mu=r["mu"],shift=r["shift"],directory_lpm=LPM_DIR)
    if not isinstance(r["lambda"],float) or r["lambda"]<=0: raise ValueError("Invalid lambda")
    return inverse_gaussian_model(r["shift"],r["mu"],r["lambda"])

def write_tables(rows):
    paths=(OUT/"LPM_pairwise_comparison_parameters.csv",OUT/"LPM_pairwise_comparison_parameters_SI.csv")
    rounded=[{k:round(v,2) if isinstance(v,float) else v for k,v in r.items()} for r in rows]
    for path,data in zip(paths,(rows,rounded)):
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(data)
    return paths

def make_figure(rows):
    grouped={s:{r["model"]:r for r in rows if r["parameter_set"]==s} for s in SETS}
    t=np.linspace(0,160,5000); data={}; ymax=0.0
    for s in SETS:
        data[s]={}
        for name in (EXP,IG):
            y=np.asarray(build_model(grouped[s][name]).pdf(t),float)
            if np.any(~np.isfinite(y)) or np.any(y<0): raise ValueError(f"Invalid density set {s}")
            data[s][name]=y; ymax=max(ymax,float(y.max()))
    fig,axs=plt.subplots(2,2,figsize=(7.1,5.25),sharex=True,sharey=True)
    for ax,s,letter in zip(axs.flat,SETS,"abcd"):
        a,b=grouped[s][EXP],grouped[s][IG]
        for name,color,ls in ((EXP,RED,"-"),(IG,GREEN,"--")):
            r=grouped[s][name]; y=data[s][name]
            ax.plot(t,y,color=color,ls=ls,lw=1.7)
            ax.fill_between(t,0,y,where=(t>=r["Q1"])&(t<=r["Q3"]),color=color,alpha=.12)
        median=(a["median"]+b["median"])/2; iqr=(a["IQR"]+b["IQR"])/2
        ax.axvline(median,color=".45",ls=":",lw=1.1)
        ax.set_title(f"({letter}) Parameter set {s}\nShift = {a['shift']:g} y; median = {median:.1f} y; IQR = {iqr:.1f} y")
        ax.set_xlim(0,160); ax.set_ylim(0,ymax*1.05); ax.tick_params(direction="out",width=1)
    fig.supxlabel("Transit time (years)",y=.105,fontsize=9.1)
    fig.supylabel("Probability density (year⁻¹)",x=.025,fontsize=9.1)
    handles=[Line2D([],[],color=RED,lw=1.7,label="Shifted exponential"),
     Line2D([],[],color=GREEN,ls="--",lw=1.7,label="Shifted inverse Gaussian"),
     Line2D([],[],color=".45",ls=":",lw=1.1,label="Median")]
    fig.legend(handles=handles,loc="lower center",ncol=3,frameon=False,bbox_to_anchor=(.5,.025))
    fig.subplots_adjust(left=.11,right=.98,top=.94,bottom=.18,hspace=.34,wspace=.12)
    paths=(OUT/"LPM_pairwise_comparison_4panels.pdf",OUT/"LPM_pairwise_comparison_4panels.png",
           OUT/"LPM_pairwise_comparison_4panels.tif")
    fig.savefig(paths[1],dpi=300,bbox_inches="tight")
    fig.savefig(paths[0],bbox_inches="tight")
    # TIFF is a single flattened raster, exported at the journal's graph resolution.
    fig.savefig(paths[2],dpi=600,bbox_inches="tight",pil_kwargs={"compression":"tiff_lzw"})
    plt.close(fig)
    with Image.open(paths[2]) as image:
        flattened = Image.new("RGB", image.size, "white")
        if image.mode == "RGBA":
            flattened.paste(image, mask=image.getchannel("A"))
        else:
            flattened.paste(image.convert("RGB"))
        flattened.save(paths[2], format="TIFF", compression="tiff_lzw", dpi=(600, 600))
    return paths

def main():
    OUT.mkdir(parents=True,exist_ok=True); rows=read_parameters(); verify(rows)
    for p in (*make_figure(rows),*write_tables(rows)): print(p)
if __name__=="__main__": main()
