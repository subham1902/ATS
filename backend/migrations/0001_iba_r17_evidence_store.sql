CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE event_records (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    event_version integer NOT NULL CHECK (event_version > 0),
    aggregate_id text NOT NULL,
    sequence bigint NOT NULL CHECK (sequence > 0),
    causation_id text,
    correlation_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL CHECK (recorded_at >= occurred_at),
    producer text NOT NULL,
    schema_version text NOT NULL,
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    envelope jsonb NOT NULL,
    trace_id text NOT NULL,
    UNIQUE (aggregate_id, sequence)
);
CREATE INDEX event_records_correlation_order
    ON event_records (correlation_id, recorded_at, event_id);
CREATE INDEX event_records_time_order ON event_records (recorded_at, event_id);

CREATE FUNCTION reject_event_record_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'event_records are immutable' USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER event_records_no_update
    BEFORE UPDATE OR DELETE ON event_records
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();

CREATE TYPE outbox_state AS ENUM ('PENDING', 'DISPATCHING', 'DISPATCHED', 'FAILED');
CREATE TYPE external_submission_state AS ENUM ('NOT_SUBMITTED', 'UNKNOWN', 'CONFIRMED', 'REJECTED');
CREATE TABLE outbox_records (
    outbox_id text PRIMARY KEY,
    event_id text NOT NULL REFERENCES event_records(event_id),
    topic text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    state outbox_state NOT NULL DEFAULT 'PENDING',
    external_state external_submission_state NOT NULL DEFAULT 'NOT_SUBMITTED',
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at timestamptz NOT NULL,
    locked_at timestamptz,
    dispatched_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL
);
CREATE INDEX outbox_dispatch_queue ON outbox_records (available_at, created_at)
    WHERE state IN ('PENDING', 'FAILED');

CREATE TABLE autonomy_token_state (
    token_id text PRIMARY KEY,
    candidate_id text NOT NULL,
    policy_id text NOT NULL,
    policy_version integer NOT NULL CHECK (policy_version > 0),
    risk_decision_id text NOT NULL,
    advisory_id text NOT NULL,
    system_state_version integer NOT NULL CHECK (system_state_version > 0),
    scope text NOT NULL,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > issued_at),
    consumed_at timestamptz,
    nonce_hash char(64) NOT NULL CHECK (nonce_hash ~ '^[0-9a-f]{64}$'),
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    token_payload jsonb NOT NULL
);
CREATE UNIQUE INDEX autonomy_token_authority_binding
    ON autonomy_token_state (
        candidate_id, policy_id, policy_version, risk_decision_id, advisory_id,
        system_state_version
    );

CREATE TABLE candidate_evidence (
    candidate_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL,
    PRIMARY KEY (candidate_id, version)
);
CREATE TABLE risk_decision_evidence (
    risk_decision_id text PRIMARY KEY,
    candidate_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL
);
CREATE TABLE advisory_evidence (
    advisory_id text PRIMARY KEY,
    candidate_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    model_version text NOT NULL,
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL
);

CREATE TABLE campaign_state (
    campaign_id text PRIMARY KEY,
    version integer NOT NULL CHECK (version > 0),
    state text NOT NULL,
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    updated_at timestamptz NOT NULL
);
CREATE TABLE position_state (
    position_id text PRIMARY KEY,
    version integer NOT NULL CHECK (version > 0),
    state text NOT NULL,
    external_state external_submission_state NOT NULL DEFAULT 'NOT_SUBMITTED',
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    updated_at timestamptz NOT NULL
);
CREATE TABLE order_authority_evidence (
    authority_id text PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE,
    token_id text NOT NULL REFERENCES autonomy_token_state(token_id),
    external_state external_submission_state NOT NULL DEFAULT 'NOT_SUBMITTED',
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL
);

CREATE TABLE audit_records (
    audit_id text PRIMARY KEY,
    event_id text,
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    action text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    payload jsonb NOT NULL,
    record_hash char(64) NOT NULL CHECK (record_hash ~ '^[0-9a-f]{64}$'),
    occurred_at timestamptz NOT NULL,
    trace_id text NOT NULL
);

CREATE TRIGGER candidate_evidence_no_mutation
    BEFORE UPDATE OR DELETE ON candidate_evidence
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();
CREATE TRIGGER risk_evidence_no_mutation
    BEFORE UPDATE OR DELETE ON risk_decision_evidence
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();
CREATE TRIGGER advisory_evidence_no_mutation
    BEFORE UPDATE OR DELETE ON advisory_evidence
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();
CREATE TRIGGER order_authority_no_mutation
    BEFORE UPDATE OR DELETE ON order_authority_evidence
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();
CREATE TRIGGER audit_records_no_mutation
    BEFORE UPDATE OR DELETE ON audit_records
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();
