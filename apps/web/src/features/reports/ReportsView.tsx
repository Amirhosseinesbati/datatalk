import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownToLine, ArrowRight, BookMarked, CalendarDays, GitCompareArrows, Printer, RefreshCw, ShieldCheck } from 'lucide-react'
import type { Report, ReportVersion, Session } from '../../api/client'
import { api, formatError } from '../../api/client'
import { EmptyState, formatDate, Loading, Notice, primaryMetric, toTitle } from '../../ui'
import { ResultTable, ResultVisual } from '../analysis/ResultVisual'

function versionNumbers(report?: Report): number[] {
  const found = (report?.versions || []).map(item => item.version).filter(value => Number.isInteger(value))
  const latest = report?.current_version || report?.version || report?.latest_version?.version
  if (latest && !found.includes(latest)) found.push(latest)
  return found.sort((a, b) => b - a)
}

function versionFromReport(report?: Report, version?: number): ReportVersion | undefined {
  if (!report) return undefined
  return report.latest_version?.version === version ? report.latest_version : undefined
}

function ReportContent({ version, label, compact = false }: { version: ReportVersion; label?: string; compact?: boolean }) {
  const analysis = version.analysis || version
  const plan = analysis.plan || version.plan
  return <div className={`report-content ${compact ? 'report-content-compact' : ''}`}>
    {label && <span className="mini-eyebrow">{label}</span>}
    <div className="report-facts"><span>Version {version.version}</span><span>{formatDate(version.version_created_at || version.created_at)}</span><span className="hash-value">Snapshot: {version.snapshot_hash || (typeof version.snapshot === 'string' ? version.snapshot : version.snapshot?.hash) || 'Unspecified'}</span>{(analysis.model_version || version.model_version) && <span>Model: {analysis.model_version || version.model_version}</span>}{(analysis.prompt_version || version.prompt_version) && <span>Prompt: {analysis.prompt_version || version.prompt_version}</span>}</div>
    <h3>{analysis.question || version.question || 'Saved analysis'}</h3>
    {analysis.narrative && <div className="saved-answer"><span>ANSWER</span><p>{analysis.narrative}</p></div>}
    {(analysis.result || version.result) && (compact ? <ResultTable result={(analysis.result || version.result)!} metric={primaryMetric(plan)} /> : <ResultVisual result={(analysis.result || version.result)!} chart={analysis.chart || version.chart} sql={analysis.sql || version.sql} metric={primaryMetric(plan)} />)}
    <details className="evidence-details report-evidence"><summary>Plan & validated SQL</summary><div className="evidence-content">
      {plan && <dl className="report-plan">{Object.entries(plan).map(([key, value]) => <div key={key}><dt>{toTitle(key)}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>}
      <pre className="saved-sql"><code>{analysis.sql || version.sql || 'SQL was not retained for this version.'}</code></pre>
    </div></details>
  </div>
}

export function ReportsView({ session }: { session: Session }) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [versionNumber, setVersionNumber] = useState<number | null>(null)
  const [compare, setCompare] = useState(false)
  const [compareNumber, setCompareNumber] = useState<number | null>(null)
  const [refreshJobId, setRefreshJobId] = useState<string | null>(null)
  const [refreshOutcome, setRefreshOutcome] = useState<'completed' | 'failed' | 'cancelled' | 'timeout' | null>(null)
  const [expectedVersion, setExpectedVersion] = useState<number | null>(null)
  const [versionWaitStartedAt, setVersionWaitStartedAt] = useState<number | null>(null)
  const reports = useQuery({ queryKey: ['reports'], queryFn: api.reports })
  const report = useQuery({ queryKey: ['report', selectedId], queryFn: () => api.report(selectedId!), enabled: !!selectedId, refetchInterval: query => versionWaitStartedAt && expectedVersion && (query.state.data?.current_version || 0) < expectedVersion ? 1000 : false })
  const allVersions = versionNumbers(report.data)
  const selectedVersion = versionNumber || allVersions[0]
  const otherVersion = compareNumber || allVersions.find(item => item !== selectedVersion)
  const version = useQuery({ queryKey: ['report-version', selectedId, selectedVersion], queryFn: () => api.reportVersion(selectedId!, selectedVersion!), enabled: !!selectedId && !!selectedVersion })
  const compareVersion = useQuery({ queryKey: ['report-version', selectedId, otherVersion], queryFn: () => api.reportVersion(selectedId!, otherVersion!), enabled: !!selectedId && !!otherVersion && compare })
  const refresh = useMutation({ mutationFn: () => api.refreshReport(selectedId!), onSuccess: job => { setRefreshOutcome(null); setExpectedVersion(job.current_version + 1); setRefreshJobId(job.analysis_id) } })
  const refreshStatus = useQuery({ queryKey: ['analysis', refreshJobId], queryFn: () => api.analysis(refreshJobId!), enabled: !!refreshJobId, refetchInterval: query => ['completed', 'failed', 'cancelled'].includes(query.state.data?.status || '') ? false : 1500 })

  useEffect(() => { if (!selectedId && reports.data?.items?.length) setSelectedId(reports.data.items[0].id) }, [reports.data, selectedId])
  useEffect(() => {
    if (!refreshJobId || !refreshStatus.data) return
    const status = refreshStatus.data.status
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      setRefreshJobId(null)
      if (status === 'completed') {
        setVersionWaitStartedAt(Date.now())
        queryClient.invalidateQueries({ queryKey: ['reports'] })
        queryClient.invalidateQueries({ queryKey: ['report', selectedId] })
      } else { setExpectedVersion(null); setRefreshOutcome(status) }
    }
  }, [refreshJobId, refreshStatus.data, queryClient, selectedId])
  useEffect(() => {
    if (expectedVersion && versionWaitStartedAt && (report.data?.current_version || 0) >= expectedVersion) {
      setVersionNumber(null)
      setExpectedVersion(null)
      setVersionWaitStartedAt(null)
      setRefreshOutcome('completed')
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    }
  }, [expectedVersion, versionWaitStartedAt, report.data?.current_version, queryClient])
  useEffect(() => {
    if (!versionWaitStartedAt) return
    const timeout = window.setTimeout(() => { setExpectedVersion(null); setVersionWaitStartedAt(null); setRefreshOutcome('timeout') }, 30_000)
    return () => window.clearTimeout(timeout)
  }, [versionWaitStartedAt])
  const primary = version.data || versionFromReport(report.data, selectedVersion)
  const secondary = compareVersion.data || versionFromReport(report.data, otherVersion)
  const canRefresh = session.user.role !== 'viewer'

  return <div className="reports-layout">
    <aside className="reports-list" aria-label="Saved reports"><div className="reports-list-head"><span className="mini-eyebrow">REPORT LIBRARY</span><strong>{reports.data?.items?.length ?? 0} saved</strong></div>
      {reports.isPending && <Loading compact label="Loading reports…" />}
      {reports.isError && <p className="aside-error">{formatError(reports.error)}</p>}
      {reports.data?.items?.map(item => <button key={item.id} className={`report-list-item ${selectedId === item.id ? 'active' : ''}`} onClick={() => { setSelectedId(item.id); setVersionNumber(null); setCompare(false); setRefreshJobId(null); setExpectedVersion(null); setVersionWaitStartedAt(null); setRefreshOutcome(null) }}><span className="report-list-icon"><BookMarked size={17} /></span><span><strong>{item.title}</strong><small>{formatDate(item.updated_at || item.created_at)}</small></span><ArrowRight size={15} /></button>)}
    </aside>
    <main className="reports-main"><header className="section-intro"><div className="eyebrow"><span className="eyebrow-mark" /> REPRODUCIBLE REPORTS</div><h1>Saved answers,<br /><em>clear lineage.</em></h1><p>Each refresh creates a new version. Open any prior result to inspect its original snapshot and query.</p></header>
      {!selectedId && !reports.isPending && <EmptyState icon={<BookMarked size={24} />} title="No reports yet">Run an analysis and choose “Save report” to keep its answer, chart, SQL and snapshot together.</EmptyState>}
      {report.isPending && selectedId && <Loading label="Opening report…" />}
      {report.isError && <Notice tone="error" title="Could not open report">{formatError(report.error)}</Notice>}
      {report.data && <div className="report-detail"><div className="report-detail-top"><div><span className="mini-eyebrow">SAVED REPORT</span><h2>{report.data.title}</h2><p><CalendarDays size={14} /> Created {formatDate(report.data.created_at)}</p></div><div className="report-actions"><a className="secondary-button" href={api.csvUrl(report.data.id)} download><ArrowDownToLine size={15} /> CSV</a><a className="secondary-button" href={api.printUrl(report.data.id)} target="_blank" rel="noopener noreferrer"><Printer size={15} /> Print</a><button className="secondary-button" onClick={() => refresh.mutate()} disabled={!canRefresh || refresh.isPending || !!refreshJobId || !!expectedVersion} title={!canRefresh ? 'Your role cannot refresh reports' : undefined}><RefreshCw size={15} className={refresh.isPending || refreshJobId || expectedVersion ? 'spin' : ''} /> {refreshJobId || expectedVersion ? 'Refreshing…' : 'Refresh'}</button></div></div>
        {refresh.isError && <Notice tone="error" title="Refresh failed">{formatError(refresh.error)}</Notice>}
        {refreshJobId && <Notice title="Refresh in progress">The server is running a new validated analysis{refreshStatus.data?.stage ? ` · ${toTitle(refreshStatus.data.stage)}` : ''}. A new version will appear when it completes.</Notice>}
        {versionWaitStartedAt && <Notice title="Finalizing report version">The analysis completed. Waiting for the new saved version to become available.</Notice>}
        {refreshStatus.isError && refreshJobId && <Notice tone="error">Live refresh status is unavailable: {formatError(refreshStatus.error)}</Notice>}
        {refreshOutcome === 'completed' && <Notice tone="success">A new report version was created. Prior versions remain available.</Notice>}
        {(refreshOutcome === 'failed' || refreshOutcome === 'cancelled' || refreshOutcome === 'timeout') && <Notice tone="error">Refresh {refreshOutcome === 'timeout' ? 'did not produce a visible version within 30 seconds' : refreshOutcome}. The prior report version remains available. Retry or reopen this report.</Notice>}
        <div className="version-toolbar"><div><label htmlFor="report-version">Viewing version</label><select id="report-version" value={selectedVersion || ''} onChange={event => setVersionNumber(Number(event.target.value))}>{allVersions.map(number => <option key={number} value={number}>Version {number}{number === allVersions[0] ? ' · latest' : ''}</option>)}</select></div><button className={`compare-toggle ${compare ? 'active' : ''}`} onClick={() => setCompare(value => !value)} disabled={allVersions.length < 2}><GitCompareArrows size={17} /> Compare versions</button></div>
        {allVersions.length < 2 && <div className="version-note"><ShieldCheck size={15} /> Refresh this report to create another version for comparison.</div>}
        {version.isError && !primary && <Notice tone="error" title="Version unavailable">{formatError(version.error)} The original snapshot may no longer be retained.</Notice>}
        {version.isPending && !primary && <Loading label="Loading saved version…" />}
        {!compare && primary && <ReportContent version={primary} />}
        {compare && <><div className="compare-picker"><span>Compare with</span><select aria-label="Comparison version" value={otherVersion || ''} onChange={event => setCompareNumber(Number(event.target.value))}>{allVersions.filter(number => number !== selectedVersion).map(number => <option key={number} value={number}>Version {number}</option>)}</select></div><div className="comparison-grid">{primary && <ReportContent version={primary} compact label="SELECTED VERSION" />}{secondary ? <ReportContent version={secondary} compact label="COMPARISON VERSION" /> : <div>{compareVersion.isPending ? <Loading label="Loading comparison…" /> : compareVersion.isError ? <Notice tone="error">{formatError(compareVersion.error)}</Notice> : null}</div>}</div></>}
      </div>}
    </main>
  </div>
}
