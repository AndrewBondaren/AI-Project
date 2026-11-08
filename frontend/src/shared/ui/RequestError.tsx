export default function RequestError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-2 text-danger">
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="rounded border border-line px-2 py-1 text-xs text-foreground hover:bg-raised">
          Повторить
        </button>
      )}
    </div>
  )
}
