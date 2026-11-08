import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import type { OpenDialogOptions } from 'electron'
import path from 'node:path'

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  win.loadURL('http://localhost:5173')
}

ipcMain.handle('dialog:openFile', async (_, options: Pick<OpenDialogOptions, 'filters'> = {}) => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: options.filters ?? [{ name: 'JSON', extensions: ['json'] }],
  })
  return result.canceled ? null : result.filePaths[0] ?? null
})

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
