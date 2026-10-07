/** Local UI fixtures only. No database, real accounts, model, or remote service is used. */
import { createServer } from 'node:http'
import { fileURLToPath } from 'node:url'

export function createFixtureServer(port = 8314) {
  const conversations = []
  const analyses = new Map()
  const reports = []
  let signedIn = true
  let failedOnce = false
  let sequence = 0
  let sessionUnavailable = false
  const requests = []
  const catalog = {
    synthetic: true, dataset_kind: 'synthetic',
    freshness: { snapshot_id: 'ui-fixture-2026', reference_date: '2026-10-06', created_at: '2026-10-06T00:00:00Z', hash: 'synthetic-ui-fixture' },
    metrics: [
      { key: 'net_revenue', name: 'Net revenue', unit: 'usd_cents', definition: 'Completed sales less line discounts and refunds, recognized on their respective event dates.' },
      { key: 'completed_orders', name: 'Completed orders', unit: 'count', definition: 'Distinct completed orders. Cancelled orders do not contribute.' },
      { key: 'refunds', name: 'Refunds', unit: 'usd_cents', definition: 'Refund amounts recognized on the refund event date.' },
    ],
    dimensions: [{ key: 'channel', name: 'Sales channel' }, { key: 'category', name: 'Product category' }, { key: 'month', name: 'Month (UTC)' }],
    date_conventions: { timezone: 'UTC', currency: 'USD', interval: '[start, end)' },
    source_tables: ['synthetic_ui_fixture'],
  }
  const server = createServer(async (req, res) => {
    const path = new URL(req.url, 'http://localhost').pathname.replace(/^\/api/, '')
    requests.push(`${req.method} ${path}`)
    let body = ''
    for await (const part of req) body += part
    const data = body ? JSON.parse(body) : {}
    const send = (payload, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(payload)) }
    const session = { mode: 'DEMO', user: { id: 'ui-fixture-user', email: 'reviewer@fixture.example', workspace_id: 'ui-fixture', role: 'admin' } }
    if (path === '/session') return sessionUnavailable ? send({ detail: 'Fixture connection unavailable' }, 503) : signedIn ? send(session) : send({ detail: 'Sign in required' }, 401)
    if (path === '/auth/login') { if (data.password === 'wrong') return send({ detail: 'Fixture sign-in failed' }, 401); signedIn = true; return send(session) }
    if (path === '/auth/logout') { signedIn = false; return send({}) }
    if (path === '/catalog') return send(catalog)
    if (path === '/conversations' && req.method === 'GET') return send({ items: conversations })
    if (path === '/conversations' && req.method === 'POST') { const item = { id: `conversation-${++sequence}`, title: 'New analysis', analyses: [] }; conversations.unshift(item); return send(item, 201) }
    const conversation = conversations.find(item => path === `/conversations/${item.id}`)
    if (conversation) return send(conversation)
    const target = conversations.find(item => path === `/conversations/${item.id}/analyses`)
    if (target && req.method === 'POST') {
      await new Promise(resolve => setTimeout(resolve, 400))
      if (/network failure/i.test(data.question) && !failedOnce) { failedOnce = true; return send({ detail: 'Fixture service temporarily unavailable. Please retry.' }, 503) }
      const clarification = /best customers/i.test(data.question)
      const denied = /delete|drop/i.test(data.question)
      const empty = /empty scope/i.test(data.question)
      const analysis = {
        id: `analysis-${++sequence}`, conversation_id: target.id, question: data.question,
        status: denied ? 'failed' : clarification ? 'clarification' : 'completed',
        created_at: '2026-10-06T10:00:00Z',
        clarification: clarification ? { question: 'Which measure should rank customers?', options: ['Show net revenue by customer last month.', 'Show completed orders by customer last month.'] } : undefined,
        error: denied ? 'Only read-only sales questions are supported. No write was executed.' : undefined,
        narrative: 'Synthetic UI fixture: these illustrative values verify presentation and interactions only. They are not an executed analytics result or a benchmark.',
        plan: { metrics: ['net_revenue'], dimensions: ['channel'], start_date: '2026-09-01', end_date: '2026-10-01', comparison: 'previous_period' },
        sql: "-- Synthetic UI fixture; this SQL is not executed\nSELECT channel, current_value FROM synthetic_ui_fixture LIMIT 200;",
        result: { columns: ['channel', 'current_value', 'previous_value', 'change'], rows: empty ? [] : [
          { channel: 'Online', current_value: 2418000, previous_value: 2136000, change: 282000 },
          { channel: 'Wholesale', current_value: 1752000, previous_value: 1828000, change: -76000 },
          { channel: 'Retail', current_value: 1294000, previous_value: 1131000, change: 163000 },
        ], row_count: empty ? 0 : 3, truncated: false },
        chart: { type: 'bar', x: 'channel', y: 'change', title: 'Net revenue change · synthetic UI fixture' },
        snapshot: { id: 'older-ui-fixture', reference_date: '2026-09-30', created_at: '2026-09-30T00:00:00Z', hash: 'older-synthetic-ui-fixture' },
        source_tables: ['synthetic_ui_fixture'],
      }
      target.title = data.question
      target.analyses.push(analysis)
      analyses.set(analysis.id, analysis)
      return send(analysis, 202)
    }
    const analysis = [...analyses.values()].find(item => path === `/analyses/${item.id}`)
    if (analysis) return send(analysis)
    if (path === '/reports' && req.method === 'GET') return send({ items: reports })
    if (path === '/reports' && req.method === 'POST') {
      const analysis = analyses.get(data.analysis_id)
      if (!analysis) return send({ detail: 'Analysis not found' }, 404)
      const report = { id: `report-${++sequence}`, title: data.title, current_version: 1, created_at: '2026-10-06T10:00:00Z', latest_version: { version: 1, analysis }, versions: [{ version: 1, analysis }] }
      reports.unshift(report)
      return send(report, 201)
    }
    const report = reports.find(item => path === `/reports/${item.id}` || path === `/reports/${item.id}/versions/1`)
    if (report) return send(path.endsWith('/versions/1') ? report.latest_version : report)
    return send({ detail: 'Route unavailable in the UI fixture preview' }, 404)
  })
  server.setSessionUnavailable = value => { sessionUnavailable = value }
  server.requestLog = () => [...requests]
  return new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', () => resolve(server)) })
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await createFixtureServer(Number(process.env.PORT || 8314))
  console.log('Synthetic UI fixture API: http://127.0.0.1:8314/api (illustrative data only)')
}
