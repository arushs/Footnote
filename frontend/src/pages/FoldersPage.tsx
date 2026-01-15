import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderOpen, Plus, Loader2, Trash2 } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useGooglePicker } from '../hooks/useGooglePicker'
import { Button } from '../components/ui/button'

interface Folder {
  id: string
  google_folder_id: string
  folder_name: string
  index_status: string
  files_total: number
  files_indexed: number
}

export function FoldersPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { isLoaded, openPicker } = useGooglePicker()
  const [folders, setFolders] = useState<Folder[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const fetchFolders = async () => {
    try {
      const response = await fetch('/api/folders', {
        credentials: 'include',
      })
      if (response.ok) {
        const data = await response.json()
        setFolders(data.folders)
      }
    } catch (error) {
      console.error('Failed to fetch folders:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFolders()
  }, [])

  // Poll for indexing status updates
  useEffect(() => {
    const indexingFolders = folders.filter((f) => f.index_status === 'indexing')
    if (indexingFolders.length === 0) return

    const interval = setInterval(async () => {
      for (const folder of indexingFolders) {
        try {
          const response = await fetch(`/api/folders/${folder.id}/status`, {
            credentials: 'include',
          })
          if (response.ok) {
            const status = await response.json()
            setFolders((prev) =>
              prev.map((f) =>
                f.id === folder.id
                  ? { ...f, index_status: status.status, files_indexed: status.files_indexed }
                  : f
              )
            )
          }
        } catch (error) {
          console.error('Failed to poll folder status:', error)
        }
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [folders])

  const handleAddFolder = async () => {
    if (!isLoaded) return

    try {
      const result = await openPicker()
      if (!result) return

      setCreating(true)
      const response = await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          google_folder_id: result.id,
          folder_name: result.name,
        }),
      })

      if (response.ok) {
        const newFolder = await response.json()
        setFolders((prev) => [...prev, newFolder])
      }
    } catch (error) {
      console.error('Failed to create folder:', error)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteFolder = async (folderId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this folder?')) return

    try {
      const response = await fetch(`/api/folders/${folderId}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (response.ok) {
        setFolders((prev) => prev.filter((f) => f.id !== folderId))
      }
    } catch (error) {
      console.error('Failed to delete folder:', error)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-foreground">Talk to a Folder</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">{user?.email}</span>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-medium text-foreground">Your Folders</h2>
          <Button onClick={handleAddFolder} disabled={!isLoaded || creating}>
            {creating ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Plus className="h-4 w-4 mr-2" />
            )}
            Add Folder
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : folders.length === 0 ? (
          <div className="text-center py-12 border border-dashed border-border rounded-lg">
            <FolderOpen className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">No folders yet</p>
            <Button onClick={handleAddFolder} disabled={!isLoaded}>
              <Plus className="h-4 w-4 mr-2" />
              Add your first folder
            </Button>
          </div>
        ) : (
          <div className="grid gap-4">
            {folders.map((folder) => (
              <div
                key={folder.id}
                onClick={() => folder.index_status === 'ready' && navigate(`/chat/${folder.id}`)}
                className={`
                  p-4 border border-border rounded-lg
                  ${folder.index_status === 'ready' ? 'cursor-pointer hover:bg-accent' : 'opacity-75'}
                `}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FolderOpen className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">{folder.folder_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {folder.files_indexed} / {folder.files_total} files indexed
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {folder.index_status === 'indexing' && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Indexing...
                      </div>
                    )}
                    {folder.index_status === 'ready' && (
                      <span className="text-sm text-green-600">Ready</span>
                    )}
                    {folder.index_status === 'failed' && (
                      <span className="text-sm text-red-600">Failed</span>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => handleDeleteFolder(folder.id, e)}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
