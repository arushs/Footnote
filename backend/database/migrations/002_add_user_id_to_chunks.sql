-- Migration: Add user_id to chunks table for tenant isolation
-- This provides defense-in-depth access control at the database level

-- Step 1: Add nullable user_id column
ALTER TABLE chunks ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- Step 2: Backfill user_id from the folder owner via file -> folder chain
UPDATE chunks c
SET user_id = f.user_id
FROM files fi
JOIN folders f ON fi.folder_id = f.id
WHERE c.file_id = fi.id;

-- Step 3: Make user_id non-nullable after backfill
ALTER TABLE chunks ALTER COLUMN user_id SET NOT NULL;

-- Step 4: Add index for filtered searches
CREATE INDEX idx_chunks_user_id ON chunks(user_id);
