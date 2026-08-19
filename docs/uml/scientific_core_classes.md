# PyAge scientific execution flow

```mermaid
flowchart LR
  YAML[YAML configuration] --> CFG[Pydantic validation]
  CFG --> TR[Tracer chronology]
  CFG --> LPM[LPM parameters]
  TR --> CONV[Convolution]
  LPM --> CONV
  CONV --> OBJ[Objective function]
  OBS[Observed concentrations] --> OBJ
  OBJ --> CAL[Calibration]
  CAL --> SAMPLES[Posterior samples]
  SAMPLES --> STATS[Statistics]
  SAMPLES --> FIGS[Figures]
  SAMPLES --> FILES[Result files]
```

The same core flow is used by single-date and temporal workflows. Site code
prepares configuration and observations but does not replace the scientific
components shown here.
