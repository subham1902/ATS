from pathlib import Path


def test_schema_has_required_table_families_and_postgres_integrity() -> None:
    sql = Path("backend/migrations/0001_iba_r17_evidence_store.sql").read_text()
    tables = {
        "event_records",
        "outbox_records",
        "autonomy_token_state",
        "candidate_evidence",
        "risk_decision_evidence",
        "advisory_evidence",
        "campaign_state",
        "position_state",
        "order_authority_evidence",
        "audit_records",
    }
    assert all(f"CREATE TABLE {table}" in sql for table in tables)
    assert "UNIQUE (aggregate_id, sequence)" in sql
    assert "idempotency_key text NOT NULL UNIQUE" in sql
    assert "UNKNOWN" in sql
    assert "reject_event_record_mutation" in sql


def test_no_secret_or_cloud_configuration_in_owned_source() -> None:
    roots = (Path("backend/src/ats/persistence"), Path("backend/migrations"))
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".sql", ".md"}
    ).lower()
    assert "neon.tech" not in combined
    assert "password=" not in combined
    assert "postgresql://" not in combined
