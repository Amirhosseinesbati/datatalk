import { useMemo, useState } from 'react'
import type { AnalysisResult, ChartSpec, ResultCell } from '../../api/client'
import { formatCell, isMoneyColumn, resultColumnTitle } from '../../ui'
import { EmptyState } from '../../ui'
import { Search } from 'lucide-react'
import { chartNumber } from './chartData'

const COLORS = Array.from({ length: 6 }, (_, index) => `var(--chart-${index + 1})`)
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

type Point = { label: string; value: number; series?: string }

function selectFields(result: AnalysisResult, chart?: ChartSpec) {
  const rows = result.rows || []
  const columns = result.columns?.length ? result.columns : Object.keys(rows[0] || {})
  const numeric = columns.find(column => rows.some(row => typeof row[column] === 'number'))
  const x = chart?.x && columns.includes(chart.x) ? chart.x : columns.find(column => column !== numeric) || columns[0]
  const y = chart?.y && columns.includes(chart.y) ? chart.y : numeric
  return { columns, x, y }
}

function getPoints(result: AnalysisResult, chart?: ChartSpec): Point[] {
  const { x, y } = selectFields(result, chart)
  if (!x || !y) return []
  return result.rows.slice(0, 18).flatMap(row => {
    const raw = row[y]
    const value = chartNumber(raw)
    if (value === undefined) return []
    return [{ label: formatCell(row[x]), value, series: chart?.series ? formatCell(row[chart.series]) : undefined }]
  })
}

export function ResultVisual({ result, chart, sql, metric }: { result: AnalysisResult; chart?: ChartSpec; sql?: string; metric?: string }) {
  const [view, setView] = useState<'chart' | 'table' | 'query'>('chart')
  const points = useMemo(() => getPoints(result, chart), [result, chart])
  const { columns, x, y } = selectFields(result, chart)
  const hasChart = !!points.length && (!chart?.type || ['bar', 'line'].includes(chart.type)) && !chart?.series
  const shownView = view === 'query' && sql ? 'query' : hasChart ? view : 'table'
  return <section className="result-surface" aria-label="Analysis result">
    <div className="result-toolbar">
      <div><h3>{chart?.title || 'Result'}</h3><span>{result.row_count ?? result.rows.length} row{(result.row_count ?? result.rows.length) === 1 ? '' : 's'} returned{result.truncated ? ' · truncated' : ''}</span></div>
      {(hasChart || sql) && <div className="segmented" role="group" aria-label="Result view">
        {hasChart && <button className={shownView === 'chart' ? 'selected' : ''} aria-pressed={shownView === 'chart'} onClick={() => setView('chart')}>Chart</button>}
        <button className={shownView === 'table' ? 'selected' : ''} aria-pressed={shownView === 'table'} onClick={() => setView('table')}>Table</button>
        {sql && <button className={shownView === 'query' ? 'selected' : ''} aria-pressed={shownView === 'query'} onClick={() => setView('query')}>Query</button>}
      </div>}
    </div>
    {shownView === 'query' ? <pre className="result-query"><code>{sql}</code></pre> : !result.rows.length ? <EmptyState icon={<Search size={22} />} title="No data in this scope">The query completed with no matching rows. Try a different period or broader grouping. Inspect Query to check the scope.</EmptyState> : shownView === 'chart' && x && y ? <div className="chart-panel"><Chart points={points} totalRows={result.rows.length} type={chart?.type === 'line' ? 'line' : 'bar'} x={x} y={y} metric={metric} /></div> : <ResultTable result={result} columns={columns} metric={metric} />}
    {!!chart?.series && <p className="result-warning">Multiple series are shown in the table to preserve each exact value.</p>}
    {hasChart && shownView === 'chart' && <details className="accessible-table"><summary>Show data table for this chart</summary><ResultTable result={result} columns={columns} metric={metric} /></details>}
    {result.truncated && <p className="result-warning">The server capped this result. Refine your question for a complete view.</p>}
  </section>
}

