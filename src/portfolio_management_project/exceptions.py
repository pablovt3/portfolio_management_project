"""Project-specific exception types."""


class DataPipelineError(RuntimeError):
    """Raised when the configured data build cannot be completed safely."""
