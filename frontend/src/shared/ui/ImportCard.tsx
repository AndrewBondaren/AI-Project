import Icon from './Icon'

interface ImportCardProps {
  label: string
  importing: boolean
  disabled?: boolean
  onImport: () => void
}

export default function ImportCard({ label, importing, disabled, onImport }: ImportCardProps) {
  return (
    <li>
      <button
        type="button"
        className="flex h-full min-h-32 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line bg-panel p-4 text-center font-semibold transition-colors enabled:hover:border-line-hover enabled:hover:bg-raised disabled:opacity-50"
        disabled={disabled || importing}
        aria-busy={importing}
        onClick={onImport}
      >
        <Icon name="import" size={32} />
        <span>{importing ? 'Импорт…' : label}</span>
      </button>
    </li>
  )
}
