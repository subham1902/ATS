"""Campaign runtime transition failures."""


class CampaignRuntimeError(ValueError):
    """Raised when a requested campaign state mutation is invalid."""


__all__ = ["CampaignRuntimeError"]
