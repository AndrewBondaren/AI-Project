import { contextBridge, ipcRenderer } from 'electron'
import type { OpenDialogOptions } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  openFile: (options?: Pick<OpenDialogOptions, 'filters'>): Promise<string | null> =>
    ipcRenderer.invoke('dialog:openFile', options),
})
