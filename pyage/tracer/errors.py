"""Domain errors raised while loading tracer definitions."""


class TracerConfigError(Exception):
    """A tracer YAML file is readable but contains an invalid definition."""


class TracerDataError(Exception):
    """A tracer configuration or chronicle file cannot be read."""
