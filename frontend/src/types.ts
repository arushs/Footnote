// API Types
export interface Citation {
  chunk_id: string
  file_name: string
  location: string
  excerpt: string
  google_drive_url: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Record<string, Citation>
  created_at: string
}

export interface Conversation {
  id: string
  preview: string
  created_at: string
}

export interface FolderStatus {
  status: 'pending' | 'indexing' | 'ready' | 'failed'
  files_total: number
  files_indexed: number
}

export interface Folder {
  id: string
  google_folder_id: string
  folder_name: string
  index_status: string
  files_total: number
  files_indexed: number
}

// Chat State
export interface ChatState {
  messages: Message[]
  isLoading: boolean
  currentConversationId: string | null
  streamingContent: string
  streamingCitations: Record<string, Citation>
}

export interface SourcesState {
  searchedFiles: string[]
  citedSources: Citation[]
}
