"""Unit tests for Dynamic Datasets: Add, Delete, Immediate Proving, and Merging."""

from ats.console.app import create_console_app
from ats.datasets.service import DatasetRegistryService
from fastapi.testclient import TestClient

SAMPLE_CSV_DATA_1 = """time,open,high,low,close,volume
2026-09-26 09:15:00,75000.0,75100.0,74950.0,75050.0,1200
2026-09-26 09:20:00,75050.0,75120.0,75020.0,75100.0,1500
2026-09-26 09:25:00,75100.0,75180.0,75080.0,75150.0,2100
2026-09-26 09:30:00,75150.0,75200.0,75130.0,75180.0,1800
2026-09-26 09:35:00,75180.0,75250.0,75160.0,75220.0,2400
"""

SAMPLE_CSV_DATA_2 = """time,open,high,low,close,volume
2026-09-26 09:35:00,75180.0,75250.0,75160.0,75220.0,2400
2026-09-26 09:40:00,75220.0,75280.0,75200.0,75260.0,1950
2026-09-26 09:45:00,75260.0,75320.0,75240.0,75300.0,2800
2026-09-26 09:50:00,75300.0,75350.0,75280.0,75340.0,3100
2026-09-26 09:55:00,75340.0,75400.0,75320.0,75380.0,2900
"""


def test_dataset_service_add_prove_merge_delete(tmp_path):
    service = DatasetRegistryService(base_dir=tmp_path)

    # 1. Add Dataset 1
    d1 = service.add_dataset(
        dataset_id="TEST_GOLD_M1",
        name="Test Gold Part 1",
        timeframe="5m",
        symbol="MCX:GOLDM FUT",
        raw_text_or_rows=SAMPLE_CSV_DATA_1,
        auto_prove=True,
    )
    assert d1["id"] == "TEST_GOLD_M1"
    assert d1["rows"] == 5
    assert d1["proving_status"] == "PROVEN_PRISTINE"
    assert d1["proof_report"]["ohlc_violations"] == 0
    assert d1["proof_report"]["certificate_id"].startswith("CERT-PROVE-TEST_GOLD_M1")

    # 2. Add Dataset 2
    d2 = service.add_dataset(
        dataset_id="TEST_GOLD_M2",
        name="Test Gold Part 2",
        timeframe="5m",
        symbol="MCX:GOLDM FUT",
        raw_text_or_rows=SAMPLE_CSV_DATA_2,
        auto_prove=True,
    )
    assert d2["id"] == "TEST_GOLD_M2"
    assert d2["rows"] == 5

    # 3. List Datasets
    all_datasets = service.list_datasets()
    assert len(all_datasets) == 2

    # 4. Merge Datasets (1 overlap at 09:35:00 -> 5 + 5 - 1 = 9 rows after deduplication)
    merged = service.merge_datasets(
        source_dataset_ids=["TEST_GOLD_M1", "TEST_GOLD_M2"],
        new_dataset_id="TEST_GOLD_COMBINED",
        new_name="Synthesized Combined Gold",
        deduplicate=True,
    )
    assert merged["id"] == "TEST_GOLD_COMBINED"
    assert merged["rows"] == 9
    assert merged["proving_status"] == "PROVEN_PRISTINE"
    assert merged["proof_report"]["total_bars"] == 9
    assert merged["proof_report"]["duplicate_timestamps"] == 0

    # 5. Delete one dataset
    deleted = service.delete_dataset("TEST_GOLD_M1")
    assert deleted is True
    assert len(service.list_datasets()) == 2

    # Verify TEST_GOLD_M1 no longer exists
    assert service.get_dataset("TEST_GOLD_M1") is None


def test_datasets_api_endpoints():
    app = create_console_app()
    client = TestClient(app)

    # 1. GET /v1/datasets
    res = client.get("/v1/datasets")
    assert res.status_code == 200
    assert "datasets" in res.json()

    # 2. POST /v1/datasets (Add fresh dataset)
    create_res = client.post(
        "/v1/datasets",
        json={
            "id": "API_TEST_DATASET",
            "name": "API Test Fresh Dataset",
            "timeframe": "5m",
            "symbol": "NSE:NIFTY50",
            "source": "Operator Upload",
            "raw_text": SAMPLE_CSV_DATA_1,
            "auto_prove": True,
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()["dataset"]
    assert created["id"] == "API_TEST_DATASET"
    assert created["proving_status"] == "PROVEN_PRISTINE"

    # 3. GET /v1/datasets/{id}
    detail_res = client.get("/v1/datasets/API_TEST_DATASET")
    assert detail_res.status_code == 200
    assert len(detail_res.json()["sample_data"]) == 5

    # 4. POST /v1/datasets/{id}/prove
    prove_res = client.post("/v1/datasets/API_TEST_DATASET/prove")
    assert prove_res.status_code == 200
    assert prove_res.json()["status"] == "success"
    assert prove_res.json()["proving_status"] == "PROVEN_PRISTINE"

    # 5. Add second dataset to test merge
    client.post(
        "/v1/datasets",
        json={
            "id": "API_TEST_DATASET_2",
            "name": "API Test Part 2",
            "timeframe": "5m",
            "symbol": "NSE:NIFTY50",
            "raw_text": SAMPLE_CSV_DATA_2,
            "auto_prove": True,
        },
    )

    # 6. POST /v1/datasets/merge
    merge_res = client.post(
        "/v1/datasets/merge",
        json={
            "source_dataset_ids": ["API_TEST_DATASET", "API_TEST_DATASET_2"],
            "new_dataset_id": "API_TEST_MERGED",
            "new_name": "API Merged Dataset",
            "deduplicate": True,
        },
    )
    assert merge_res.status_code == 200
    merged_data = merge_res.json()["dataset"]
    assert merged_data["id"] == "API_TEST_MERGED"
    assert merged_data["rows"] == 9
    assert merged_data["proving_status"] == "PROVEN_PRISTINE"

    # 7. GET /v1/datasets/{id}/export
    export_res = client.get("/v1/datasets/API_TEST_MERGED/export")
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    assert "75000.0" in export_res.text

    # 8. Clean up created test datasets via DELETE
    for tid in ["API_TEST_DATASET", "API_TEST_DATASET_2", "API_TEST_MERGED"]:
        del_res = client.delete(f"/v1/datasets/{tid}")
        assert del_res.status_code == 200
