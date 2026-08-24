"""Deterministic R02 regime intelligence."""

from .detector import detect_regime
from .errors import RegimeInputError
from .models import RegimeDetectorConfiguration

__all__ = ["RegimeDetectorConfiguration", "RegimeInputError", "detect_regime"]
