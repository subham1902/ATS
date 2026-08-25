from ats.market.derivatives.normalization import NormalizedDerivativeContract


def test_normalized_contract_has_provider_aliases_but_no_authority_methods() -> None:
    fields = set(NormalizedDerivativeContract.model_fields)
    assert {
        "instrument_id",
        "provider_instrument_key",
        "provider_exchange_token",
        "contract_hash",
    } <= fields
    assert not hasattr(NormalizedDerivativeContract, "place_order")
