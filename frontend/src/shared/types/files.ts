export type FilePickerOptions = {
  filters?: { name: string; extensions: string[] }[]
}

export type FileSource =
  | { file: File; path?: never }
  | { path: string; file?: never }
