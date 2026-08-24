"""R02 input-boundary errors."""


class RegimeInputError(ValueError):
    """Raised when evidence lineage or chronology is structurally invalid."""


__all__ = ["RegimeInputError"]
