import { readFileSync } from 'node:fs'

const source = process.argv[2]
const document = source
  ? await fetch(source).then(response => { if (!response.ok) throw new Error(`OpenAPI fetch failed (${response.status})`); return response.json() })
  : JSON.parse(readFileSync(new URL('../src/api/openapi.json', import.meta.url), 'utf8'))

if (!document.openapi?.startsWith('3.')) throw new Error('Expected an OpenAPI 3 document')

function dereference(schema) {
  if (!schema) return {}
  if (schema.$ref) {
    const path = schema.$ref.replace(/^#\//, '').split('/')
    return dereference(path.reduce((value, segment) => value?.[segment], document))
  }
  if (schema.allOf) return { properties: Object.assign({}, ...schema.allOf.map(item => dereference(item).properties || {})) }
  if (schema.anyOf) return schema.anyOf.map(dereference).find(item => item.properties) || {}
  return schema
}

const contracts = [
  ['get', '/api/session', [], ['user', 'mode']],
  ['post', '/api/auth/login', ['email', 'password'], ['user', 'mode']],
  ['post', '/api/auth/logout'],
  ['get', '/api/catalog', [], ['metrics', 'dimensions', 'freshness', 'source_tables', 'synthetic', 'dataset_kind']],
  ['get', '/api/conversations', [], ['items']],
  ['post', '/api/conversations', [], ['id', 'title']],
  ['get', '/api/conversations/{conversation_id}', [], ['id', 'analyses']],
  ['post', '/api/conversations/{conversation_id}/analyses', ['question'], ['id', 'status', 'stage', 'question']],
  ['get', '/api/analyses/{analysis_id}', [], ['id', 'status', 'stage', 'question', 'plan', 'sql', 'result', 'events', 'snapshot']],
  ['get', '/api/analyses/{analysis_id}/events'],
  ['post', '/api/analyses/{analysis_id}/cancel'],
  ['get', '/api/reports', [], ['items']],
  ['post', '/api/reports', ['analysis_id', 'title'], ['id', 'title', 'current_version', 'versions']],
  ['get', '/api/reports/{report_id}', [], ['id', 'title', 'current_version', 'versions']],
  ['post', '/api/reports/{report_id}/refresh', [], ['report_id', 'analysis_id', 'status', 'current_version']],
  ['get', '/api/reports/{report_id}/versions/{version}', [], ['version', 'version_created_at', 'question', 'plan', 'sql', 'result', 'chart', 'narrative', 'evidence', 'snapshot', 'model_version', 'prompt_version', 'source_tables']],
  ['get', '/api/reports/{report_id}/export.csv'],
  ['get', '/api/reports/{report_id}/print'],
  ['get', '/api/imports/template.csv'],
  ['post', '/api/imports/preview', ['file'], ['token', 'accepted_count', 'rejected_count', 'preview']],
  ['post', '/api/imports/publish', ['token'], ['id', 'status', 'accepted_count']],
]

const problems = []
for (const [method, path, requestKeys = [], responseKeys = []] of contracts) {
  const operation = document.paths?.[path]?.[method]
  if (!operation) { problems.push(`${method.toUpperCase()} ${path}: route missing`); continue }
  if (requestKeys.length) {
    const body = operation.requestBody?.content?.['application/json']?.schema || operation.requestBody?.content?.['multipart/form-data']?.schema
    const properties = dereference(body).properties || {}
    for (const key of requestKeys) if (!(key in properties)) problems.push(`${method.toUpperCase()} ${path}: request.${key} missing`)
  }
  if (responseKeys.length) {
    const responses = operation.responses || {}
    const success = responses['200'] || responses['201']
    const properties = dereference(success?.content?.['application/json']?.schema).properties || {}
    for (const key of responseKeys) if (!(key in properties)) problems.push(`${method.toUpperCase()} ${path}: response.${key} missing`)
  }
}

if (problems.length) {
  for (const problem of problems) process.stderr.write(`${problem}\n`)
  process.exitCode = 1
} else {
  process.stdout.write(`OpenAPI contract verified: ${contracts.length} operations and their typed request/response fields.\n`)
}
