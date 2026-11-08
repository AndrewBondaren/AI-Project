import type { FilePickerOptions } from './files'

declare global {
  interface Window {
    electron?: {
      openFile(options?: FilePickerOptions): Promise<string | null>
    }
  }
}
