import { useMemo, useState } from 'react'
import { BookOpen, CalendarClock, Database, Layers3, Search, SlidersHorizontal } from 'lucide-react'
import type { Catalog, Dimension, Metric } from '../../api/client'
import { EmptyState, toTitle } from '../../ui'

export function CatalogView({ catalog, compact = false }: { catalog: Catalog; compact?: boolean }) {
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState<'all' | 'metrics' | 'dimensions'>('all')
  const query = search.trim().toLowerCase()
  const metrics = useMemo(() => (catalog.metrics || []).filter(item => `${item.key} ${item.name} ${item.definition}`.toLowerCase().includes(query)), [catalog.metrics, query])
  const dimensions = useMemo(() => (catalog.dimensions || []).filter(item => `${item.key} ${item.name} ${item.definition || ''}`.toLowerCase().includes(query)), [catalog.dimensions, query])
  const count = (kind === 'dimensions' ? 0 : metrics.length) + (kind === 'metrics' ? 0 : dimensions.length)
  return <div className={`catalog-view ${compact ? 'catalog-compact' : ''}`}>
    {!compact && <header className="section-intro"><div className="eyebrow"><span className="eyebrow-mark" /> SEMANTIC CATALOG</div><h1>Know what each<br /><em>number means.</em></h1><p>Search approved metrics and dimensions before you ask. These definitions govern the analytical plan.</p></header>}
    <div className="catalog-controls"><label className="search-field"><Search size={18} aria-hidden="true" /><span className="sr-only">Search catalog</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search definitions, names, or fields…" /></label><div className="segmented" role="group" aria-label="Catalog type"><button className={kind === 'all' ? 'selected' : ''} onClick={() => setKind('all')}>All</button><button className={kind === 'metrics' ? 'selected' : ''} onClick={() => setKind('metrics')}>Metrics</button><button className={kind === 'dimensions' ? 'selected' : ''} onClick={() => setKind('dimensions')}>Dimensions</button></div></div>
    <div className="catalog-overview"><span><BookOpen size={16} /> {catalog.metrics?.length ?? 0} governed metrics</span><span><SlidersHorizontal size={16} /> {catalog.dimensions?.length ?? 0} dimensions</span><span><CalendarClock size={16} /> Reference date: {catalog.freshness?.reference_date || 'Unavailable'}</span></div>
    {catalog.date_conventions && <div className="catalog-conventions"><strong>Date & money conventions</strong><span>Timezone: {catalog.date_conventions.timezone || '—'}</span><span>Interval: {catalog.date_conventions.interval || '—'}</span><span>Sales: {catalog.date_conventions.sales_basis || '—'}</span><span>Refunds: {catalog.date_conventions.refund_basis || '—'}</span><span>Currency: {catalog.date_conventions.currency || '—'}</span></div>}
    {count === 0 && <EmptyState icon={<Search size={23} />} title="No matching definitions">Try a different term or show all catalog items.</EmptyState>}
    {kind !== 'dimensions' && metrics.length > 0 && <section className="catalog-section"><div className="catalog-heading"><div><span className="catalog-symbol"><BookOpen size={17} /></span><div><h2>Metrics</h2><p>How your business measures performance</p></div></div><span>{metrics.length}</span></div><div className="catalog-card-grid">{metrics.map(metric => <MetricCard key={metric.key} metric={metric} />)}</div></section>}
    {kind !== 'metrics' && dimensions.length > 0 && <section className="catalog-section"><div className="catalog-heading"><div><span className="catalog-symbol purple"><Layers3 size={17} /></span><div><h2>Dimensions</h2><p>Ways to group and filter results</p></div></div><span>{dimensions.length}</span></div><div className="catalog-card-grid">{dimensions.map(dimension => <DimensionCard key={dimension.key} dimension={dimension} />)}</div></section>}
    {!!catalog.source_tables?.length && <div className="catalog-sources"><Database size={16} /> Approved sources: {catalog.source_tables.join(' · ')}</div>}
  </div>
}

function MetricCard({ metric }: { metric: Metric }) {
  return <article className="catalog-card"><div><span className="catalog-type">METRIC</span>{metric.unit && <span className="metric-unit">{metric.unit === 'usd_cents' ? 'USD' : toTitle(metric.unit)}</span>}</div><h3>{metric.name}</h3><p>{metric.definition}</p><code>{metric.key}</code>{metric.source && <small>Source: {metric.source}</small>}</article>
}

function DimensionCard({ dimension }: { dimension: Dimension }) {
  return <article className="catalog-card"><div><span className="catalog-type dimension-type">DIMENSION</span>{dimension.type && <span className="metric-unit">{toTitle(dimension.type)}</span>}</div><h3>{dimension.name}</h3><p>{dimension.definition || 'Available for grouping and filtering in analytical questions.'}</p><code>{dimension.key}</code>{!!dimension.values?.length && <small>Examples: {dimension.values.slice(0, 4).join(', ')}</small>}</article>
}
