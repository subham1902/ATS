from __future__ import annotations

import pytest
from ats.market.derivatives.contract_master import (
    ContractMaster,
    DerivativeInstrument,
    normalize_contract_master,
)

from tests.unit.market.derivatives.contract_master.helpers import content, manifest


@pytest.mark.parametrize("model", [ContractMaster, DerivativeInstrument])
def test_public_models_export_json_schema(
    model: type[ContractMaster] | type[DerivativeInstrument],
) -> None:
    schema = model.model_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_json_round_trip_is_deterministic() -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    encoded = master.model_dump_json()
    assert ContractMaster.model_validate_json(encoded) == master


def test_authority_fields_are_required_and_strict() -> None:
    required = ContractMaster.model_json_schema()["required"]
    assert set(required) == {"schema_version", "manifest", "instruments", "payload_hash"}
