import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, FileSpreadsheet, FileUp, Info, ShieldCheck, UploadCloud, X } from 'lucide-react'
import type { ImportPreview, Session } from '../../api/client'
import { api, formatError } from '../../api/client'
import { formatCell, Notice, resultColumnTitle } from '../../ui'

const MAX_FILE_MB = 10

export function ImportsView({ session }: { session: Session }) {
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [localError, setLocalError] = useState('')
  const [dragging, setDragging] = useState(false)
  const previewMutation = useMutation({ mutationFn: api.previewImport, onSuccess: data => { setPreview(data); setLocalError('') } })
  const publish = useMutation({ mutationFn: api.publishImport, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['catalog'] }); queryClient.invalidateQueries({ queryKey: ['conversations'] }) } })
  const canImport = session.user.role === 'admin' || session.user.role === 'operator'

  function chooseFile(next: File | null) {
    setPreview(null)
    publish.reset()
    previewMutation.reset()
    setLocalError('')
    if (!next) { setFile(null); return }
    if (!next.name.toLowerCase().endsWith('.csv')) { setLocalError('Choose a .csv file that follows the supported sales template.'); setFile(null); return }
    if (next.size > MAX_FILE_MB * 1024 * 1024) { setLocalError(`The file exceeds the ${MAX_FILE_MB} MB browser preview limit.`); setFile(null); return }
    setFile(next)
  }

  const columns = preview?.columns?.length ? preview.columns : Object.keys(preview?.preview?.[0] || {})
  return <main className="imports-main" id="workspace-content" tabIndex={-1}><header className="section-intro"><div className="eyebrow"><span className="eyebrow-mark" /> CONTROLLED DATA IMPORT</div><h1>Bring sales data<br /><em>into the picture.</em></h1><p>Preview a supported CSV, inspect type validation and rejected rows, then publish accepted records as one transaction.</p></header>
    <div className="import-flow"><div className="flow-step active"><span>01</span><strong>Choose file</strong></div><div className={`flow-step ${preview ? 'active' : ''}`}><span>02</span><strong>Review rows</strong></div><div className={`flow-step ${publish.isSuccess ? 'active' : ''}`}><span>03</span><strong>Publish</strong></div></div>
    {!canImport && <Notice tone="error" title="Import permission required">Your role can inspect analytics but cannot publish data. Ask a workspace operator or admin.</Notice>}
    <div className="import-card"><div className="import-card-head"><span className="import-symbol"><FileSpreadsheet size={22} /></span><div><h2>Sales CSV template</h2><p>Only the documented Northstar Supply sales schema is supported in v1.</p></div><a className="text-button template-link" href={api.importTemplateUrl()} download>Download template <ArrowRight size={15} /></a></div>
      <div className={`dropzone ${dragging ? 'dragging' : ''} ${!canImport ? 'disabled' : ''}`} onDragOver={event => { event.preventDefault(); if (canImport) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (canImport) chooseFile(event.dataTransfer.files[0] || null) }}>
        <UploadCloud size={28} aria-hidden="true" /><strong>{file ? file.name : 'Drop your CSV here'}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB · ready to preview` : 'or choose a file from your computer'}</span>
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" id="sales-csv-file" onChange={event => chooseFile(event.target.files?.[0] || null)} disabled={!canImport} />
        <button className="secondary-button" type="button" onClick={() => input.current?.click()} disabled={!canImport}><FileUp size={16} /> Browse files</button>
      </div>
      <div className="import-help"><Info size={16} /><span>CSV files are checked on the server before any rows are published. The preview token expires; reselect a file if it does.</span></div>
      {localError && <Notice tone="error">{localError}</Notice>}
      {file && <div className="import-file-actions"><span><CheckCircle2 size={16} /> {file.name}</span><div><button className="text-button" onClick={() => { chooseFile(null); if (input.current) input.current.value = '' }}><X size={14} /> Remove</button><button className="primary-button" onClick={() => previewMutation.mutate(file)} disabled={previewMutation.isPending}>{previewMutation.isPending ? 'Validating…' : 'Preview import'} <ArrowRight size={16} /></button></div></div>}
      {previewMutation.isError && <Notice tone="error" title="Preview failed">{formatError(previewMutation.error)}</Notice>}
    </div>
    {preview && <section className="import-preview"><div className="preview-head"><div><span className="mini-eyebrow">VALIDATION PREVIEW</span><h2>Review before publishing</h2></div><div className="preview-counts"><span className="accepted"><strong>{preview.accepted_count}</strong> accepted</span><span className="rejected"><strong>{preview.rejected_count}</strong> rejected</span></div></div>
      {preview.rejected_count > 0 && <Notice tone="info" title="Rejected rows stay out of the dataset">Review the issues below. Publishing includes only the accepted rows.</Notice>}
      <div className="preview-table-wrap"><h3>Sample of accepted rows</h3><div className="table-scroll"><table><thead><tr>{columns.map(column => <th scope="col" key={column}>{resultColumnTitle(column)}{column.endsWith('_cents') ? ' (USD)' : ''}</th>)}</tr></thead><tbody>{preview.preview?.slice(0, 10).map((row, index) => <tr key={index}>{columns.map(column => <td key={column}>{formatCell(row[column], column)}</td>)}</tr>)}</tbody></table></div>{!preview.preview?.length && <p className="table-empty">No accepted rows are available to preview.</p>}</div>
      {!!preview.errors?.length && <div className="import-errors"><h3>Rejected row report</h3><ul>{preview.errors.slice(0, 30).map((error, index) => <li key={index}><span>{typeof error === 'string' ? `Issue ${index + 1}` : `Row ${error.row ?? '?'}`}</span><strong>{typeof error === 'string' ? error : `${error.field ? `${error.field}: ` : ''}${error.message || 'Invalid value'}`}</strong></li>)}</ul>{preview.errors.length > 30 && <p>Showing 30 of {preview.errors.length} issues.</p>}</div>}
      <div className="publish-row"><span><ShieldCheck size={17} /> Publish accepted records transactionally</span><button className="primary-button" onClick={() => publish.mutate(preview.token)} disabled={publish.isPending || publish.isSuccess || preview.accepted_count < 1}>{publish.isPending ? 'Publishing…' : 'Publish accepted rows'} <ArrowRight size={16} /></button></div>
      {publish.isError && <Notice tone="error" title="Publish failed">{formatError(publish.error)} No success was recorded in this browser.</Notice>}
      {publish.isSuccess && <Notice tone="success" title="Dataset updated">Import {publish.data.id} published {publish.data.accepted_count} accepted rows. New analyses use the latest dataset snapshot.</Notice>}
    </section>}
  </main>
}
