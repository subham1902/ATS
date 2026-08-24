"""R07 thesis synthesis input failures."""


class ThesisSynthesisError(ValueError):
    """Raised when evidence cannot safely produce a market thesis."""


__all__ = ["ThesisSynthesisError"]
