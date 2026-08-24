# IBA-R17 migrations

`0001_iba_r17_evidence_store.sql` is the deterministic empty-database baseline.
Apply it through `ats.persistence.migrations.apply_migrations`; applied versions are
recorded in `schema_migrations` and never re-run. PostgreSQL is the only supported
dialect. No legacy upgrade path is claimed.
