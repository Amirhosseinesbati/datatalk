import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BookOpen, CirclePlus, Clock3, History, LoaderCircle, MessageCircleQuestion, Search, Send, Sparkles } from 'lucide-react'
import type { Analysis, Catalog, Conversation, Session } from '../../api/client'
import { api, formatError } from '../../api/client'
import { AnalysisBlock } from '../analysis/AnalysisBlock'
import { Loading, Notice } from '../../ui'

const PROMPTS = [
  { label: 'Channel change', text: "Which channel's net revenue changed most last month?" },
  { label: 'Product mix', text: 'Break down net revenue by product category for the last quarter.' },
  { label: 'Refund trend', text: 'How did refunds change month by month this year?' },
]

export function Notebook({ catalog, session, onOpenGlossary, onSaved }: { catalog?: Catalog; session: Session; onOpenGlossary: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [freshPage, setFreshPage] = useState(false)
  const [question, setQuestion] = useState('')
  const [historyLimit, setHistoryLimit] = useState(8)
  const [localAnalyses, setLocalAnalyses] = useState<Analysis[]>([])
  const [requestError, setRequestError] = useState('')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: api.conversations })
  const conversation = useQuery({ queryKey: ['conversation', selectedId], queryFn: () => api.conversation(selectedId!), enabled: !!selectedId })

  useEffect(() => {
    if (!selectedId && !freshPage && conversations.data?.items?.length) setSelectedId(conversations.data.items[0].id)
  }, [conversations.data, selectedId, freshPage])

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
    analyze.mutate(value)
  }

  function newPage() {
    setSelectedId(null)
    setFreshPage(true)
    setLocalAnalyses([])
    setQuestion('')
    setRequestError('')
    textarea.current?.focus()
  }

  function chooseConversation(id: string) {
    setSelectedId(id)
    setFreshPage(false)
    setLocalAnalyses([])
    setRequestError('')
  }

  function usePrompt(text: string) {
    setQuestion(text)
    textarea.current?.focus()
  }

  const history = conversation.data?.analyses || []
  const historyItems = conversations.data?.items || []
  const analyses = [...history, ...localAnalyses.filter(local => !history.some(saved => saved.id === local.id))]
  const noAnalyses = analyses.length === 0
  const canRun = session.user.role !== 'viewer'

  return <div className="notebook-grid">
    <aside className="notebook-aside" aria-label="Notebook history">
      <div className="aside-head"><span className="mini-eyebrow">YOUR WORKSPACE</span><button className="icon-button" onClick={newPage} aria-label="New analysis"><CirclePlus size={19} /></button></div>
      <button className="new-page-button" onClick={newPage}><CirclePlus size={17} /> New analysis</button>
      <div className="aside-section-title"><History size={14} /> RECENT QUESTIONS</div>
      {conversations.isPending && <Loading compact label="Loading history…" />}
      {conversations.isError && <p className="aside-error">{formatError(conversations.error)}</p>}
      <div className="history-list">
        {historyItems.slice(0, historyLimit).map((item: Conversation) => <button key={item.id} className={`history-item ${selectedId === item.id ? 'active' : ''}`} onClick={() => chooseConversation(item.id)}><span>{item.title || 'Untitled analysis'}</span><ArrowRight size={14} /></button>)}
        {historyItems.length > historyLimit && <button className="text-button" onClick={() => setHistoryLimit(count => count + 8)}>Show older questions <ArrowRight size={13} /></button>}
        {!conversations.isPending && !conversations.data?.items?.length && <p className="aside-muted">Your questions will appear here.</p>}
      </div>
      <div className="aside-bottom"><button data-modal-return onClick={event => { event.currentTarget.focus(); onOpenGlossary() }}><BookOpen size={17} /><span><strong>Metric glossary</strong><small>Business definitions</small></span><ArrowRight size={15} /></button><div className="catalog-snippet"><Search size={15} /> {catalog?.metrics?.length ?? 0} governed metrics · {catalog?.dimensions?.length ?? 0} dimensions</div></div>
    </aside>

    <main className="notebook-main">
      <header className="page-intro"><div><div className="eyebrow"><span className="eyebrow-mark" /> ANALYTICAL NOTEBOOK</div><h1>Ask your data.<br /><em>See the evidence.</em></h1><p>Answers grounded in Northstar Supply's defined sales metrics, with the query and assumptions always within reach.</p></div><div className="intro-aside"><span className="seed-stamp">SYNTHETIC DEMO DATASET</span><p>Explore a fictional sales operation built for this local demonstration.</p></div></header>

      {selectedId && conversation.isPending && noAnalyses && <Loading label="Opening notebook…" />}
      {conversation.isError && <Notice tone="error" title="Could not open this notebook">{formatError(conversation.error)}</Notice>}
      {noAnalyses && (!selectedId || !conversation.isPending) && <div className="starter-panel"><div className="starter-icon"><MessageCircleQuestion size={23} /></div><div className="starter-content"><span className="mini-eyebrow">START WITH A QUESTION</span><h2>Turn a business question into a report.</h2><p>Ask for trends, comparisons, customer groups, products, channels or refunds. DataTalk resolves the scope, runs a bounded query, and shows what supports the answer.</p><div className="prompt-grid">{PROMPTS.map(prompt => <button key={prompt.label} onClick={() => usePrompt(prompt.text)}><span>{prompt.label}</span><strong>{prompt.text}</strong><ArrowRight size={17} /></button>)}</div></div></div>}

      <div className="analysis-list" aria-live="polite">{analyses.map(analysis => <AnalysisBlock key={analysis.id} analysis={analysis} catalog={catalog} onClarify={submit} onRetry={submit} onSaved={onSaved} canSave={canRun} />)}</div>

      <section className="question-composer" aria-label="Ask a sales question"><div className="composer-heading"><div><Sparkles size={16} /><strong>{noAnalyses ? 'Ask a question' : 'Ask a follow-up'}</strong></div><span><Clock3 size={13} /> Sales data, governed metrics</span></div>
        <form onSubmit={event => { event.preventDefault(); submit() }}><label className="sr-only" htmlFor="analysis-question">Your sales question</label><textarea ref={textarea} id="analysis-question" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); submit() } }} placeholder="e.g. Which channel's net revenue changed most last month?" rows={3} maxLength={1000} disabled={!canRun || analyze.isPending} /><div className="composer-footer"><span>{!canRun ? 'Viewer role cannot run analyses.' : 'Ctrl + Enter to run · Specific scopes produce clearer answers'}</span><button className="primary-button" type="submit" disabled={!canRun || !question.trim() || analyze.isPending}>{analyze.isPending ? <><LoaderCircle className="spin" size={16} /> Running…</> : <><Send size={16} /> Run analysis</>}</button></div></form>
      </section>
      {analyze.isPending && <div className="run-status" role="status"><LoaderCircle className="spin" size={16} /><div><strong>Running the analytical workflow</strong><span>Waiting for the server's validated result. This may take a moment.</span></div></div>}
      {requestError && <Notice tone="error" title="Request failed">{requestError} Your question was not saved. You can retry.</Notice>}
      <div className="notebook-footnote"><span>Answers use approved analytical views and a read-only query role.</span><button onClick={onOpenGlossary}>Explore definitions <ArrowRight size={13} /></button></div>
    </main>
  </div>
}
