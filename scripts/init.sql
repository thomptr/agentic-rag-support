CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS observation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_observation_logs_run_id ON observation_logs(run_id);
CREATE INDEX idx_observation_logs_event_type ON observation_logs(event_type);
