"""R06 deterministic calibration input failures."""


class CalibrationInputError(ValueError):
    """Raised when evidence cannot safely enter calibration."""


__all__ = ["CalibrationInputError"]
