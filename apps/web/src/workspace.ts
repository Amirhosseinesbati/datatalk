export const defaultPrompts = [
  { label: 'Channel performance', text: "Which channel's net revenue changed most last month?", detail: 'Compare channels with the previous period', icon: 'compare' },
  { label: 'Product mix', text: 'Show net revenue by category last month.', detail: 'See where revenue comes from', icon: 'mix' },
  { label: 'Refund trend', text: 'Show refunds by month this year.', detail: 'Explore refunds on their event date', icon: 'trend' },
] as const

export function workspaceConfig(env: Record<string, string | undefined>) {
  const value = (key: string, fallback: string) => env[key]?.trim() || fallback
  return {
    productName: value('VITE_PRODUCT_NAME', 'DataTalk'),
    workspaceName: value('VITE_WORKSPACE_NAME', 'Northstar Supply'),
    demoEmail: value('VITE_DEMO_EMAIL', 'manager@northstar.example.com'),
    prompts: defaultPrompts,
  }
}

export const guidedMetrics: Record<string, string> = {
  net_revenue: 'net revenue', gross_sales: 'gross sales', discounts: 'discounts',
  refunds: 'refunds', completed_orders: 'completed orders', average_order_value: 'average order value',
  returning_customers: 'returning customers', cancelled_orders: 'cancelled orders',
}
export const guidedGroups: Record<string, string> = {
  channel: 'channel', category: 'category', product: 'product', customer: 'customer',
  campaign: 'campaign', month: 'month', week: 'week', day: 'day',
}
export const guidedPeriods: Record<string, string> = {
  last_month: 'last month', this_year: 'this year', last_year: 'last year',
}

export function buildQuestion(metric: string, group: string, period: string, compare: boolean): string {
  if (!guidedMetrics[metric] || (group && !guidedGroups[group]) || !guidedPeriods[period]) return ''
  return `${compare ? 'Compare' : 'Show'} ${guidedMetrics[metric]}${group ? ` by ${guidedGroups[group]}` : ''} ${guidedPeriods[period]}${compare ? ' with the previous period' : ''}.`
}

export function datasetLabel(synthetic?: boolean, kind?: string): string {
  if (kind === 'mixed') return 'Mixed workspace data'
  if (kind === 'imported') return 'Imported workspace data'
  if (kind === 'unknown') return 'Data source unconfirmed'
  if (kind === 'synthetic') return 'Synthetic demonstration'
  return synthetic === true ? 'Synthetic demonstration' : synthetic === false ? 'Workspace data' : 'Data source unconfirmed'
}

// A saved result's own snapshot remains authoritative after imports change the catalog.
export function resultProvenance(analysis: { snapshot?: { reference_date: string; created_at: string } | null }) {
  return { referenceDate: analysis.snapshot?.reference_date, createdAt: analysis.snapshot?.created_at }
}
