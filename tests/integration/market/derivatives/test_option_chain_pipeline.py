from __future__ import annotations

from ats.market.derivatives.option_chain import build_option_chain, compute_option_chain_evidence

from tests.unit.market.derivatives.option_chain.helpers import context, master, quote


def test_contract_master_to_chain_to_evidence_pipeline() -> None:
    contract_master = master()
    chain = build_option_chain(
        contract_master=contract_master,
        context=context(),
        inputs=(quote("C1"), quote("C2"), quote("P2"), quote("P3")),
    )
    evidence = compute_option_chain_evidence(chain)
    assert len(chain.quotes) == 4
    assert evidence.chain_id == chain.chain_id
    assert evidence.data_cutoff == chain.data_cutoff
    assert all(item.data_cutoff <= chain.as_of_time for item in chain.quotes)
