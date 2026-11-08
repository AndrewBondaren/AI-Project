export default function Icon({ name, size = 22, className = '' }: { name: string; size?: number; className?: string }) {
  return <img src={`/icons/${name}.svg`} alt="" width={size} height={size} className={`shrink-0 ${className}`} />
}
