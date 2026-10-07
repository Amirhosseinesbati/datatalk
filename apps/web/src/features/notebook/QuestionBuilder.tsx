import { useState } from 'react'
import { ArrowUpRight, SlidersHorizontal } from 'lucide-react'
import type { Catalog } from '../../api/client'
import { buildQuestion, guidedGroups, guidedMetrics, guidedPeriods } from '../../workspace'

export function QuestionBuilder({ catalog, onUse, disabled }: { catalog?: Catalog; onUse: (text: string) => void; disabled: boolean }) {
  const [metric, setMetric] = useState('net_revenue')
  const [group, setGroup] = useState('channel')
  const [period, setPeriod] = useState('last_month')
  const [compare, setCompare] = useState(false)
  const metrics = catalog?.metrics.filter(item => guidedMetrics[item.key]) || []
  const groups = catalog?.dimensions.filter(item => guidedGroups[item.key]) || []
  const selectedMetric = metrics.find(item => item.key === metric) || metrics[0]
  const selectedGroup = group && !groups.some(item => item.key === group) ? '' : group
  const question = buildQuestion(selectedMetric?.key || '', selectedGroup, period, compare)

  return <details className="question-builder">
    <summary><SlidersHorizontal size={17} /><span>Build a question step by step</span><small>No SQL needed</small></summary>
    <div className="builder-content">
      <p>Choose a measure and scope. Review the generated question before running it.</p>
      {!metrics.length ? <p role="status">Load the metric catalog to use the guided builder. You can still write a question below.</p> : <>
        <div className="builder-fields">
          <label>Measure<select value={selectedMetric?.key} onChange={event => setMetric(event.target.value)} disabled={disabled}>{metrics.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</select></label>
          <label>Group by<select value={selectedGroup} onChange={event => setGroup(event.target.value)} disabled={disabled}><option value="">Overall total</option>{groups.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</select></label>
          <label>Period<select value={period} onChange={event => setPeriod(event.target.value)} disabled={disabled}>{Object.entries(guidedPeriods).map(([key, label]) => <option key={key} value={key}>{label.charAt(0).toUpperCase() + label.slice(1)}</option>)}</select></label>
        </div>
        <p className="builder-definition">{selectedMetric?.definition}</p>
        <label className="builder-compare"><input type="checkbox" checked={compare} onChange={event => setCompare(event.target.checked)} disabled={disabled} /> Compare with the previous period</label>
        <div className="builder-preview"><p>{question}</p><button className="secondary-button" onClick={() => onUse(question)} disabled={disabled || !question}>Use this question <ArrowUpRight size={16} /></button></div>
      </>}
      <small>Dates use the dataset reference date and UTC calendar periods. The result shows the exact resolved scope.</small>
    </div>
  </details>
}
