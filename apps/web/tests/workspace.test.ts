import assert from 'node:assert/strict'
import test from 'node:test'
import { buildQuestion, datasetLabel, resultProvenance, workspaceConfig } from '../src/workspace.ts'
import { chartNumber } from '../src/features/analysis/chartData.ts'
import { formatDate } from '../src/time.ts'

test('guided scope makes an editable question with explicit comparison and period', () => {
  assert.equal(buildQuestion('completed_orders', 'channel', 'last_month', true), 'Compare completed orders by channel last month with the previous period.')
  assert.equal(buildQuestion('refunds', 'month', 'this_year', false), 'Show refunds by month this year.')
  assert.equal(buildQuestion('average_order_value', '', 'last_year', false), 'Show average order value last year.')
})

test('unmapped scopes do not silently produce a different query', () => {
  assert.equal(buildQuestion('profit', 'channel', 'last_month', false), '')
  assert.equal(buildQuestion('net_revenue', 'region', 'last_month', false), '')
  assert.equal(buildQuestion('net_revenue', 'channel', 'last_quarter', false), '')
})

test('dataset identity is independent of model mode and unknown remains unconfirmed', () => {
  assert.equal(datasetLabel(true), 'Synthetic demonstration')
  assert.equal(datasetLabel(false), 'Workspace data')
  assert.equal(datasetLabel(), 'Data source unconfirmed')
  assert.equal(datasetLabel(true, 'mixed'), 'Mixed workspace data')
  assert.equal(datasetLabel(false, 'imported'), 'Imported workspace data')
  assert.equal(datasetLabel(false, 'unknown'), 'Data source unconfirmed')
})

test('saved result provenance never borrows a newer catalog snapshot', () => {
  assert.deepEqual(resultProvenance({ snapshot: { reference_date: '2025-09-01', created_at: '2025-09-02T00:00:00Z' } }), { referenceDate: '2025-09-01', createdAt: '2025-09-02T00:00:00Z' })
  assert.deepEqual(resultProvenance({}), { referenceDate: undefined, createdAt: undefined })
})

test('client workspace settings use trimmed values and safe defaults', () => {
  const settings = workspaceConfig({ VITE_PRODUCT_NAME: ' Atlas ', VITE_WORKSPACE_NAME: ' ', VITE_DEMO_EMAIL: 'demo@example.com' })
  assert.equal(settings.productName, 'Atlas')
  assert.equal(settings.workspaceName, 'Northstar Supply')
  assert.equal(settings.demoEmail, 'demo@example.com')
  assert.equal(settings.prompts.length, 3)
})

test('charts distinguish missing values from true zero and retain negative numbers', () => {
  for (const value of [null, undefined, '', ' ', false, true, 'invalid', Infinity, NaN]) assert.equal(chartNumber(value), undefined)
  assert.equal(chartNumber(0), 0)
  assert.equal(chartNumber('0'), 0)
  assert.equal(chartNumber('-12.5'), -12.5)
})

test('date presentation uses UTC regardless of host timezone or omitted API offset', () => {
  assert.equal(formatDate('2026-09-30T00:00:00'), 'Sep 30, 2026, 12:00 AM UTC')
  assert.equal(formatDate('2026-09-30T03:30:00+03:30'), 'Sep 30, 2026, 12:00 AM UTC')
  assert.equal(formatDate('invalid'), 'invalid')
  assert.equal(formatDate(), 'Date unavailable')
})
