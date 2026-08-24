from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance.models import TradingCampaign
from ats.governance.campaign import initialize_campaign_state

from tests.unit.contracts.intelligence.fixtures import T0
from tests.unit.kernel.fixtures import make_kernel_fixture


def campaign(**updates: object) -> TradingCampaign:
    value = make_kernel_fixture()["campaign"]
    assert isinstance(value, TradingCampaign)
    values = value.model_dump(mode="python")
    values.update(updates)
    values["payload_hash"] = "0" * 64
    changed = TradingCampaign.model_validate(values)
    return changed.model_copy(update={"payload_hash": compute_payload_hash(changed)})


def state(campaign_value: TradingCampaign | None = None):
    current = campaign_value or campaign()
    return initialize_campaign_state(current, as_of_time=T0)
