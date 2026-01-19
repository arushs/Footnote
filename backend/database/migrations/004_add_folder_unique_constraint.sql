-- Migration: Add unique constraint on folders(user_id, google_folder_id)
-- This prevents duplicate folders for the same user

-- Only add if it doesn't already exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'folders_user_id_google_folder_id_key'
           OR conname = 'uq_folders_user_google'
    ) THEN
        ALTER TABLE folders ADD CONSTRAINT uq_folders_user_google UNIQUE (user_id, google_folder_id);
    END IF;
END $$;
