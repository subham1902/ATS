from ats.market.derivatives.providers import DerivativeMarketFeed


def test_provider_protocol_does_not_expose_credentials_or_execution() -> None:
    names = set(DerivativeMarketFeed.__dict__)
    assert names.isdisjoint({"credentials", "place_order", "submit_order", "token"})
