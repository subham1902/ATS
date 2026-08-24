"""Derivative instrument-selection boundary failures."""


class InstrumentSelectionError(ValueError):
    """Raised when supplied evidence is inconsistent or unsafe to rank."""


__all__ = ["InstrumentSelectionError"]
