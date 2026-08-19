# PyAge architecture overview

```{mermaid}
flowchart TB
  subgraph Core["pyage (core library)"]
    LPM[pyage/lpm]
    TRACER[pyage/tracer]
    CONV[pyage/convolution]
    CAL[pyage/calibration]
    CONC[pyage/concentrations]
    CFG[pyage/config]
    IO[pyage/data_io]
    TOOLS[pyage/tools]
    WORKFLOWS[pyage/workflows]
    CLI[pyage/cli]
  end

  subgraph Data["data_core (shared model data)"]
    LPMDATA[data_core/data_lpm]
    TRDATA[data_core/data_tracer]
  end

  subgraph Sites["sites (site-specific workflows)"]
    PLOEMEUR[sites/ploemeur]
  end

  subgraph Examples["examples (runnable examples)"]
    EXPL[examples/natural/ploemeur]
    EXFT[examples/natural/fontainebleau]
    EXTMP[examples/templates]
  end

  subgraph Tests["tests (regression + golden)"]
    TESTS[tests/*]
  end

  LPMDATA --> LPM
  TRDATA --> TRACER
  TRACER --> CONV
  LPM --> CONV
  CONV --> CAL
  CONC --> CAL
  CFG --> CAL
  IO --> LPM
  IO --> TRACER

  Sites --> Core
  Examples --> Core
  CLI --> WORKFLOWS
  WORKFLOWS --> CAL
  WORKFLOWS --> CONC
  Tests --> Core
```
