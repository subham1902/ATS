from ats.market.derivatives.acquisition import UpstoxReadOnlyClient


def test_acquisition_surface_has_no_execution_or_account_mutation_methods() -> None:
    public = {name for name in dir(UpstoxReadOnlyClient) if not name.startswith("_")}
    assert {
        "get_bod_instruments",
        "get_expiries",
        "get_expired_option_contracts",
        "get_expired_future_contracts",
        "get_expired_historical_candles_1m",
        "get_underlying_historical_candles",
    } <= public
    assert not any(
        term in name
        for name in public
        for term in ("order", "trade", "position", "fund", "withdraw", "cancel")
    )
