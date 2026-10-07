import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BookOpen, BookMarked, ChartNoAxesCombined, Database, FileUp, LockKeyhole, LogOut, Menu, PanelLeftClose, Sparkles, WifiOff } from 'lucide-react'
import type { Session } from './api/client'
import { ApiError, api, formatError } from './api/client'
import { CatalogView } from './features/catalog/CatalogView'
import { ImportsView } from './features/imports/ImportsView'
import { Notebook } from './features/notebook/Notebook'
import { ReportsView } from './features/reports/ReportsView'
import { Loading, Modal, Notice } from './ui'

import { workspace } from './config'
import { datasetLabel } from './workspace'
import { ThemeControl } from './ThemeControl'

type Page = 'notebook' | 'reports' | 'catalog' | 'imports'
const items: Array<{ id: Page; label: string; icon: typeof ChartNoAxesCombined }> = [
  { id: 'notebook', label: 'Notebook', icon: ChartNoAxesCombined },
  { id: 'reports', label: 'Reports', icon: BookMarked },
  { id: 'catalog', label: 'Catalog', icon: BookOpen },
  { id: 'imports', label: 'Data import', icon: FileUp },
]

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const passwordInput = useRef<HTMLInputElement>(null)
  const login = useMutation({ mutationFn: ({ email, password }: { email: string; password: string }) => api.login(email, password), onSuccess: onLogin })
  return <div className="login-page"><div className="login-side"><div className="brand brand-light"><span className="brand-mark"><ChartNoAxesCombined size={23} /></span><span><strong>{workspace.productName}</strong><small>{workspace.workspaceName}</small></span></div><div className="login-statement"><span className="login-kicker">SALES INTELLIGENCE, WITH RECEIPTS</span><h1>Your analytics<br /><em>workspace.</em></h1><p>Explore governed metrics, inspect every query, and save answers that can be reproduced.</p></div><div className="login-side-foot"><span className="orbit-dot" /> Analytical workspace · v1 pilot</div></div>
    <main className="login-main"><div className="standalone-theme"><ThemeControl /></div><div className="login-mobile-brand"><ChartNoAxesCombined size={23} /> {workspace.productName}</div><div className="login-card"><div className="login-icon"><LockKeyhole size={23} /></div><div className="eyebrow"><span className="eyebrow-mark" /> WELCOME BACK</div><h2>Sign in to your workspace</h2><p>Use your account, or fill the bundled demo email below.</p><form onSubmit={event => { event.preventDefault(); login.mutate({ email, password }) }}><label htmlFor="login-email">Email address</label><input id="login-email" type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@company.com" required /><label htmlFor="login-password">Password</label><input ref={passwordInput} id="login-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter password" required />{login.isError && <Notice tone="error" title="Sign in failed">{formatError(login.error)}</Notice>}<button className="primary-button login-submit" type="submit" disabled={login.isPending}>{login.isPending ? 'Signing in…' : <>Sign in <ArrowRight size={17} /></>}</button></form><div className="demo-separator"><span>LOCAL DEMONSTRATION</span></div><button className="demo-login" onClick={() => { setEmail(workspace.demoEmail); setPassword(''); passwordInput.current?.focus() }} disabled={login.isPending}><Sparkles size={18} /><span><strong>Use demo email</strong><small>Then enter the configured password</small></span><ArrowRight size={17} /></button><p className="login-note">Demo data is synthetic. Installations can change or disable the seeded account.</p></div></main>
  </div>
}

