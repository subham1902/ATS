CREATE TYPE capital_reservation_state AS ENUM ('RESERVED', 'COMMITTED', 'RELEASED');

CREATE TABLE portfolio_capital_account (
    portfolio_id text PRIMARY KEY,
    version integer NOT NULL CHECK (version > 0),
    total_capital numeric(38,12) NOT NULL CHECK (total_capital > 0),
    deployable_capital numeric(38,12) NOT NULL CHECK (deployable_capital > 0),
    reserved_capital numeric(38,12) NOT NULL DEFAULT 0 CHECK (reserved_capital >= 0),
    used_capital numeric(38,12) NOT NULL DEFAULT 0 CHECK (used_capital >= 0),
    realized_pnl numeric(38,12) NOT NULL DEFAULT 0,
    unrealized_pnl numeric(38,12) NOT NULL DEFAULT 0,
    daily_loss numeric(38,12) NOT NULL DEFAULT 0 CHECK (daily_loss >= 0),
    maximum_drawdown numeric(38,12) NOT NULL DEFAULT 0
        CHECK (maximum_drawdown >= 0 AND maximum_drawdown <= 1),
    loss_state text NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (deployable_capital <= total_capital),
    CHECK (reserved_capital + used_capital <= deployable_capital)
);

CREATE TABLE capital_reservation (
    reservation_id text PRIMARY KEY,
    portfolio_id text NOT NULL REFERENCES portfolio_capital_account(portfolio_id),
    campaign_id text NOT NULL,
    candidate_id text NOT NULL,
    instrument_id text NOT NULL,
    amount numeric(38,12) NOT NULL CHECK (amount > 0),
    state capital_reservation_state NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT capital_reservation_candidate_key UNIQUE (portfolio_id, candidate_id)
);

CREATE INDEX capital_reservation_portfolio_state
    ON capital_reservation (portfolio_id, state, created_at, reservation_id);
