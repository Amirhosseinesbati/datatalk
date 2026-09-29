import { useEffect, useRef, type ReactNode } from 'react'
import { AlertCircle, CheckCircle2, LoaderCircle, X } from 'lucide-react'

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty-state">
    <div className="empty-icon" aria-hidden="true">{icon}</div>
    <h3>{title}</h3>
    <p>{children}</p>
    {action}
  </div>
}

export function Notice({ tone = 'info', title, children, onDismiss }: { tone?: 'info' | 'success' | 'error'; title?: string; children: ReactNode; onDismiss?: () => void }) {
  const Icon = tone === 'error' ? AlertCircle : tone === 'success' ? CheckCircle2 : AlertCircle
  return <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
    <Icon size={17} aria-hidden="true" />
    <div>{title && <strong>{title}</strong>}<span>{children}</span></div>
    {onDismiss && <button className="icon-button" onClick={onDismiss} aria-label="Dismiss notice"><X size={16} /></button>}
  </div>
}

export function Loading({ label = 'Loading…', compact = false }: { label?: string; compact?: boolean }) {
  return <div className={`loading ${compact ? 'loading-compact' : ''}`} role="status"><LoaderCircle className="spin" size={18} aria-hidden="true" /><span>{label}</span></div>
}

export function Modal({ title, children, onClose, width = 'normal' }: { title: string; children: ReactNode; onClose: () => void; width?: 'normal' | 'wide' }) {
  const dialog = useRef<HTMLElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') || [])
    const initial = dialog.current?.querySelector<HTMLElement>('[data-autofocus], [autofocus]') || focusable()[0] || dialog.current
    initial?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current(); return }
      if (event.key !== 'Tab') return
      const nodes = focusable()
      if (!nodes.length) { event.preventDefault(); dialog.current?.focus(); return }
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (!dialog.current?.contains(document.activeElement)) { event.preventDefault(); first.focus() }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => { document.removeEventListener('keydown', onKeyDown); document.body.style.overflow = previousOverflow; (previous && previous !== document.body ? previous : document.querySelector<HTMLElement>('[data-modal-return]'))?.focus() }
  }, [])
  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <section ref={dialog} className={`modal modal-${width}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
      <div className="modal-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={19} /></button></div>
      {children}
    </section>
  </div>
}

const monetaryMetrics = new Set(['gross_sales', 'discounts', 'refunds', 'net_revenue', 'average_order_value'])
const comparisonValueColumns = new Set(['current_value', 'previous_value', 'change'])

export function primaryMetric(plan?: Record<string, unknown>): string | undefined {
  const metrics = plan?.metrics
  return Array.isArray(metrics) && typeof metrics[0] === 'string' ? metrics[0] : undefined
}

export function isMoneyColumn(column?: string, metric?: string): boolean {
  return !!column && (column.endsWith('_cents') || (!!metric && monetaryMetrics.has(metric) && comparisonValueColumns.has(column)))
}

export function formatCell(value: unknown, column?: string, metric?: string): string {
  if (value === null || value === undefined || value === '') return '—'
  if (isMoneyColumn(column, metric)) {
    const cents = typeof value === 'number' ? value : Number(value)
    if (Number.isFinite(cents)) return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100)
  }
  if (column?.endsWith('_percent') && typeof value === 'number') return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)}%`
  if (typeof value === 'number') return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

export function formatDate(value?: string): string {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function toTitle(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, character => character.toUpperCase())
}

export function resultColumnTitle(value: string): string {
  return toTitle(value.replace(/_cents$/, ''))
}
