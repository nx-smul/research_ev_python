"""Custom exception hierarchy for the EVCS placement optimizer."""


class ConfigError(ValueError):
    """Raised when a scenario or override configuration is invalid."""


class RealDataPreflightError(ValueError):
    """Raised when required, provenance-verified public inputs are unavailable."""


class OptimizationError(RuntimeError):
    """Raised when the optimization solver encounters an unrecoverable error."""
