import json
from pathlib import Path

import pytest
from ats.strategies.small_account_presets import SmallAccountPreset

ROOT = Path(__file__).resolve().parents[3]


def presets():
    return json.loads(
        (ROOT / "docs/research/presets/gold-triple-small-account-v3.json").read_text()
    )["presets"]


def test_frozen_presets_cannot_grant_authority_and_reproduce_native_settings():
    s2, s3 = [SmallAccountPreset.model_validate(p) for p in presets()]
    assert not s2.execution_eligible and not s3.execution_eligible
    assert s3.native_inputs("ACC-test", "XAUUSDm")["AllowedWeekdayMask"] == "28"
    assert s2.native_inputs("ACC-test", "GOLD")["AllowedWeekdayMask"] == "62"
    assert s3.native_inputs("ACC-test", "XAUUSD")["EnabledStrategyMask"] == "4"
    assert s2.native_inputs("ACC-test", "XAUUSD")["EnabledStrategyMask"] == "2"
    assert s3.native_inputs("ACC-test", "XAUUSD")["ClockProfileCsv"] == ""
    assert s2.preset_hash != s3.preset_hash


@pytest.mark.parametrize(
    "change",
    [
        {"research_initial_capital": "500"},
        {"risk_fraction": "0.02"},
        {"execution_eligible": True},
        {"parent_retest_level": "M15_CLOSE"},
        {"weekdays_utc": [0, 1, 2, 3, 4]},
        {"profit_protection": True},
    ],
)
def test_unknown_balance_or_unverified_variant_does_not_inherit_results(change):
    with pytest.raises(ValueError):
        SmallAccountPreset.model_validate({**presets()[1], **change})


def test_native_inputs_reject_path_or_line_injection():
    preset = SmallAccountPreset.model_validate(presets()[1])
    for account, symbol in (("ACC-../other", "XAUUSD"), ("ACC-valid", "XAUUSD\nTargetR=10")):
        with pytest.raises(ValueError):
            preset.native_inputs(account, symbol)
