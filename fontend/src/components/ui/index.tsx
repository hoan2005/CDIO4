import React from 'react'

// ── Spinner ──────────────────────────────────────────────
export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size} height={size}
      viewBox="0 0 24 24"
      className="animate-spin text-accent"
      fill="none" stroke="currentColor" strokeWidth={2}
    >
      <circle cx="12" cy="12" r="10" strokeOpacity={0.25} />
      <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
    </svg>
  )
}

// ── Typing indicator ─────────────────────────────────────
export function TypingDots() {
  return (
    <div className="flex items-center gap-1 h-5">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-accent/70 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}

// ── Badge ────────────────────────────────────────────────
export function Badge({ children, color = 'accent' }: { children: React.ReactNode; color?: string }) {
  const colorMap: Record<string, string> = {
    accent: 'bg-accent/20 text-accent border-accent/30',
    green:  'bg-math-green/20 text-math-green border-math-green/30',
    blue:   'bg-math-blue/20 text-math-blue border-math-blue/30',
    yellow: 'bg-math-yellow/20 text-math-yellow border-math-yellow/30',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-mono ${colorMap[color] ?? colorMap.accent}`}>
      {children}
    </span>
  )
}

// ── Icon Button ──────────────────────────────────────────
interface IconBtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
}
export function IconBtn({ children, label, className = '', ...props }: IconBtnProps) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`p-1.5 rounded-lg text-white/40 hover:text-white/80 hover:bg-white/5 transition-colors ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

// ── Tooltip wrapper ──────────────────────────────────────
export function Tooltip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="relative group">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded text-xs bg-bg-secondary border border-border-subtle text-white/70 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-50">
        {label}
      </span>
    </div>
  )
}
