"""R07 deterministic market-thesis synthesis."""

from .engine import synthesize_market_thesis
from .errors import ThesisSynthesisError
from .models import (
    ThesisSynthesisConfiguration,
    ThesisSynthesisFacts,
    ThesisSynthesisResult,
    ThesisSynthesisStatus,
)

__all__ = [
    "ThesisSynthesisConfiguration",
    "ThesisSynthesisError",
    "ThesisSynthesisFacts",
    "ThesisSynthesisResult",
    "ThesisSynthesisStatus",
    "synthesize_market_thesis",
]