function Chart({ points, totalRows, type, x, y, metric }: { points: Point[]; totalRows: number; type: 'bar' | 'line'; x: string; y: string; metric?: string }) {
  const [activePoint, setActivePoint] = useState<number | null>(null)
  const width = 800
  const height = 316
  const left = 67
  const right = 24
  const top = 20
  const bottom = 64
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const values = points.map(point => point.value)
  const min = Math.min(0, ...values)
  const max = Math.max(0, ...values)
  const span = max - min || 1
  const yAt = (value: number) => top + (max - value) / span * plotHeight
  const zeroY = yAt(0)
  const step = plotWidth / Math.max(points.length, 1)
  const formatLabel = (label: string) => label.length > 13 ? `${label.slice(0, 11)}…` : label
  const linePath = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${left + step * (index + .5)} ${yAt(point.value)}`).join(' ')
  const tickValues = Array.from({ length: 5 }, (_, index) => min + span * (index / 4))
  const axisValue = (value: number) => isMoneyColumn(y, metric) ? `${value < 0 ? '-' : ''}$${compact.format(Math.abs(value) / 100)}` : compact.format(value)
  const yLabel = `${resultColumnTitle(y)}${isMoneyColumn(y, metric) ? ' (USD)' : ''}`

  return <div className="chart-scroll">
    <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`${type === 'line' ? 'Line' : 'Bar'} chart of ${yLabel} by ${resultColumnTitle(x)}. Focus a point for its value, or use the data table below.`}>
      {tickValues.map((tick, index) => <g key={index}>
        <line x1={left} x2={width - right} y1={yAt(tick)} y2={yAt(tick)} stroke="var(--chart-grid)" strokeDasharray={tick === 0 ? undefined : '4 5'} />
        <text x={left - 12} y={yAt(tick) + 4} textAnchor="end" className="chart-axis">{axisValue(tick)}</text>
      </g>)}
      {type === 'line' && <path d={linePath} fill="none" stroke={COLORS[0]} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />}
      {points.map((point, index) => {
        const center = left + step * (index + .5)
        const upper = Math.min(yAt(point.value), zeroY)
        const barHeight = Math.max(Math.abs(zeroY - yAt(point.value)), 2)
        return <g key={`${point.label}-${index}`} className="chart-point" tabIndex={0} role="img" aria-label={`${point.label}: ${formatCell(point.value, y, metric)}`} onFocus={() => setActivePoint(index)} onBlur={() => setActivePoint(null)} onMouseEnter={() => setActivePoint(index)} onMouseLeave={() => setActivePoint(null)} onKeyDown={event => { if (event.key === 'Escape') setActivePoint(null) }}>
          {type === 'bar' ? <rect x={center - Math.min(step * .29, 24)} y={upper} width={Math.min(step * .58, 48)} height={barHeight} rx="4" fill={COLORS[index % COLORS.length]} /> : <circle cx={center} cy={yAt(point.value)} r="5" fill={COLORS[0]} stroke="var(--panel-soft)" strokeWidth="2" />}
          <title>{point.label}: {formatCell(point.value, y, metric)}{point.series ? ` · ${point.series}` : ''}</title>
          <text x={center} y={height - 34} textAnchor="end" transform={`rotate(-28 ${center} ${height - 34})`} className="chart-axis chart-x-label">{formatLabel(point.label)}</text>
        </g>
      })}
    </svg>
    {activePoint !== null && points[activePoint] && <div className="chart-tooltip" role="status"><span>{points[activePoint].label}</span><strong>{formatCell(points[activePoint].value, y, metric)}</strong></div>}
    <p className="chart-caption">{yLabel} by {resultColumnTitle(x)} · Plotting {points.length} of {totalRows} returned rows (up to 18). Missing values are omitted. Use the table for exact values.</p>
  </div>
}

export function ResultTable({ result, columns: providedColumns, metric }: { result: AnalysisResult; columns?: string[]; metric?: string }) {
  const [page, setPage] = useState(0)
  const columns = providedColumns?.length ? providedColumns : result.columns?.length ? result.columns : Object.keys(result.rows?.[0] || {})
  const pageSize = 20
  const pages = Math.max(1, Math.ceil(result.rows.length / pageSize))
  const effectivePage = Math.min(page, pages - 1)
  return <div className="table-area">
    <div className="table-scroll"><table><thead><tr>{columns.map(column => <th scope="col" key={column}>{resultColumnTitle(column)}{isMoneyColumn(column, metric) ? ' (USD)' : ''}</th>)}</tr></thead>
      <tbody>{result.rows.slice(effectivePage * pageSize, (effectivePage + 1) * pageSize).map((row, rowIndex) => <tr key={rowIndex}>{columns.map(column => <td key={column} className={typeof row[column] === 'number' ? 'numeric' : ''}>{formatCell(row[column] as ResultCell, column, metric)}</td>)}</tr>)}</tbody>
    </table></div>
    {!result.rows.length && <p className="table-empty">No rows matched the selected scope.</p>}
    {pages > 1 && <div className="pagination"><span>Rows {effectivePage * pageSize + 1}–{Math.min((effectivePage + 1) * pageSize, result.rows.length)} of {result.rows.length}</span><div><button disabled={effectivePage === 0} onClick={() => setPage(value => Math.max(0, value - 1))}>Previous</button><button disabled={effectivePage >= pages - 1} onClick={() => setPage(value => Math.min(pages - 1, value + 1))}>Next</button></div></div>}
  </div>
}
