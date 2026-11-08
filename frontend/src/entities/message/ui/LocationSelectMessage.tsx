import type { LocationChoice, LocationSelectData, LocationSelectHandler, SceneReadyData } from '@/shared/types/chat'

interface SelectionProps {
  isActive: boolean
  isStreaming: boolean
  onSelect?: LocationSelectHandler
}

type LocationButtonsProps = SelectionProps & { children: LocationChoice[] }
type LocationSelectProps = SelectionProps & { data: LocationSelectData }

function LocationButtons({ children, isActive, isStreaming, onSelect }: LocationButtonsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {children.map(child => (
        <button
          key={child.id}
          className={`flex items-center gap-1 rounded-lg border border-line bg-raised px-3 py-2 text-sm transition-colors enabled:hover:border-line-hover enabled:hover:bg-accent/7 disabled:cursor-default disabled:opacity-40 ${child.isHome ? "border-accent/40" : ''}`}
          disabled={!isActive || isStreaming}
          onClick={() => onSelect?.(child.id, child.name)}
        >
          <span className="flex flex-col items-start gap-0.5">
            <span className="text-sm font-medium">{child.name}</span>
            {(child.typeLabel || child.stateName) && (
              <span className="flex items-center gap-1">
                {child.typeLabel && <span className="text-xs text-muted">{child.typeLabel}</span>}
                {child.typeLabel && child.stateName && <span className="text-xs text-muted opacity-50">·</span>}
                {child.stateName && <span className="text-xs text-accent">{child.stateName}</span>}
              </span>
            )}
          </span>
          {child.isHome && <span className="text-xs font-semibold text-accent">дом</span>}
        </button>
      ))}
    </div>
  )
}

export function LocationSelectMessage({ data, isActive, isStreaming, onSelect }: LocationSelectProps) {
  const { parent, children } = data
  const heading = parent
    ? `Выберите место в ${parent.name}:`
    : 'Выберите локацию:'

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted">{heading}</p>
      <LocationButtons
        children={children}
        isActive={isActive}
        isStreaming={isStreaming}
        onSelect={onSelect}
      />
    </div>
  )
}

export function SceneReadyMessage({ data }: { data: SceneReadyData }) {
  const { location } = data
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-semibold tracking-wider text-accent uppercase">Сцена создана</span>
      <p className="text-base font-semibold">{location.name}</p>
      {location.description && (
        <p className="text-sm leading-normal text-muted">{location.description}</p>
      )}
    </div>
  )
}
