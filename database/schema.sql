-- Talk-to-Folder Database Schema
-- PostgreSQL with pgvector extension for vector similarity search

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table: Stores authenticated users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions table: OAuth token storage
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

-- Folders table: Indexed Google Drive folders
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    google_folder_id TEXT NOT NULL,
    folder_name TEXT,
    index_status TEXT DEFAULT 'pending',  -- pending, indexing, ready, failed
    files_total INT DEFAULT 0,
    files_indexed INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, google_folder_id)
);

CREATE INDEX idx_folders_user_id ON folders(user_id);
CREATE INDEX idx_folders_status ON folders(index_status);

-- Files table: Individual files within folders
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    google_file_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    modified_time TIMESTAMPTZ,
    file_preview TEXT,
    file_embedding vector(768),  -- Nomic embedding dimension
    index_status TEXT DEFAULT 'pending',  -- pending, indexing, completed, failed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(folder_id, google_file_id)
);

CREATE INDEX idx_files_folder_id ON files(folder_id);
CREATE INDEX idx_files_status ON files(index_status);

-- Vector index for file-level retrieval (Stage 1)
CREATE INDEX idx_files_embedding ON files
    USING ivfflat (file_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Chunks table: Text chunks for fine-grained retrieval
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_embedding vector(768),
    -- Location metadata stored as JSONB for flexibility
    -- Examples:
    --   {"type": "pdf", "page": 3, "block_index": 2}
    --   {"type": "doc", "heading_path": "Intro > Background", "para_index": 5}
    --   {"type": "sheet", "sheet_name": "Q4", "row_range": "1-25"}
    location JSONB NOT NULL,
    chunk_index INT NOT NULL,  -- Ordering within file
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_file_id ON chunks(file_id);

-- Vector index for chunk-level retrieval (Stage 2)
CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (chunk_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Conversations table: Chat sessions per folder
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_folder_id ON conversations(folder_id);

-- Messages table: Individual messages in conversations
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    citations JSONB,  -- Parsed citation data for assistant messages
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- Indexing jobs table: Background worker job queue
CREATE TABLE indexing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    file_id UUID REFERENCES files(id) ON DELETE CASCADE UNIQUE,
    status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    priority INT DEFAULT 0,  -- Higher = process first
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_indexing_jobs_status ON indexing_jobs(status, priority DESC, created_at);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update folders.updated_at
CREATE TRIGGER update_folders_updated_at
    BEFORE UPDATE ON folders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
