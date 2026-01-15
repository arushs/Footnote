import { useCallback, useEffect, useState } from 'react'

const GOOGLE_API_KEY = import.meta.env.VITE_GOOGLE_API_KEY
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
const PICKER_SCOPE = 'https://www.googleapis.com/auth/drive.readonly'

interface PickerResult {
  id: string
  name: string
  mimeType: string
}

declare global {
  interface Window {
    gapi: {
      load: (api: string, callback: () => void) => void
      client: {
        init: (config: { apiKey: string; discoveryDocs?: string[] }) => Promise<void>
        getToken: () => { access_token: string } | null
      }
    }
    google: {
      picker: {
        PickerBuilder: new () => GooglePickerBuilder
        ViewId: {
          FOLDERS: string
          DOCS: string
        }
        DocsView: new (viewId: string) => DocsView
        Feature: {
          MULTISELECT_ENABLED: string
          NAV_HIDDEN: string
        }
        Action: {
          PICKED: string
          CANCEL: string
        }
      }
      accounts: {
        oauth2: {
          initTokenClient: (config: {
            client_id: string
            scope: string
            callback: (response: { access_token?: string; error?: string }) => void
          }) => TokenClient
        }
      }
    }
  }
}

interface TokenClient {
  requestAccessToken: () => void
}

interface DocsView {
  setIncludeFolders: (include: boolean) => DocsView
  setSelectFolderEnabled: (enabled: boolean) => DocsView
  setMimeTypes: (mimeTypes: string) => DocsView
}

interface GooglePickerBuilder {
  addView: (view: DocsView | string) => GooglePickerBuilder
  setOAuthToken: (token: string) => GooglePickerBuilder
  setDeveloperKey: (key: string) => GooglePickerBuilder
  setCallback: (callback: (data: PickerData) => void) => GooglePickerBuilder
  enableFeature: (feature: string) => GooglePickerBuilder
  setTitle: (title: string) => GooglePickerBuilder
  build: () => { setVisible: (visible: boolean) => void }
}

interface PickerData {
  action: string
  docs?: Array<{
    id: string
    name: string
    mimeType: string
  }>
}

export function useGooglePicker() {
  const [isLoaded, setIsLoaded] = useState(false)
  const [accessToken, setAccessToken] = useState<string | null>(null)

  useEffect(() => {
    // Load the Google API script
    const loadScript = (src: string, id: string): Promise<void> => {
      return new Promise((resolve, reject) => {
        if (document.getElementById(id)) {
          resolve()
          return
        }
        const script = document.createElement('script')
        script.src = src
        script.id = id
        script.async = true
        script.defer = true
        script.onload = () => resolve()
        script.onerror = reject
        document.body.appendChild(script)
      })
    }

    const initializeGoogleAPIs = async () => {
      try {
        // Load Google API client
        await loadScript('https://apis.google.com/js/api.js', 'google-api')

        // Load Google Identity Services
        await loadScript('https://accounts.google.com/gsi/client', 'google-gsi')

        // Initialize GAPI
        await new Promise<void>((resolve) => {
          window.gapi.load('picker', () => resolve())
        })

        setIsLoaded(true)
      } catch (error) {
        console.error('Failed to load Google APIs:', error)
      }
    }

    initializeGoogleAPIs()
  }, [])

  const getAccessToken = useCallback((): Promise<string> => {
    return new Promise((resolve, reject) => {
      if (accessToken) {
        resolve(accessToken)
        return
      }

      const tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: GOOGLE_CLIENT_ID,
        scope: PICKER_SCOPE,
        callback: (response) => {
          if (response.error) {
            reject(new Error(response.error))
            return
          }
          if (response.access_token) {
            setAccessToken(response.access_token)
            resolve(response.access_token)
          }
        },
      })

      tokenClient.requestAccessToken()
    })
  }, [accessToken])

  const openPicker = useCallback(async (): Promise<PickerResult | null> => {
    if (!isLoaded) {
      throw new Error('Google APIs not loaded')
    }

    const token = await getAccessToken()

    return new Promise((resolve) => {
      const view = new window.google.picker.DocsView(window.google.picker.ViewId.FOLDERS)
        .setIncludeFolders(true)
        .setSelectFolderEnabled(true)

      const picker = new window.google.picker.PickerBuilder()
        .addView(view)
        .setOAuthToken(token)
        .setDeveloperKey(GOOGLE_API_KEY)
        .setTitle('Select a folder to index')
        .setCallback((data: PickerData) => {
          if (data.action === window.google.picker.Action.PICKED && data.docs?.[0]) {
            const doc = data.docs[0]
            resolve({
              id: doc.id,
              name: doc.name,
              mimeType: doc.mimeType,
            })
          } else if (data.action === window.google.picker.Action.CANCEL) {
            resolve(null)
          }
        })
        .build()

      picker.setVisible(true)
    })
  }, [isLoaded, getAccessToken])

  return {
    isLoaded,
    openPicker,
  }
}
