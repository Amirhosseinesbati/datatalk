export function formatDate(value?: string): string {
  if (!value) return 'Date unavailable'
  // The API's stored timestamps use UTC, including SQLite's offset-free representation.
  const timestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::[\d.]+)?$/.test(value) ? `${value}Z` : value
  const date = new Date(timestamp)
  return Number.isNaN(date.valueOf()) ? value : `${new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(date)} UTC`
}
