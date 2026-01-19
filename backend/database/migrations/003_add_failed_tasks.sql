-- Dead Letter Queue table for capturing Celery tasks that have exhausted all retries.
-- This enables debugging, manual retry, and monitoring of failed background tasks.

CREATE TABLE IF NOT EXISTS failed_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) UNIQUE NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    args JSONB,
    kwargs JSONB,
    exception_type VARCHAR(255),
    exception_message TEXT,
    traceback TEXT,
    retries INTEGER DEFAULT 0,
    failed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Index for finding tasks by name (useful for task-specific analysis)
CREATE INDEX IF NOT EXISTS idx_failed_tasks_task_name ON failed_tasks(task_name);

-- Index for finding recent failures (useful for monitoring dashboards)
CREATE INDEX IF NOT EXISTS idx_failed_tasks_failed_at ON failed_tasks(failed_at);

-- Partial index for unresolved tasks (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_failed_tasks_unresolved ON failed_tasks(resolved_at) WHERE resolved_at IS NULL;

-- Comment on table purpose
COMMENT ON TABLE failed_tasks IS 'Dead Letter Queue for Celery tasks that have exhausted all retries';
