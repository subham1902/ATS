"""R05 structural input failures."""


class EnsembleInputError(ValueError):
    """Raised when forecast evidence cannot be bound safely."""


__all__ = ["EnsembleInputError"]
