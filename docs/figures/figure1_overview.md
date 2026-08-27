# Figure 1 — PyAges scientific workflow (overview)

The Mermaid diagram below is the editable source used by the HTML
documentation. A standalone [SVG export](figure1_overview.svg) is retained for
article and review workflows that cannot render Mermaid directly.

```{mermaid}
flowchart TB
  %% Increase font size for publication
  %% Mermaid theme variables are supported by mermaid-cli
  %% At the 110 mm manuscript width, 18 px remains above 9 pt.
  %% Use straight connectors so every arrow has an unambiguous source and target
  %%{init: {"theme": "base", "flowchart": {"curve": "linear", "nodeSpacing": 55, "rankSpacing": 65}, "themeVariables": {"fontFamily": "Arial, Helvetica, sans-serif", "fontSize": "18px", "lineColor": "#4b6a8b"}}}%%
  %% Node styles
  classDef main fill:#e9f0f8,stroke:#4b6a8b,stroke-width:1.2,color:#1c2b3a;
  classDef side fill:#f4f6f8,stroke:#8a97a5,stroke-width:1,color:#1c2b3a;
  classDef output fill:#eef6f2,stroke:#5b8b6f,stroke-width:1.2,color:#1c2b3a;

  %% Core classes
  LPM["LPMs<br/>Dirac, Exponential"]:::main
  TRACER["Tracers<br/>CFCs, SF6, 3H"]:::main
  CONV["Convolution"]:::main
  MODEL["Modeled tracer values"]:::main
  CAL["Calibration (Metropolis-Hastings)"]:::main

  %% External data / outputs
  OBS["Tracer observations"]:::side
  OUT1["Posterior parameter distributions"]:::output
  %% (removed) Model diagnostics box

  %% Flow
  LPM --> CONV
  TRACER --> CONV
  CONV --> MODEL
  MODEL --> CAL
  OBS --> CAL
  CAL --> OUT1

  %% Keep all connectors visible and consistent in print and HTML exports
  linkStyle default stroke:#4b6a8b,stroke-width:1.8px,fill:none;
```
