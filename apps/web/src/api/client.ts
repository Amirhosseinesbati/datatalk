export type UserRole = 'admin' | 'operator' | 'viewer'

export interface Session {
  user: { id: string; email: string; role: UserRole; workspace_id: string }
  mode: 'DEMO' | 'CONNECTED' | string
}

export interface Metric {
  key: string
  name: string
  definition: string
  unit?: string
  source?: string
  expression?: string
}

export interface Dimension {
  key: string
  name: string
  definition?: string
  type?: string
  values?: string[]
}

export interface Catalog {
  metrics: Metric[]
  dimensions: Dimension[]
  freshness?: { snapshot_id: string; reference_date: string; created_at: string; hash: string } | null
  source_tables?: string[]
  synthetic?: boolean
  dataset_kind?: 'synthetic' | 'imported' | 'mixed' | 'unknown'
  date_conventions?: { timezone?: string; interval?: string; sales_basis?: string; refund_basis?: string; currency?: string }
}

export type ResultCell = string | number | boolean | null
export interface AnalysisResult {
  columns: string[]
  rows: Record<string, ResultCell>[]
  row_count: number
  truncated: boolean
  row_cap?: number
  query_duration_ms?: number | null
}

export interface ChartSpec {
  type: 'bar' | 'line' | 'table' | 'pie' | string
  x?: string
  y?: string
  series?: string
  title?: string
}

export interface Analysis {
  id: string
  conversation_id?: string
  question: string
  status: 'completed' | 'clarification' | 'failed' | 'running' | string
  stage?: string
  clarification?: string | { question?: string; options?: string[] }
  plan?: Record<string, unknown>
  sql?: string
  result?: AnalysisResult
  chart?: ChartSpec
  narrative?: string
  evidence?: unknown
  error?: string | { detail?: string; message?: string }
  created_at?: string
  snapshot_hash?: string
  snapshot?: { id: string; hash: string; reference_date: string; created_at: string } | null
  events?: Array<{ stage: string; at?: string }>
  source_tables?: string[]
  model_version?: string
  prompt_version?: string
}

export interface Conversation {
  id: string
  title?: string
  created_at?: string
  updated_at?: string
  analyses?: Analysis[]
}

export interface ReportVersion {
  id?: string
  version: number
  created_at?: string
  version_created_at?: string
  analysis?: Analysis
  analysis_id?: string
  snapshot_hash?: string
  snapshot?: string | { hash?: string; created_at?: string }
  result?: AnalysisResult
  chart?: ChartSpec
  sql?: string
  plan?: Record<string, unknown>
  question?: string
  narrative?: string
  source_tables?: string[]
  model_version?: string
  prompt_version?: string
}

export interface Report {
  id: string
  title: string
  created_at?: string
  updated_at?: string
  current_version?: number
  version?: number
  versions?: ReportVersion[]
  analysis?: Analysis
  question?: string
  latest_version?: ReportVersion
}

export interface ReportRefreshJob {
  report_id: string
  analysis_id: string
  status: string
  current_version: number
}

export interface ImportPreview {
  token: string
  accepted_count: number
  rejected_count: number
  errors: Array<{ row?: number; field?: string; message?: string } | string>
  preview: Record<string, ResultCell>[]
  columns?: string[]
}

export interface ImportPublished {
  id: string
  status: string
  accepted_count: number
  rejected_count?: number
  snapshot_hash?: string
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message)
    this.name = 'ApiError'
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')

function messageFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload === 'string') return payload
  if (!payload || typeof payload !== 'object') return fallback
  const value = payload as Record<string, unknown>
  if (typeof value.detail === 'string') return value.detail
  if (Array.isArray(value.detail)) return value.detail.map(item => typeof item === 'object' && item && 'msg' in item ? String(item.msg) : String(item)).join('; ')
  if (typeof value.message === 'string') return value.message
  if (typeof value.error === 'string') return value.error
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: 'include',
      headers: { ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...init.headers },
    })
  } catch {
    throw new ApiError('Cannot reach the DataTalk service. Check the connection and try again.', 0, 'network')
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => undefined)
    throw new ApiError(messageFromPayload(payload, `Request failed (${response.status}).`), response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const json = (body: unknown) => JSON.stringify(body)

export const api = {
  base: API_BASE,
  session: () => request<Session>('/session'),
  login: (email: string, password: string) => request<Session>('/auth/login', { method: 'POST', body: json({ email, password }) }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  catalog: () => request<Catalog>('/catalog'),
  conversations: () => request<{ items: Conversation[] }>('/conversations'),
  conversation: (id: string) => request<Conversation>(`/conversations/${encodeURIComponent(id)}`),
  createConversation: () => request<Conversation>('/conversations', { method: 'POST' }),
  analyze: (conversationId: string, question: string) => request<Analysis>(`/conversations/${encodeURIComponent(conversationId)}/analyses`, { method: 'POST', body: json({ question }) }),
  analysis: (id: string) => request<Analysis>(`/analyses/${encodeURIComponent(id)}`),
  cancelAnalysis: (id: string) => request<{ id: string; status: string }>(`/analyses/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  reports: () => request<{ items: Report[] }>('/reports'),
  report: (id: string) => request<Report>(`/reports/${encodeURIComponent(id)}`),
  saveReport: (analysisId: string, title: string) => request<Report>('/reports', { method: 'POST', body: json({ analysis_id: analysisId, title }) }),
  refreshReport: (id: string) => request<ReportRefreshJob>(`/reports/${encodeURIComponent(id)}/refresh`, { method: 'POST' }),
  reportVersion: (id: string, version: number) => request<ReportVersion>(`/reports/${encodeURIComponent(id)}/versions/${version}`),
  previewImport: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<ImportPreview>('/imports/preview', { method: 'POST', body })
  },
  publishImport: (token: string) => request<ImportPublished>('/imports/publish', { method: 'POST', body: json({ token }) }),
  csvUrl: (id: string) => `${API_BASE}/reports/${encodeURIComponent(id)}/export.csv`,
  printUrl: (id: string) => `${API_BASE}/reports/${encodeURIComponent(id)}/print`,
  importTemplateUrl: () => `${API_BASE}/imports/template.csv`,
}

export function formatError(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
