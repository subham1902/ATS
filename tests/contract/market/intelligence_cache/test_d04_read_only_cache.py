from ats.market.intelligence_cache import MarketIntelligenceCache, MarketIntelligenceSnapshot


def test_intelligence_cache_is_evidence_only_and_has_no_refresh_or_authority_surface() -> None:
    cache_methods = {name for name in dir(MarketIntelligenceCache) if not name.startswith("_")}
    assert cache_methods == {"read", "update"}
    assert not hasattr(MarketIntelligenceSnapshot, "authorize")
    assert not hasattr(MarketIntelligenceSnapshot, "place_order")
