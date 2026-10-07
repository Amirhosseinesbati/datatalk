import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { BookmarkPlus, Check, ChevronDown, Copy, Database, FileCode2, Info, LoaderCircle, RotateCcw, ShieldCheck, Sparkles, XCircle } from 'lucide-react'
import type { Analysis, Catalog } from '../../api/client'
import { api, formatError } from '../../api/client'
import { formatDate, Modal, Notice, primaryMetric, toTitle } from '../../ui'
import { ResultVisual } from './ResultVisual'
import { resultProvenance } from '../../workspace'

function humanValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.map(humanValue).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function detail(error: Analysis['error']): string {
  if (typeof error === 'string') return error
  return error?.detail || error?.message || 'The analysis could not be completed.'
}

function Evidence({ analysis, catalog }: { analysis: Analysis; catalog?: Catalog }) {
  const [copied, setCopied] = useState(false)
  const provenance = resultProvenance(analysis)
  const [copyError, setCopyError] = useState('')
  const planEntries = analysis.plan ? Object.entries(analysis.plan).filter(([, value]) => value !== undefined && value !== null && value !== '') : []
  const evidence = analysis.evidence && typeof analysis.evidence === 'object' && !Array.isArray(analysis.evidence) ? analysis.evidence as Record<string, unknown> : null
  const evidenceSources = Array.isArray(evidence?.source_tables) ? evidence.source_tables.filter((item): item is string => typeof item === 'string') : []
  const sources = analysis.source_tables?.length ? analysis.source_tables : evidenceSources
  async function copySql() {
    if (!analysis.sql) return
    try { await navigator.clipboard.writeText(analysis.sql); setCopied(true); setTimeout(() => setCopied(false), 1800) }
    catch { setCopyError('Copy is unavailable in this browser. Select the SQL text to copy it.') }
  }
  return <div className="evidence-content">
    {!!analysis.events?.length && <section className="execution-trace"><h4><ShieldCheck size={15} /> Execution record</h4><ol>{analysis.events.map((event, index) => <li key={`${event.stage}-${index}`}><span className="trace-dot" /><strong>{toTitle(event.stage)}</strong><time>{event.at ? formatDate(event.at) : ''}</time></li>)}</ol></section>}
    <div className="evidence-grid">
      <section><h4><ShieldCheck size={15} /> Query scope</h4><dl>
        {planEntries.map(([key, value]) => <div key={key}><dt>{toTitle(key)}</dt><dd>{humanValue(value)}</dd></div>)}
        {!planEntries.length && <div><dt>Plan</dt><dd>Plan details were not returned.</dd></div>}
      </dl></section>
      <section><h4><Database size={15} /> Provenance</h4><dl>
        <div><dt>Dataset reference date</dt><dd>{provenance.referenceDate || 'Not retained for this result'}</dd></div>
        <div><dt>Snapshot created</dt><dd>{provenance.createdAt ? formatDate(provenance.createdAt) : 'Not retained for this result'}</dd></div>
        {catalog?.freshness?.reference_date && <div><dt>Current catalog reference</dt><dd>{catalog.freshness.reference_date} (may differ from this result)</dd></div>}
        <div><dt>Rows</dt><dd>{analysis.result?.row_count ?? '—'}{analysis.result?.truncated ? ' · capped' : ''}</dd></div>
        <div><dt>Snapshot</dt><dd className="hash-value">{analysis.snapshot?.hash || analysis.snapshot_hash || 'See saved report'}</dd></div>
        <div><dt>Sources used</dt><dd>{sources.length ? sources.join(', ') : 'See query below'}</dd></div>
        {analysis.model_version && <div><dt>Model version</dt><dd>{analysis.model_version}</dd></div>}
        {analysis.prompt_version && <div><dt>Prompt version</dt><dd>{analysis.prompt_version}</dd></div>}
      </dl></section>
    </div>
    {analysis.evidence != null && <section className="evidence-raw"><h4><Info size={15} /> Computed evidence</h4><pre>{typeof analysis.evidence === 'string' ? analysis.evidence : JSON.stringify(analysis.evidence, null, 2)}</pre></section>}
    <section className="sql-section"><div className="sql-heading"><h4><FileCode2 size={15} /> Validated SQL</h4>{analysis.sql && <button className="text-button" onClick={copySql}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? 'Copied' : 'Copy SQL'}</button>}</div>
      {analysis.sql ? <pre><code>{analysis.sql}</code></pre> : <p>SQL was not returned for this analysis.</p>}
      {copyError && <p className="field-error">{copyError}</p>}
    </section>
  </div>
}

