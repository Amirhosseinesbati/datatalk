import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BookOpen, ChartNoAxesCombined, CirclePlus, Clock3, Database, History, Layers3, LoaderCircle, Send, ShieldCheck, Terminal } from 'lucide-react'
import type { Analysis, Catalog, Conversation, Session } from '../../api/client'
import { api, formatError } from '../../api/client'
import { AnalysisBlock } from '../analysis/AnalysisBlock'
import { Loading, Notice } from '../../ui'
import { workspace } from '../../config'
import { datasetLabel } from '../../workspace'
import { QuestionBuilder } from './QuestionBuilder'
import { ContextPanel } from './ContextPanel'

const promptIcons = { compare: ChartNoAxesCombined, mix: Layers3, trend: Clock3 }

export function Notebook({ catalog, session, onOpenGlossary, onSaved }: { catalog?: Catalog; session: Session; onOpenGlossary: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [freshPage, setFreshPage] = useState(false)
  const [question, setQuestion] = useState('')
  const [historyLimit, setHistoryLimit] = useState(8)
  const [localAnalyses, setLocalAnalyses] = useState<Analysis[]>([])
  const [requestError, setRequestError] = useState('')
  const [lastQuestion, setLastQuestion] = useState('')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const historyDrawer = useRef<HTMLDetailsElement>(null)
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: api.conversations })
  const conversation = useQuery({ queryKey: ['conversation', selectedId], queryFn: () => api.conversation(selectedId!), enabled: !!selectedId })

  useEffect(() => {
    if (!selectedId && !freshPage && !question && conversations.data?.items?.length) setSelectedId(conversations.data.items[0].id)
  }, [conversations.data, selectedId, freshPage, question])

  const analyze = useMutation({
    mutationFn: async (text: string) => {
      let conversationId = selectedId
      if (!conversationId) {
        const created = await api.createConversation()
        conversationId = created.id
        setSelectedId(conversationId)
        setFreshPage(false)
      }
      return api.analyze(conversationId, text)
    },
    onSuccess: analysis => {
      setLocalAnalyses(current => [...current.filter(item => item.id !== analysis.id), analysis])
      setRequestError('')
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation', analysis.conversation_id || selectedId] })
    },
    onError: (error, attemptedQuestion) => { setRequestError(formatError(error)); setQuestion(current => current || attemptedQuestion) },
  })

  function submit(text = question) {
    const value = text.trim()
    if (!value || analyze.isPending) return
    setQuestion('')
    setRequestError('')
    setLastQuestion(value)
    analyze.mutate(value)
  }

  function newPage() {
    if (analyze.isPending) return
    setSelectedId(null)
    setFreshPage(true)
    setLocalAnalyses([])
    setQuestion('')
    setRequestError('')
    textarea.current?.focus()
  }

  function chooseConversation(id: string) {
    if (analyze.isPending) return
    setSelectedId(id)
    setFreshPage(false)
    setLocalAnalyses([])
    setQuestion('')
    setRequestError('')
    if (historyDrawer.current) historyDrawer.current.open = false
    textarea.current?.focus()
  }

  function usePrompt(text: string) {
    setQuestion(text)
    textarea.current?.focus()
  }

  const history = conversation.data?.analyses || []
  const historyItems = conversations.data?.items || []
  const analyses = [...history, ...localAnalyses.filter(local => (!local.conversation_id || local.conversation_id === selectedId) && !history.some(saved => saved.id === local.id))]
  const noAnalyses = analyses.length === 0
  const canRun = session.user.role !== 'viewer'

  return <div className="notebook-grid workbench-grid">
    <main className="notebook-main" id="workspace-content" tabIndex={-1}>
      <header className="workbench-heading">
        <div><span className="workbench-symbol"><Terminal size={20} /></span><span><h1>Query workbench</h1><p>{workspace.workspaceName} <span className="heading-divider">/</span> Sales analytics</p></span></div>
        <span className="read-only-badge"><ShieldCheck size={13} /> Read-only</span>
      </header>
      <div className="scope-ribbon" aria-label="Data context"><span><Database size={13} />{datasetLabel(catalog?.synthetic, catalog?.dataset_kind)}</span><span><Clock3 size={13} /> Reference {catalog?.freshness?.reference_date || 'unavailable'} · UTC</span><button onClick={onOpenGlossary}><BookOpen size={13} />{catalog ? `${catalog.metrics.length} defined metrics` : 'Catalog unavailable'}</button></div>
      <div className="notebook-tools">
        <button className="new-page-button" onClick={newPage} disabled={analyze.isPending}><CirclePlus size={15} /> New analysis</button>
        <details ref={historyDrawer} className="history-drawer" onKeyDown={event => { if (event.key === 'Escape' && historyDrawer.current?.open) { event.preventDefault(); historyDrawer.current.open = false; historyDrawer.current.querySelector('summary')?.focus() } }}><summary><History size={14} /> Recent questions <span>{historyItems.length}</span></summary>
          {conversations.isPending && <Loading compact label="Loading history." />}
          {conversations.isError && <Notice tone="error">{formatError(conversations.error)} <button className="text-button" onClick={() => conversations.refetch()}>Retry history</button></Notice>}
          <div className="history-list">{historyItems.slice(0, historyLimit).map((item: Conversation) => <button key={item.id} className={`history-item ${selectedId === item.id ? 'active' : ''}`} aria-current={selectedId === item.id ? 'page' : undefined} disabled={analyze.isPending} onClick={() => chooseConversation(item.id)}><span>{item.title || 'Untitled analysis'}</span><ArrowRight size={14} /></button>)}
            {historyItems.length > historyLimit && <button className="text-button" onClick={() => setHistoryLimit(count => count + 8)}>Show older questions</button>}
            {conversations.isSuccess && !historyItems.length && <p className="aside-muted">Your questions will appear here.</p>}
          </div>
        </details>
        <span className="execution-mode">{session.mode.toLowerCase() === 'demo' ? 'Deterministic planner · No model calls' : 'Connected planner'}</span>
      </div>
      <section className="question-composer" aria-label="Ask a sales question" aria-busy={analyze.isPending}>
        <div className="composer-heading"><div><Terminal size={15} /><strong>{noAnalyses ? 'Question editor' : 'Follow-up editor'}</strong></div><span>Natural language → bounded SQL</span></div>
        <form onSubmit={event => { event.preventDefault(); submit() }}>
          <div className="editor-body"><span className="editor-gutter" aria-hidden="true">01</span><label className="sr-only" htmlFor="analysis-question">Your sales question</label><textarea ref={textarea} id="analysis-question" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit() } }} placeholder="Which channel's net revenue changed most last month?" rows={3} maxLength={1000} disabled={!canRun || analyze.isPending} /></div>
          <div className="composer-footer"><span>{!canRun ? 'Viewer role cannot run analyses.' : 'Ctrl / ⌘ + Enter to run · Review the resolved scope in each result'}</span><button className="primary-button" type="submit" disabled={!canRun || !question.trim() || analyze.isPending}>{analyze.isPending ? <><LoaderCircle className="spin" size={15} /> Running…</> : <><Send size={15} /> Run analysis</>}</button></div>
        </form>
      </section>
      <QuestionBuilder catalog={catalog} onUse={usePrompt} disabled={!canRun || analyze.isPending} />
      {noAnalyses && <div className="query-examples"><span>Try a question</span><div className="prompt-grid">{workspace.prompts.map(prompt => { const Icon = promptIcons[prompt.icon]; return <button key={prompt.label} onClick={() => usePrompt(prompt.text)} disabled={!canRun || analyze.isPending} title={prompt.text}><Icon size={14} /><span>{prompt.label}</span><ArrowRight size={12} /></button> })}</div></div>}
      {analyze.isPending && <div className="run-status" role="status"><LoaderCircle className="spin" size={16} /><div><strong>Running the analytical workflow</strong><span>Waiting for the server's validated result. This may take a moment.</span></div></div>}
      {requestError && <Notice tone="error" title="Request failed">{requestError} Your draft is restored. The request outcome is unconfirmed; check history before retrying. <button className="text-button" onClick={() => submit(lastQuestion)} disabled={analyze.isPending || !canRun}>Retry submitted question</button></Notice>}
      {selectedId && conversation.isPending && noAnalyses && <Loading label="Opening notebook." />}
      {conversation.isError && <Notice tone="error" title="Could not open this notebook">{formatError(conversation.error)} <button className="text-button" onClick={() => conversation.refetch()}>Retry notebook</button></Notice>}
      <div className="results-heading"><span><ChartNoAxesCombined size={15} /> Results</span><span>{analyses.length} analysis record{analyses.length === 1 ? '' : 's'}</span></div>
      {noAnalyses && !analyze.isPending && (!selectedId || !conversation.isPending) && !conversation.isError && <section className="workbench-empty"><div className="empty-chart-grid" aria-hidden="true"><ChartNoAxesCombined size={36} /></div><h2>No results in this notebook</h2><p>Run a question to inspect the chart, exact rows and validated query.</p><span>01 Define scope <ArrowRight size={12} /> 02 Inspect evidence <ArrowRight size={12} /> 03 Save report</span></section>}
      <div className="analysis-list" aria-live="polite">{analyses.map(analysis => <AnalysisBlock key={analysis.id} analysis={analysis} catalog={catalog} onClarify={submit} onRetry={submit} onSaved={onSaved} canSave={canRun} />)}</div>
      <div className="notebook-footnote"><ShieldCheck size={13} /><span>Workspace-scoped data · Read-only execution · Snapshot-backed reports</span></div>
    </main>
    <ContextPanel catalog={catalog} onOpenGlossary={onOpenGlossary} />
  </div>
}