export function App() {
  const queryClient = useQueryClient()
  useEffect(() => { document.title = `${workspace.productName} · ${workspace.workspaceName}` }, [])
  const [page, setPage] = useState<Page>('notebook')
  const [glossaryOpen, setGlossaryOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 800px)').matches)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 800px)')
    const update = () => setIsMobile(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (!isMobile || !sidebarOpen) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const navigation = document.querySelector<HTMLElement>('.global-sidebar')
    const controls = () => Array.from(navigation?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') || [])
    controls()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setSidebarOpen(false) }
      if (event.key !== 'Tab') return
      const nodes = controls()
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      else if (!navigation?.contains(document.activeElement)) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = previousOverflow; previous?.focus() }
  }, [isMobile, sidebarOpen])
  const session = useQuery({ queryKey: ['session'], queryFn: api.session, retry: false, refetchInterval: 60_000 })
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: api.catalog, enabled: !!session.data })
  const logout = useMutation({ mutationFn: api.logout, onSuccess: () => { queryClient.clear(); setPage('notebook'); setSidebarOpen(false) } })

  if (session.isPending) return <div className="app-loading"><div className="standalone-theme"><ThemeControl /></div><span className="brand-mark"><ChartNoAxesCombined size={24} /></span><Loading label="Connecting to DataTalk…" /></div>
  if (session.isError && session.error instanceof ApiError && session.error.status === 401) return <Login onLogin={data => queryClient.setQueryData(['session'], data)} />
  if (!session.data) return <div className="connection-page"><div className="standalone-theme"><ThemeControl /></div><WifiOff size={34} /><h1>{workspace.productName} is unavailable</h1><p>{formatError(session.error)}</p><button className="primary-button" onClick={() => session.refetch()} disabled={session.isFetching}>{session.isFetching ? 'Retrying…' : 'Retry connection'}</button></div>

  const current = session.data
  function navigate(next: Page) { setPage(next); setSidebarOpen(false); setGlossaryOpen(false); requestAnimationFrame(() => document.getElementById('workspace-content')?.focus()) }
  const currentLabel = items.find(item => item.id === page)?.label || 'Notebook'
  return <div className="app-shell"><a className="skip-link" href="#workspace-content">Skip to workspace content</a>
    <aside className={`global-sidebar ${sidebarOpen ? 'mobile-open' : ''}`} aria-label="Primary navigation" inert={isMobile && !sidebarOpen} role={isMobile && sidebarOpen ? 'dialog' : undefined} aria-modal={isMobile && sidebarOpen ? true : undefined}>
      <div className="sidebar-top"><div className="brand"><span className="brand-mark"><ChartNoAxesCombined size={22} /></span><span><strong>{workspace.productName}</strong><small>{workspace.workspaceName}</small></span></div><button className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><PanelLeftClose size={18} /></button></div>
      <div className="workspace-identity"><span className="identity-icon">{workspace.workspaceName.charAt(0)}</span><span><strong>{workspace.workspaceName}</strong><small>{datasetLabel(catalog.data?.synthetic, catalog.data?.dataset_kind)}</small></span></div>
      <div className="nav-label">WORKSPACE</div><nav className="primary-nav">{items.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? 'active' : ''} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon size={18} /><span>{item.label}</span>{page === item.id && <span className="nav-active-dot" />}</button> })}</nav>
      <div className="sidebar-spacer" /><div className="sidebar-insight"><div><Database size={17} /> Defined data</div><p>Approved sales views and a bounded read-only query path.</p><button onClick={() => navigate('catalog')}>Explore catalog <ArrowRight size={14} /></button></div>
      <div className="sidebar-account"><span className="avatar">{current.user.email.charAt(0).toUpperCase()}</span><span><strong>{current.user.email}</strong><small>{current.user.role} · {current.user.workspace_id}</small></span><button className="icon-button" onClick={() => logout.mutate()} disabled={logout.isPending} aria-label="Sign out"><LogOut size={16} /></button></div>
    </aside>
    {sidebarOpen && <button className="mobile-overlay" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
    <div className="main-shell"><header className="global-header"><div className="header-left"><button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation" aria-expanded={sidebarOpen}><Menu size={21} /></button><span className="breadcrumb">Workspace</span><span className="breadcrumb-slash">/</span><strong>{currentLabel}</strong></div><div className="header-right"><ThemeControl /><span className={`mode-pill ${current.mode.toLowerCase() === 'demo' ? 'demo' : ''}`}>{current.mode.toLowerCase() === 'demo' ? 'DEMO MODE' : current.mode.toUpperCase()}</span><span className={`connection-status ${session.isError ? 'connection-lost' : ''}`}><i /> {session.isError ? 'Connection issue' : 'Session connected'}</span><span className="header-avatar">{current.user.email.charAt(0).toUpperCase()}</span></div></header>
      {session.isError && <div className="global-error"><Notice tone="error" title="Connection interrupted">{formatError(session.error)} <button className="text-button" disabled={session.isFetching} onClick={() => session.refetch()}>Retry connection</button></Notice></div>}
      {logout.isError && <div className="global-error"><Notice tone="error" title="Sign out failed">{formatError(logout.error)} <button className="text-button" onClick={() => logout.mutate()}>Retry sign out</button></Notice></div>}
      {catalog.isError && page !== 'catalog' && <div className="global-error"><Notice tone="error" title="Catalog unavailable">{formatError(catalog.error)} Definitions may be missing from the notebook. <button className="text-button" onClick={() => catalog.refetch()}>Retry catalog</button></Notice></div>}
      {page === 'notebook' && <Notebook session={current} catalog={catalog.data} onOpenGlossary={() => setGlossaryOpen(true)} onSaved={() => queryClient.invalidateQueries({ queryKey: ['reports'] })} />}
      {page === 'reports' && <ReportsView session={current} />}
      {page === 'catalog' && <div className="page-wrap" id="workspace-content" tabIndex={-1}>{catalog.isPending ? <Loading label="Loading semantic catalog…" /> : catalog.isError ? <Notice tone="error">{formatError(catalog.error)} <button className="text-button" onClick={() => catalog.refetch()}>Retry</button></Notice> : catalog.data && <CatalogView catalog={catalog.data} />}</div>}
      {page === 'imports' && <ImportsView session={current} />}
    </div>
    <nav className="mobile-bottom-nav" aria-label="Mobile navigation">{items.map(item => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? 'active' : ''} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon size={19} /><span>{item.label}</span></button> })}</nav>
    {glossaryOpen && <Modal title="Metric glossary" onClose={() => setGlossaryOpen(false)} width="wide">{catalog.isPending ? <Loading label="Loading definitions…" /> : catalog.data ? <CatalogView catalog={catalog.data} compact /> : <Notice tone="error">{formatError(catalog.error)}</Notice>}</Modal>}
  </div>
}
