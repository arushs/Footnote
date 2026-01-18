-- Migration: Add hybrid search support (tsvector columns and GIN indexes)
-- Run this migration on existing databases to enable hybrid search

-- Add search_vector column to files table
ALTER TABLE files ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Add search_vector column to chunks table
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Add last_synced_at column to folders table for diff-based sync
ALTER TABLE folders ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;

-- Create GIN indexes for full-text search
CREATE INDEX IF NOT EXISTS idx_files_search_vector ON files USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_chunks_search_vector ON chunks USING GIN(search_vector);

-- Function to auto-update file search_vector
CREATE OR REPLACE FUNCTION update_file_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.file_name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.file_preview, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for files (drop first to avoid duplicates)
DROP TRIGGER IF EXISTS files_search_vector_update ON files;
CREATE TRIGGER files_search_vector_update
    BEFORE INSERT OR UPDATE OF file_name, file_preview ON files
    FOR EACH ROW EXECUTE FUNCTION update_file_search_vector();

-- Function to auto-update chunk search_vector
CREATE OR REPLACE FUNCTION update_chunk_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', coalesce(NEW.chunk_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for chunks (drop first to avoid duplicates)
DROP TRIGGER IF EXISTS chunks_search_vector_update ON chunks;
CREATE TRIGGER chunks_search_vector_update
    BEFORE INSERT OR UPDATE OF chunk_text ON chunks
    FOR EACH ROW EXECUTE FUNCTION update_chunk_search_vector();

-- Backfill search_vector for existing files
UPDATE files
SET search_vector =
    setweight(to_tsvector('english', coalesce(file_name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(file_preview, '')), 'B')
WHERE search_vector IS NULL;

-- Backfill search_vector for existing chunks
UPDATE chunks
SET search_vector = to_tsvector('english', coalesce(chunk_text, ''))
WHERE search_vector IS NULL;
