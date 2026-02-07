# UML classes for sites/ploemeur

```mermaid
classDiagram
class CalibrationConfig
class ExecutionConfig
class ObservationsConfig
class PloemeurDriverConfig
class PloemeurSite
class ResultsConfig
class SimulationStrategy
class WorkflowConfig
class _BaseCfg
class ploemeur_one_date
class sim_results
class sim_tree
_BaseCfg <|-- PloemeurDriverConfig
BaseSite <|-- PloemeurSite
BaseModel <|-- _BaseCfg
```
