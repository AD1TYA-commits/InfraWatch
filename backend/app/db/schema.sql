-- InfraWatch canonical PostgreSQL + PostGIS schema.
-- Applied automatically inside the `db` container on first boot (see
-- docker-compose.yml). For local SQLite dev, SQLAlchemy creates an
-- equivalent (non-PostGIS) schema automatically from app/models — see
-- app/models/models.py for the portability note on the geometry column.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS projects (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    project_type        TEXT NOT NULL,
    description         TEXT DEFAULT '',
    latitude            DOUBLE PRECISION NOT NULL,
    longitude           DOUBLE PRECISION NOT NULL,
    -- Keep the local SQLite and PostgreSQL schemas aligned. The application
    -- stores portable WKT here; PostGIS can still be used for later spatial
    -- migrations without blocking the zero-setup demo.
    geometry_wkt        TEXT,
    start_date          DATE,
    expected_end_date   DATE,
    approved_cost       DOUBLE PRECISION,
    reported_progress   DOUBLE PRECISION DEFAULT 0,
    status              TEXT DEFAULT 'normal',
    is_demo             BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS milestones (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_date      DATE NOT NULL,
    expected_progress   DOUBLE PRECISION NOT NULL,
    description         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS financial_records (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    amount              DOUBLE PRECISION NOT NULL,
    category            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress_reports (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    reported_progress   DOUBLE PRECISION NOT NULL,
    source              TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS satellite_observations (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    acquisition_date    DATE NOT NULL,
    source              TEXT NOT NULL,
    image_reference     TEXT NOT NULL,
    cloud_percentage    DOUBLE PRECISION,
    processing_status   TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS ai_results (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    observation_a       INTEGER NOT NULL REFERENCES satellite_observations(id),
    observation_b       INTEGER NOT NULL REFERENCES satellite_observations(id),
    changed_area        DOUBLE PRECISION,
    observed_progress   DOUBLE PRECISION,
    confidence          DOUBLE PRECISION,
    model_version       TEXT DEFAULT 'baseline-diff-v0'
);

CREATE TABLE IF NOT EXISTS anomalies (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type                TEXT NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    severity            TEXT NOT NULL,
    explanation         TEXT NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id                  SERIAL PRIMARY KEY,
    user_action         TEXT NOT NULL,
    project_id          INTEGER REFERENCES projects(id),
    timestamp           TIMESTAMP DEFAULT NOW()
);
