CREATE TABLE position_reduction_authority_evidence (
    reduction_id text PRIMARY KEY,
    position_id text NOT NULL REFERENCES position_state(position_id),
    position_version integer NOT NULL CHECK (position_version > 0),
    position_evidence_hash char(64) NOT NULL CHECK (position_evidence_hash ~ '^[0-9a-f]{64}$'),
    governance_context_id text NOT NULL,
    governance_context_payload_hash char(64) NOT NULL CHECK (governance_context_payload_hash ~ '^[0-9a-f]{64}$'),
    risk_decision_id text NOT NULL,
    risk_decision_payload_hash char(64) NOT NULL CHECK (risk_decision_payload_hash ~ '^[0-9a-f]{64}$'),
    action_kind text NOT NULL,
    risk_direction text NOT NULL CHECK (risk_direction = 'REDUCE'),
    system_state_version integer NOT NULL CHECK (system_state_version > 0),
    effective_constraints_hash char(64) NOT NULL CHECK (effective_constraints_hash ~ '^[0-9a-f]{64}$'),
    requested_quantity numeric NOT NULL CHECK (requested_quantity > 0),
    exit_reason text NOT NULL,
    decision_outcome text NOT NULL,
    payload jsonb NOT NULL,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL
);
CREATE INDEX position_reduction_authority_open
    ON position_reduction_authority_evidence (position_id, created_at, reduction_id);
CREATE TRIGGER position_reduction_authority_no_mutation
    BEFORE UPDATE OR DELETE ON position_reduction_authority_evidence
    FOR EACH ROW EXECUTE FUNCTION reject_event_record_mutation();
