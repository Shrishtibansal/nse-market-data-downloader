"""One small exception hierarchy so the pipeline can catch *our* errors
separately from genuine bugs."""


class NSEError(Exception):
    """Base class for every expected failure."""


class ConfigError(NSEError):
    """Config file missing or malformed."""


class FetchError(NSEError):
    """Network / HTTP problem (after retries were exhausted)."""


class InvalidResponseError(NSEError):
    """Got a response, but its shape is not what we expect."""


class ValidationError(NSEError):
    """Data parsed fine but failed quality checks."""


class EmptyDataError(ValidationError):
    """Zero usable records."""


class StorageError(NSEError):
    """Could not write the output file."""
