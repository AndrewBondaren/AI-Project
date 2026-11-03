export async function openFile(options = {}) {
  if (window.electron) {
    return window.electron.openFile(options)
  }
  // Browser fallback: native file input
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    const exts = options.filters?.[0]?.extensions?.map(e => `.${e}`).join(',') ?? '.json'
    input.accept = exts
    input.onchange = () => resolve(input.files[0]?.path ?? null)
    input.click()
  })
}
