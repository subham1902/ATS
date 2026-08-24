"""Paper execution boundary failures."""


class PaperExecutionError(ValueError):
    """Raised when a paper action is structurally unsafe."""


__all__ = ["PaperExecutionError"]
