# PyAge architecture overview

```mermaid
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

  subgraph Scripts["scripts (entry points)"]
    LAUNCH[scripts/launcher.py]
    LAUNCHT[scripts/launcher_temporal.py]
    CHECK[scripts/run_system_check.py]
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
  Scripts --> Core
  Tests --> Core
```
