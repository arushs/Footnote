-- Migration: Add user_id to chunks table for tenant isolation
-- This provides defense-in-depth access control at the database level

-- Step 1: Add nullable user_id column (idempotent)
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS user_id UUID;

-- Step 2: Add foreign key constraint if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chunks_user_id_fkey'
    ) THEN
        ALTER TABLE chunks ADD CONSTRAINT chunks_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Step 3: Backfill user_id from the folder owner via file -> folder chain
UPDATE chunks c
SET user_id = f.user_id
FROM files fi
JOIN folders f ON fi.folder_id = f.id
WHERE c.file_id = fi.id AND c.user_id IS NULL;

-- Step 4: Make user_id non-nullable after backfill (idempotent)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chunks' AND column_name = 'user_id' AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE chunks ALTER COLUMN user_id SET NOT NULL;
    END IF;
END $$;

-- Step 5: Add index for filtered searches (idempotent)
CREATE INDEX IF NOT EXISTS idx_chunks_user_id ON chunks(user_id);