export function AnalysisBlock({ analysis, catalog, onClarify, onRetry, onSaved, canSave }: { analysis: Analysis; catalog?: Catalog; onClarify: (question: string) => void; onRetry: (question: string) => void; onSaved: () => void; canSave: boolean }) {
  const [saveOpen, setSaveOpen] = useState(false)
  const [title, setTitle] = useState(analysis.question.slice(0, 90))
  const [streamStage, setStreamStage] = useState('')
  const isTerminal = (status?: string) => ['completed', 'clarification', 'failed', 'cancelled'].includes(status || '')
  const live = useQuery({ queryKey: ['analysis', analysis.id], queryFn: () => api.analysis(analysis.id), enabled: !isTerminal(analysis.status), initialData: analysis, refetchInterval: query => isTerminal(query.state.data?.status) ? false : 1500 })
  const current = live.data || analysis
  const pending = !isTerminal(current.status)
  const cancel = useMutation({ mutationFn: () => api.cancelAnalysis(analysis.id), onSuccess: () => live.refetch() })
  const save = useMutation({ mutationFn: () => api.saveReport(current.id, title.trim()), onSuccess: () => { setSaveOpen(false); onSaved() } })
  const clarification = typeof current.clarification === 'string' ? current.clarification : current.clarification?.question
  const options = typeof current.clarification === 'object' ? current.clarification?.options : undefined

  useEffect(() => {
    if (isTerminal(analysis.status)) return
    const source = new EventSource(`${api.base}/analyses/${encodeURIComponent(analysis.id)}/events`, { withCredentials: true })
    const onStage = (event: Event) => {
      try { const payload = JSON.parse((event as MessageEvent).data) as { stage?: string }; if (payload.stage) setStreamStage(payload.stage) }
      catch { /* GET polling remains authoritative if an event is malformed. */ }
      live.refetch()
    }
    const onDone = () => { live.refetch(); source.close() }
    source.addEventListener('stage', onStage)
    source.addEventListener('done', onDone)
    source.onerror = () => source.close()
    return () => source.close()
  }, [analysis.id, analysis.status])

  return <article className="analysis-block">
    <div className="block-topline"><span className="block-index"><Sparkles size={14} /> Analysis</span><span>{formatDate(current.created_at)}</span></div>
    <h2>{current.question}</h2>
    {pending && <div className="job-progress" role="status"><div className="job-progress-head"><LoaderCircle size={18} className="spin" /><div><strong>{toTitle(streamStage || current.stage || current.status)}</strong><span>Server workflow is still running. This record will update automatically.</span></div></div>{!!current.events?.length && <ol>{current.events.map((event, index) => <li key={`${event.stage}-${index}`}>{toTitle(event.stage)}</li>)}</ol>}<div className="job-progress-foot"><span>Analysis ID: {current.id}</span><button className="text-button" onClick={() => cancel.mutate()} disabled={cancel.isPending || current.status === 'cancelling'}><XCircle size={14} /> {current.status === 'cancelling' ? 'Cancelling…' : 'Cancel run'}</button></div>{cancel.isError && <Notice tone="error">{formatError(cancel.error)}</Notice>}{live.isError && <Notice tone="error">Live status is unavailable: {formatError(live.error)} Retry by reopening this notebook.</Notice>}</div>}
    {current.status === 'cancelled' && <div className="block-error"><Notice title="Analysis cancelled">The run stopped before producing a result.</Notice><button className="secondary-button" onClick={() => onRetry(current.question)}><RotateCcw size={15} /> Run again</button></div>}
    {current.status === 'clarification' && <div className="clarification"><span className="mini-eyebrow">One detail to confirm</span><p>{clarification || 'Please narrow the scope before the query runs.'}</p>{options && options.length > 0 && <div className="clarification-options">{options.map(option => <button key={option} onClick={() => onClarify(option)}>{option}</button>)}</div>}</div>}
    {current.status === 'failed' && <div className="block-error"><Notice tone="error" title="Analysis stopped">{detail(current.error)}</Notice><button className="secondary-button" onClick={() => onRetry(current.question)}><RotateCcw size={15} /> Retry this question</button></div>}
    {current.status === 'completed' && <>
      <div className="answer"><div className="answer-label">Answer</div><p>{current.narrative || 'The validated query completed. Inspect the result and evidence below.'}</p></div>
      {current.result && <ResultVisual result={current.result} chart={current.chart} sql={current.sql} metric={primaryMetric(current.plan)} />}
      <div className="block-actions"><button className="primary-button save-button" data-modal-return onClick={event => { event.currentTarget.focus(); setSaveOpen(true) }} disabled={!canSave} title={!canSave ? 'Your role cannot save reports' : undefined}><BookmarkPlus size={16} /> Save report</button><span className="result-meta"><ShieldCheck size={15} /> Validated query {current.result ? current.result.truncated ? '· result capped' : '· result complete' : '· result unavailable'}</span></div>
      {save.isSuccess && <Notice tone="success">Report saved. Open Reports to revisit or export it.</Notice>}
      <details className="evidence-details"><summary><span><FileCode2 size={17} /> Assumptions, evidence & SQL</span><ChevronDown size={17} className="details-chevron" /></summary><Evidence analysis={current} catalog={catalog} /></details>
    </>}
    {saveOpen && <Modal title="Save reproducible report" onClose={() => setSaveOpen(false)}><form onSubmit={event => { event.preventDefault(); if (title.trim()) save.mutate() }}>
      <p className="modal-copy">The report stores this question, analytical plan, validated SQL, result, chart, and dataset snapshot.</p>
      <label className="field-label" htmlFor={`report-title-${analysis.id}`}>Report title</label><input id={`report-title-${analysis.id}`} value={title} maxLength={120} onChange={event => setTitle(event.target.value)} required data-autofocus />
      {save.isError && <Notice tone="error">{formatError(save.error)}</Notice>}
      <div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setSaveOpen(false)}>Cancel</button><button type="submit" className="primary-button" disabled={save.isPending || !title.trim()}>{save.isPending ? 'Saving…' : 'Save report'}</button></div>
    </form></Modal>}
  </article>
}
