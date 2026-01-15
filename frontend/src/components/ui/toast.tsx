import { useEffect, useState } from 'react'
import { X, AlertCircle, CheckCircle2, Info } from 'lucide-react'
import { cn } from '../../lib/utils'

export type ToastType = 'error' | 'success' | 'info'

interface Toast {
  id: string
  message: string
  type: ToastType
}

let toastListeners: ((toasts: Toast[]) => void)[] = []
let toasts: Toast[] = []

function notifyListeners() {
  toastListeners.forEach((listener) => listener([...toasts]))
}

export function addToast(message: string, type: ToastType = 'error') {
  const id = crypto.randomUUID()
  toasts = [...toasts, { id, message, type }]
  notifyListeners()

  // Auto-remove after 5 seconds
  setTimeout(() => {
    removeToast(id)
  }, 5000)
}

export function removeToast(id: string) {
  toasts = toasts.filter((t) => t.id !== id)
  notifyListeners()
}

export function useToasts() {
  const [localToasts, setLocalToasts] = useState<Toast[]>(toasts)

  useEffect(() => {
    toastListeners.push(setLocalToasts)
    return () => {
      toastListeners = toastListeners.filter((l) => l !== setLocalToasts)
    }
  }, [])

  return localToasts
}

export function ToastContainer() {
  const toasts = useToasts()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
      ))}
    </div>
  )
}

interface ToastItemProps {
  toast: Toast
  onClose: () => void
}

function ToastItem({ toast, onClose }: ToastItemProps) {
  const Icon = toast.type === 'error' ? AlertCircle : toast.type === 'success' ? CheckCircle2 : Info

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border p-4 shadow-lg min-w-[300px] max-w-md animate-in slide-in-from-right',
        toast.type === 'error' && 'bg-destructive/10 border-destructive/20 text-destructive',
        toast.type === 'success' && 'bg-green-500/10 border-green-500/20 text-green-600',
        toast.type === 'info' && 'bg-blue-500/10 border-blue-500/20 text-blue-600'
      )}
    >
      <Icon className="h-5 w-5 shrink-0 mt-0.5" />
      <p className="flex-1 text-sm">{toast.message}</p>
      <button
        onClick={onClose}
        className="shrink-0 p-1 rounded hover:bg-black/5 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
