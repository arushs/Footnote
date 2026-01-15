import { Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/chat/:folderId" element={<ChatPage />} />
    </Routes>
  )
}

function LandingPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-6 max-w-md px-4">
        <h1 className="text-4xl font-bold text-foreground">Talk to a Folder</h1>
        <p className="text-muted-foreground">
          Chat with your Google Drive documents using AI
        </p>
        <a
          href="/api/auth/google"
          className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Sign in with Google
        </a>
      </div>
    </div>
  )
}

function ChatPage() {
  return (
    <div className="min-h-screen flex bg-background">
      <aside className="w-64 border-r border-border p-4">
        <h2 className="font-semibold text-foreground">Chat History</h2>
      </aside>
      <main className="flex-1 flex flex-col">
        <div className="flex-1 p-4">
          <p className="text-muted-foreground">Messages will appear here</p>
        </div>
        <div className="border-t border-border p-4">
          <input
            type="text"
            placeholder="Ask about your files..."
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
        </div>
      </main>
      <aside className="w-72 border-l border-border p-4">
        <h2 className="font-semibold text-foreground">Sources</h2>
      </aside>
    </div>
  )
}

export default App
