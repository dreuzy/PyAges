# Scientific execution flow

```{mermaid}
flowchart LR
  YAML[YAML] --> CFG[Validated config]
  OBSFILE[Observation table] --> OBS[Concentrations]
  CFG --> CTX[WorkflowContext]
  OBS --> PROBLEM[CalibrationProblem]
  CTX --> PROBLEM
  TR[Tracer] --> CONV[Convolution]
  LPM[LPM] --> CONV
  CONV --> PROBLEM
  PROBLEM --> METHOD[CalibrationMethod]
  METHOD --> SAMPLES[LpmDist.frame]
  SAMPLES --> STATS[Analysis]
  SAMPLES --> FILES[TSV + manifest]
  SAMPLES --> FIGS[Optional figures]
```

The same core flow is used by single-date and temporal workflows. Site code
prepares configuration and observations but does not replace the scientific
components shown here.
