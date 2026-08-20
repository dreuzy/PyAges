# PyAge architecture overview

```{mermaid}
flowchart LR
  DATA[data_core] --> TRACER[tracer]
  DATA --> LPM[lpm]

  CLI[cli] --> WF[workflows]
  CONFIG[config] --> WF
  CONC[concentrations] --> PROBLEM[CalibrationProblem]
  WF --> CONC
  WF --> PROBLEM

  TRACER --> CONV[convolution]
  LPM --> CONV
  CONV --> PROBLEM
  PROBLEM --> METHODS[calibration methods]
  METHODS --> RESULT[LpmDist]
  RESULT --> IO[data_io]
  RESULT --> PLOTS[workflow plots]

  EXAMPLES[examples and sites] -. configure .-> CLI
  TESTS[tests] -. qualify .-> CONV
  TESTS -. qualify .-> METHODS
```

Arrows represent runtime dependencies or data flow. `examples` and `sites`
consume the installable core; the core does not import them.
