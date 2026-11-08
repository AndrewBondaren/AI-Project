import { useEffect, useRef } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

export default function CreateSessionDialog() {
  const ref = useRef<HTMLDialogElement>(null)
  const navigate = useNavigate()
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    dialog.showModal()
    return () => dialog.close()
  }, [])
  return (
    <dialog ref={ref} className="fixed inset-0 m-auto max-h-[75dvh] w-[min(850px,90vw)] overflow-y-auto rounded-xl border border-line bg-panel p-0 text-foreground shadow-2xl backdrop:bg-black/30 backdrop:backdrop-blur-sm max-sm:max-h-[90dvh] max-sm:w-[95vw]" aria-label="Создание сессии" onCancel={e => { e.preventDefault(); navigate('/') }}>
      <button className="absolute top-4 right-4 z-10 p-1.5" onClick={() => navigate('/')} aria-label="Закрыть">
        <img src="/icons/close.svg" alt="" width="22" height="22" />
      </button>
      <Outlet />
    </dialog>
  )
}
