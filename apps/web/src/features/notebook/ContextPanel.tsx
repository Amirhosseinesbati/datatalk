import { useState } from 'react'
import { ArrowUpRight, BookOpen, Database, Hash, Search, ShieldCheck } from 'lucide-react'
import type { Catalog } from '../../api/client'

export function ContextPanel({ catalog, onOpenGlossary }: { catalog?: Catalog; onOpenGlossary: () => void }) {
  const [filter, setFilter] = useState('')
  const term = filter.trim().toLowerCase()
  const metrics = catalog?.metrics.filter(item => `${item.key} ${item.name} ${item.definition}`.toLowerCase().includes(term)) || []
  const dimensions = catalog?.dimensions.filter(item => `${item.key} ${item.name}`.toLowerCase().includes(term)) || []
  return <aside className="context-panel" aria-label="Schema and data context">
    <div className="context-heading"><span><Database size={16} /> Data context</span><ShieldCheck size={15} /></div>
    <div className="context-body">
      <label className="context-search"><Search size={14} /><span className="sr-only">Filter data context</span><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Find a metric or dimension…" /></label>
      <div className="context-section-heading"><BookOpen size={13} /> METRICS <span>{catalog?.metrics.length ?? '—'}</span></div>
      {!catalog && <p className="context-note">Definitions are unavailable until the catalog loads.</p>}
      {metrics.map(metric => <details className="context-metric" key={metric.key}><summary><Hash size={13} /><span>{metric.name}<code>{metric.key}</code></span></summary><p>{metric.definition}</p>{metric.unit && <small>Unit: {metric.unit === 'usd_cents' ? 'USD cents' : metric.unit}</small>}</details>)}
      {!!catalog && !metrics.length && <p className="context-note">No matching metrics.</p>}
      <div className="context-section-heading"><Hash size={13} /> DIMENSIONS <span>{catalog?.dimensions.length ?? '—'}</span></div>
      <div className="dimension-tags">{dimensions.map(item => <span key={item.key} title={item.definition || item.name}>{item.key}</span>)}</div>
      <details className="context-sources"><summary><Database size={13} /> Source tables <span>{catalog?.source_tables?.length ?? '—'}</span></summary>{catalog?.source_tables?.map(source => <code key={source}>{source}</code>)}{!catalog?.source_tables?.length && <p className="context-note">Source names were not supplied.</p>}</details>
      <div className="context-contract"><strong>Query contract</strong><span>Read-only analytical views</span><span>Dates: {catalog?.date_conventions?.timezone || 'UTC'} · half-open ranges</span><span>Currency: {catalog?.date_conventions?.currency || 'See catalog'}</span><span>Relative dates follow the snapshot reference.</span></div>
      <button className="context-glossary" onClick={onOpenGlossary}>Open full catalog <ArrowUpRight size={14} /></button>
    </div>
  </aside>
}
