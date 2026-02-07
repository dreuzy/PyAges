# UML classes for pyage/tracer

```mermaid
classDiagram
class ConstantTracer
class DecayTracer
class DisplayOptions
class SyntheticTracer
class Tracer
class TracerConfigError
class TracerDataError
class TracerProtocol
Exception <|-- TracerConfigError
Exception <|-- TracerDataError
Protocol <|-- TracerProtocol
```
