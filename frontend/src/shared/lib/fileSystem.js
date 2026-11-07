export async function openFile(options = {}) {
  if (window.electron) {
    const path = await window.electron.openFile(options)
    return path ? { path } : null
  }
  // Browser fallback: native file input
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    const exts = options.filters?.flatMap(filter => filter.extensions).map(e => `.${e}`).join(',') ?? '.json'
    input.accept = exts
    input.onchange = () => resolve(input.files[0] ? { file: input.files[0] } : null)
    input.oncancel = () => resolve(null)
    input.click()
  })
}
