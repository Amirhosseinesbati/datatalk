/** Isolated, dependency-free Chromium regression. UI fixtures, not API/model quality evidence. */
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { resolve } from 'node:path'
import { createFixtureServer } from './fixture-preview.mjs'

const executable = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
if (!executable) throw new Error('Set CHROME_PATH to an installed Chromium browser; this script does not download one.')
const output = resolve('node_modules/.datatalk-theme-qa')
mkdirSync(output, { recursive: true })
const fixture = await createFixtureServer()
// Test the actual production bundle under an external-script-only CSP.
const preview = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname
  if (path.startsWith('/api/')) {
    let body = ''
    for await (const part of req) body += part
    const upstream = await fetch(`http://127.0.0.1:8314${path}`, { method: req.method, headers: { 'Content-Type': 'application/json' }, body: ['GET', 'HEAD'].includes(req.method) ? undefined : body })
    res.writeHead(upstream.status, { 'Content-Type': 'application/json' }); res.end(await upstream.text()); return
  }
  const root = resolve('dist')
  const file = resolve(root, `.${path === '/' ? '/index.html' : path}`)
  if (!file.startsWith(`${root}\\`) && !file.startsWith(`${root}/`)) { res.writeHead(403); res.end(); return }
  if (!existsSync(file)) { res.writeHead(404); res.end(); return }
  const type = path.endsWith('.js') ? 'application/javascript' : path.endsWith('.css') ? 'text/css' : path.endsWith('.svg') ? 'image/svg+xml' : 'text/html'
  res.writeHead(200, { 'Content-Type': type, 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'", 'Cache-Control': 'no-store' })
  res.end(readFileSync(file))
})
await new Promise((resolve, reject) => { preview.once('error', reject); preview.listen(4314, '127.0.0.1', resolve) })
let chrome
let socket
let id = 0
const pending = new Map()
const browserErrors = []
const policyErrors = []
const observations = []
const publicationChecks = { initialRunButton: [], enabledRunButton: [], mobileHeader: [], mobileLastContent: [] }
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function waitFor(predicate, label, timeout = 20_000) {
  const start = Date.now()
  while (Date.now() - start < timeout) { if (await predicate()) return; await pause(150) }
  throw new Error(`Timed out: ${label}`)
}
function command(method, params = {}) {
  return new Promise((resolve, reject) => {
    const callId = ++id
    const timeout = setTimeout(() => { pending.delete(callId); reject(new Error(`CDP timeout: ${method}`)) }, 15_000)
    pending.set(callId, { resolve: value => { clearTimeout(timeout); resolve(value) }, reject })
    socket.send(JSON.stringify({ id: callId, method, params }))
  })
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result.value
}
const text = () => evaluate('document.body?.innerText || ""')
async function click(label) {
  assert.equal(await evaluate(`(() => { const el = [...document.querySelectorAll('button')].find(el => el.textContent.trim() === ${JSON.stringify(label)}); if (!el || el.disabled) return false; el.click(); return true })()`), true, `Button available: ${label}`)
}
async function fill(selector, value) {
  await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)}); el.dispatchEvent(new Event('input', { bubbles: true })); })()`)
}
async function key(key, modifiers = 0) {
  await command('Input.dispatchKeyEvent', { type: 'keyDown', key, modifiers, windowsVirtualKeyCode: key === 'Tab' ? 9 : 27 })
  await command('Input.dispatchKeyEvent', { type: 'keyUp', key, modifiers, windowsVirtualKeyCode: key === 'Tab' ? 9 : 27 })
}
async function ask(question, expected) {
  await waitFor(async () => await evaluate('document.querySelector("#analysis-question")?.disabled === false'), 'composer ready')
  const before = await evaluate('document.querySelectorAll(".analysis-block").length')
  await fill('#analysis-question', question)
  await click('Run analysis')
  await waitFor(async () => (await evaluate('document.querySelectorAll(".analysis-block").length')) > before && (await text()).includes(expected), expected)
}
async function screenshot(name) {
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
  const { data } = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  writeFileSync(resolve(output, name), Buffer.from(data, 'base64'))
}
async function noOverflow() {
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'No horizontal page overflow')
}
async function theme(value) {
  assert.equal(await evaluate(`(() => { const el = document.querySelector('select[aria-label="Appearance"]'); if (!el) return false; el.value = ${JSON.stringify(value)}; el.dispatchEvent(new Event('change', { bubbles: true })); return true })()`), true)
  await waitFor(async () => await evaluate('document.documentElement.dataset.themePreference') === value, `theme ${value}`)
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
  assert.equal(await evaluate('getComputedStyle(document.documentElement).colorScheme === document.documentElement.dataset.theme'), true, 'Native controls match resolved theme')
}
async function captureThemes(prefix) {
  for (const value of ['dark', 'light']) {
    await theme(value); await noOverflow()
    // Protect exact data and muted metadata against legacy white surfaces in Dark.
    const contrastFailures = await evaluate(`(() => {
      const rgb = value => value.match(/[\\d.]+/g)?.map(Number) || [];
      const luminance = color => rgb(color).slice(0, 3).map(value => { const n = value / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4 }).reduce((total, value, index) => total + value * [.2126, .7152, .0722][index], 0);
      return [...document.querySelectorAll('.table-scroll td, .catalog-overview span, .catalog-heading > span, .login-note, .chart-tooltip')].flatMap(el => {
        if (!el.getClientRects().length) return [];
        let surface = el;
        while (surface.parentElement && (rgb(getComputedStyle(surface).backgroundColor)[3] ?? 1) === 0) surface = surface.parentElement;
        const foreground = luminance(getComputedStyle(el).color), background = luminance(getComputedStyle(surface).backgroundColor);
        const ratio = (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05);
        return ratio >= 4.5 ? [] : [{ text: el.innerText.slice(0, 50), ratio }];
      });
    })()`)
    assert.deepEqual(contrastFailures, [], `Data/metadata text contrast: ${prefix} ${value}`)
    await screenshot(`${prefix}-${value}.png`)
  }
}
async function runButtonEvidence() {
  return evaluate(`(() => {
    const el = document.querySelector('.composer-footer button[type="submit"]'), css = getComputedStyle(el);
    const brightness = Number(css.filter.match(/brightness\\(([\\d.]+)\\)/)?.[1] || 1);
    const luminance = color => color.match(/[\\d.]+/g).slice(0, 3).map(Number).map(value => { const n = Math.min(value * brightness, 255) / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4 }).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
    const a = luminance(css.color), b = luminance(css.backgroundColor);
    return { theme: document.documentElement.dataset.theme, disabled: el.disabled, editorValue: document.querySelector('#analysis-question').value, placeholder: document.querySelector('#analysis-question').placeholder, color: css.color, background: css.backgroundColor, opacity: css.opacity, brightness, contrast: (Math.max(a,b)+.05)/(Math.min(a,b)+.05) };
  })()`)
}
async function verifyMobileBounds(kind) {
  const evidence = await evaluate(`(() => {
    const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom } };
    return { theme: document.documentElement.dataset.theme, width: innerWidth, height: innerHeight, header: rect('.global-header'), themeControl: rect('.theme-control'), appearanceDisabled: document.querySelector('select[aria-label="Appearance"]').disabled, menu: rect('.mobile-menu'), navigation: rect('.mobile-bottom-nav'), lastAction: rect('.context-glossary') };
  })()`)
  if (kind === 'header') {
    assert.equal(evidence.appearanceDisabled, false, 'Mobile theme selector is enabled')
    for (const box of [evidence.themeControl, evidence.menu]) {
      assert.ok(box.left >= 0 && box.right <= evidence.width && box.top >= 0 && box.bottom <= evidence.header.bottom, 'Mobile header control fits viewport/header')
    }
    publicationChecks.mobileHeader.push(evidence)
  } else {
    assert.ok(evidence.lastAction.top >= 0 && evidence.lastAction.bottom <= evidence.navigation.top && evidence.lastAction.bottom > evidence.lastAction.top, 'Final context action is visible above fixed navigation at maximum scroll')
    publicationChecks.mobileLastContent.push(evidence)
  }
}

try {
  await waitFor(async () => { try { return (await fetch('http://127.0.0.1:4314')).ok } catch { return false } }, 'local production preview')
  chrome = spawn(executable, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-sync', '--disable-component-update',
    '--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
    `--user-data-dir=${resolve(output, `chrome-${Date.now()}`)}`, 'about:blank',
  ], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] })
  const browserUrl = await new Promise((resolve, reject) => {
    let stderr = ''
    const timeout = setTimeout(() => reject(new Error('Chromium startup timeout')), 20_000)
    chrome.stderr.on('data', chunk => { stderr += chunk; const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/); if (match) { clearTimeout(timeout); resolve(match[1]) } })
    chrome.once('error', reject)
  })
  const debugOrigin = new URL(browserUrl).origin.replace('ws:', 'http:')
  const targets = await (await fetch(`${debugOrigin}/json/list`)).json()
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }))
  socket.addEventListener('message', event => {
    const payload = JSON.parse(event.data)
    if (payload.id && pending.has(payload.id)) {
      const request = pending.get(payload.id); pending.delete(payload.id)
      payload.error ? request.reject(new Error(payload.error.message)) : request.resolve(payload.result)
    }
    if (payload.method === 'Runtime.exceptionThrown') browserErrors.push(payload.params.exceptionDetails.text)
    if (payload.method === 'Log.entryAdded' && payload.params.entry.source === 'security') policyErrors.push(payload.params.entry.text)
  })
  await command('Page.enable')
  await command('Runtime.enable')
  await command('Emulation.setFocusEmulationEnabled', { enabled: true })
  await command('Log.enable')
  await command('Page.addScriptToEvaluateOnNewDocument', { source: "window.__themeAtPaint = []; new PerformanceObserver(list => { for (const entry of list.getEntries()) window.__themeAtPaint.push({ name: entry.name, theme: document.documentElement.dataset.theme }); }).observe({ type: 'paint', buffered: true });" })
  await command('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }, { name: 'prefers-reduced-motion', value: 'reduce' }] })
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false })
  fixture.setSessionUnavailable(true)
  await command('Page.navigate', { url: 'http://127.0.0.1:4314' })
  await waitFor(async () => (await text()).includes('DataTalk is unavailable'), 'initial unavailable connection')
  assert.equal(await evaluate('document.documentElement.dataset.theme'), 'dark', 'Fresh visit defaults dark on light OS')
  assert.equal(await evaluate('window.__themeAtPaint.length > 0 && window.__themeAtPaint.every(entry => entry.theme === "dark")'), true, 'Dark is applied before first paint')
  await captureThemes('connection-desktop')
  fixture.setSessionUnavailable(false)
  await click('Retry connection')
  await waitFor(async () => (await text()).includes('3 defined metrics'), 'catalog-backed initial workspace')
  await evaluate('document.documentElement.style.scrollBehavior = "auto"')
  assert.match(await text(), /Synthetic demonstration/)
  await noOverflow()
  await captureThemes('workspace-desktop')
  for (const value of ['dark', 'light']) {
    await theme(value)
    const evidence = await runButtonEvidence()
    assert.equal(evidence.disabled, true, 'Initial screenshot Run button is disabled')
    assert.equal(evidence.editorValue, '', 'Visible initial question is placeholder only')
    publicationChecks.initialRunButton.push(evidence)
  }
  observations.push('Desktop initial state: source, reference date, starter prompts, no overflow')

  await evaluate('document.querySelector(".question-builder").open = true')
  await click('Use this question')
  assert.equal(await evaluate('document.querySelector("#analysis-question").value'), 'Show net revenue by channel last month.')
  await waitFor(async () => await evaluate('document.querySelector(".composer-footer button").disabled') === false, 'Run button enabled by real draft')
  for (const value of ['dark', 'light']) {
    await theme(value)
    const evidence = await runButtonEvidence()
    assert.equal(evidence.disabled, false, 'Real question enables Run')
    assert.equal(evidence.opacity, '1', 'Enabled Run is not faded')
    assert.ok(evidence.contrast >= 4.5, `Enabled ${value} Run label contrast meets 4.5:1: ${JSON.stringify(evidence)}`)
    publicationChecks.enabledRunButton.push({ state: 'normal', ...evidence })
    const point = await evaluate('(() => { const r = document.querySelector(".composer-footer button").getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 } })()')
    await command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    await evaluate('new Promise(resolve => requestAnimationFrame(resolve))')
    const hovered = await runButtonEvidence()
    assert.ok(hovered.contrast >= 4.5, `Enabled ${value} hover contrast meets 4.5:1`)
    publicationChecks.enabledRunButton.push({ state: 'hover', ...hovered })
    await command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1, y: 1 })
    await evaluate('document.querySelector(".composer-footer button").focus()')
    const focused = await runButtonEvidence()
    assert.ok(focused.contrast >= 4.5, `Enabled ${value} focused contrast meets 4.5:1`)
    publicationChecks.enabledRunButton.push({ state: 'focus', ...focused })
    await evaluate('scrollTo(0, 0)')
    await screenshot(`run-enabled-desktop-${value}.png`)
  }
  await fill('.context-search input', 'net_revenue')
  await waitFor(async () => await evaluate('document.querySelectorAll(".context-metric").length') === 1, 'schema context filter')
  await evaluate('window.__editorBeforeTheme = document.querySelector("#analysis-question"); true')
  const requestsBeforeTheme = fixture.requestLog().length
  await theme('dark'); await theme('light')
  assert.equal(await evaluate('document.querySelector("#analysis-question") === window.__editorBeforeTheme && document.querySelector("#analysis-question").value === "Show net revenue by channel last month."'), true, 'Theme preserves editor identity and draft')
  assert.equal(await evaluate('document.querySelector(".context-search input").value === "net_revenue" && document.querySelectorAll(".context-metric").length === 1'), true, 'Theme preserves data context filter')
  await pause(250)
  assert.equal(fixture.requestLog().length, requestsBeforeTheme, 'Theme change sends no business request')
  await fill('.context-search input', '')
  await click('Run analysis')
  assert.equal(await evaluate('document.querySelector(".new-page-button").disabled'), true, 'Cannot switch notebook during request')
  await theme('dark')
  await waitFor(async () => (await text()).includes('Synthetic UI fixture:'), 'completed analysis')
  await waitFor(async () => await evaluate('(() => { const point = document.querySelector(".chart-point"); if (point) { point.blur(); point.focus(); } return !!document.querySelector(".chart-tooltip") })()'), 'keyboard chart tooltip')
  assert.match(await evaluate('document.querySelector(".chart-tooltip").innerText'), /Online/)
  await captureThemes('result-desktop')
  await key('Escape')
  await waitFor(async () => await evaluate('document.querySelector(".chart-tooltip") === null'), 'chart tooltip dismissed')
  assert.equal(await evaluate('document.querySelector(".chart-tooltip") === null'), true, 'Chart tooltip dismisses with Escape')
  await click('Query')
  assert.match(await text(), /this SQL is not executed/)
  await click('Table')
  assert.match(await text(), /\$24,180\.00/)
  await evaluate('document.querySelector(".evidence-details").open = true')
  assert.match(await text(), /2026-09-30/)
  assert.match(await text(), /may differ from this result/)
  await evaluate('document.querySelector(".analysis-block").scrollIntoView()')
  observations.push('Guided question, executed UI lifecycle, exact money table, query and original snapshot')
  await click('Save report')
  await waitFor(async () => await evaluate('document.activeElement.id.startsWith("report-title-")'), 'modal initial focus')
  await fill('[id^="report-title-"]', 'Preserved modal draft')
  await evaluate('window.datatalkTheme.setPreference("dark")')
  assert.equal(await evaluate('document.querySelector("[id^=report-title-]").value'), 'Preserved modal draft', 'Theme preserves open modal fields')
  await screenshot('save-modal-dark.png')
  await key('Escape')
  assert.equal(await evaluate('document.activeElement.classList.contains("save-button")'), true, 'Modal returns focus to save action')
  await click('Save report')
  await fill('[id^="report-title-"]', 'Channel review · synthetic UI fixture')
  await evaluate('document.querySelector(".modal form").requestSubmit()')
  await waitFor(async () => (await text()).includes('Report saved.'), 'report saved feedback')
  await click('Reports')
  await waitFor(async () => (await text()).includes('Channel review'), 'reopened report')
  await captureThemes('reports-desktop')
  await click('Catalog')
  await waitFor(async () => (await text()).includes('governed metrics'), 'catalog page')
  await fill('.search-field input', 'no-fixture-match')
  await waitFor(async () => (await text()).includes('No matching definitions'), 'catalog no results')
  await captureThemes('catalog-empty-desktop')
  await fill('.search-field input', '')
  await captureThemes('catalog-desktop')
  await click('Data import')
  await waitFor(async () => (await text()).includes('Drop your CSV here'), 'import page')
  await captureThemes('imports-desktop')
  await evaluate('(() => { const dt = new DataTransfer(); dt.items.add(new File(["synthetic fixture"], "fixture.txt", { type: "text/plain" })); const input = document.querySelector("#sales-csv-file"); input.files = dt.files; input.dispatchEvent(new Event("change", { bubbles: true })); })()')
  await waitFor(async () => (await text()).includes('Choose a .csv file'), 'local invalid file error')
  await captureThemes('import-error-desktop')
  await click('Notebook')
  await waitFor(async () => (await text()).includes('Synthetic UI fixture:'), 'reopened conversation')
  await evaluate('document.querySelector(".history-drawer").open = true; document.querySelector(".history-drawer summary").focus()')
  await key('Escape')
  assert.equal(await evaluate('!document.querySelector(".history-drawer").open && document.activeElement.matches(".history-drawer summary")'), true, 'Recent questions closes with Escape and retains focus')
  observations.push('Save modal focus and retained draft, success feedback, reports/reopening, catalog filtering/empty state, local CSV precheck and history Escape')

  await ask('best customers', 'Which measure should rank customers?')
  await click('Show net revenue by customer last month.')
  await waitFor(async () => (await evaluate('document.querySelectorAll(".analysis-block").length')) === 3, 'clarification follow-up')
  await ask('delete all orders', 'Only read-only sales questions')
  await fill('#analysis-question', 'network failure')
  await click('Run analysis')
  await waitFor(async () => (await text()).includes('Your draft is restored'), 'request error')
  await evaluate('document.querySelector(".notice-error").scrollIntoView({ block: "center" })')
  await captureThemes('request-error-desktop')
  assert.equal(await evaluate('document.querySelector("#analysis-question").value'), 'network failure')
  const beforeRetry = await evaluate('document.querySelectorAll(".analysis-block").length')
  await click('Retry submitted question')
  await waitFor(async () => (await evaluate('document.querySelectorAll(".analysis-block").length')) > beforeRetry && !(await text()).includes('Your draft is restored'), 'successful retry')
  await ask('empty scope', 'No data in this scope')
  await evaluate('[...document.querySelectorAll(".analysis-block")].at(-1).scrollIntoView({ block: "start" })')
  await captureThemes('empty-result-desktop')
  for (const width of [1024, 768]) {
    await command('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: false })
    await evaluate('scrollTo(0, 0)')
    await captureThemes(`workspace-${width}`)
  }
  observations.push('Clarification follow-up, policy denial, request failure/draft recovery/retry, empty result')

  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await evaluate('scrollTo(0, 0)')
  await noOverflow()
  await captureThemes('workspace-mobile')
  for (const value of ['dark', 'light']) {
    await theme(value); await evaluate('scrollTo(0, 0)'); await verifyMobileBounds('header')
    await screenshot(`mobile-header-${value}.png`)
    await evaluate('scrollTo(0, document.documentElement.scrollHeight)'); await verifyMobileBounds('last')
    await screenshot(`mobile-last-content-${value}.png`)
  }
  await command('Emulation.setDeviceMetricsOverride', { width: 320, height: 740, deviceScaleFactor: 1, mobile: true })
  await noOverflow()
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await click('New analysis')
  await waitFor(async () => (await text()).includes('No results in this notebook'), 'fresh mobile notebook')
  await evaluate('document.querySelector(".question-builder").open = true; document.querySelector(".question-builder").scrollIntoView()')
  await noOverflow()
  await captureThemes('builder-mobile')
  await click('Use this question')
  await click('Run analysis')
  await waitFor(async () => (await text()).includes('Synthetic UI fixture:'), 'mobile run')
  await click('Table')
  await noOverflow()
  await evaluate('document.querySelector(".result-surface").scrollIntoView({ block: "center" })')
  await captureThemes('result-mobile')
  observations.push('390px mobile: new notebook, builder, repeat run and table with no page overflow')

  await evaluate('document.querySelector(".mobile-menu").click()')
  await waitFor(async () => await evaluate('document.querySelector(".global-sidebar").classList.contains("mobile-open")'), 'mobile navigation opened')
  assert.equal(await evaluate('document.activeElement.classList.contains("sidebar-close")'), true, 'Mobile navigation receives focus')
  await key('Tab', 8)
  assert.equal(await evaluate('document.activeElement.getAttribute("aria-label")'), 'Sign out', 'Mobile navigation traps reverse Tab')
  await evaluate('window.datatalkTheme.setPreference("dark")')
  assert.equal(await evaluate('document.querySelector(".global-sidebar").classList.contains("mobile-open")'), true, 'Theme preserves navigation state')
  await screenshot('navigation-mobile-dark.png')
  await key('Escape')
  assert.equal(await evaluate('document.querySelector(".global-sidebar").inert'), true, 'Closed mobile navigation is inert')
  await evaluate('document.querySelector(".mobile-menu").click()')
  await evaluate('document.querySelector(".sidebar-account button").click()')
  await waitFor(async () => (await text()).includes('Sign in to your workspace'), 'login state after sign out')
  await noOverflow()
  await captureThemes('login-mobile')
  await fill('#login-email', 'reviewer@fixture.example')
  await fill('#login-password', 'wrong')
  await evaluate('document.querySelector(".login-card form").requestSubmit()')
  await waitFor(async () => (await text()).includes('Fixture sign-in failed'), 'login error')
  await fill('#login-password', 'fixture-only')
  await evaluate('document.querySelector(".login-card form").requestSubmit()')
  await waitFor(async () => (await text()).includes('3 defined metrics'), 'repeated login succeeds')
  observations.push('Mobile navigation focus/Tab/Escape, sign out, login failure and successful retry')
  await theme('system')
  assert.equal(await evaluate('document.documentElement.dataset.theme'), 'light', 'System resolves current OS')
  await command('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] })
  await waitFor(async () => await evaluate('document.documentElement.dataset.theme') === 'dark', 'System follows live OS')
  await theme('light')
  await command('Page.reload')
  await waitFor(async () => (await text()).includes('3 defined metrics'), 'reload after persisted theme')
  assert.equal(await evaluate('document.documentElement.dataset.theme'), 'light', 'Explicit preference survives reload and dark OS')
  assert.equal(await evaluate('window.__themeAtPaint.length > 0 && window.__themeAtPaint.every(entry => entry.theme === "light")'), true, 'Persisted light is applied before paint')
  await command('Page.addScriptToEvaluateOnNewDocument', { source: "Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Blocked for regression', 'SecurityError'); } });" })
  await command('Page.reload')
  await waitFor(async () => (await text()).includes('3 defined metrics'), 'workspace with blocked storage')
  await theme('light'); await theme('system')
  assert.equal(await evaluate('document.documentElement.dataset.theme'), 'dark', 'Blocked storage still allows System')
  observations.push('Both themes at 1440, 1024, 768 and 390; no overflow at 320; accessible chart tooltip, unchanged draft/modal/navigation/request flow; zero theme-triggered API calls; persisted and System pre-paint themes; blocked storage; strict CSP')
  assert.deepEqual(browserErrors, [], 'No uncaught browser exceptions')
  assert.deepEqual(policyErrors, [], 'No CSP violations')
  writeFileSync(resolve(output, 'verification.json'), JSON.stringify({ fixtureOnly: true, productionBundle: true, strictCsp: true, observations, browserErrors, policyErrors }, null, 2))
  writeFileSync(resolve(output, 'publication-check.json'), JSON.stringify({ fixtureOnly: true, publicationChecks }, null, 2))
  console.log(JSON.stringify({ publicationChecks }, null, 2))
  console.log(JSON.stringify({ passed: observations.length, fixtureOnly: true, output, observations }, null, 2))
} catch (error) {
  console.error(JSON.stringify({ failure: error.message, active: await evaluate('document.activeElement?.outerHTML.slice(0, 700)').catch(() => null), theme: await evaluate('document.documentElement.dataset.theme').catch(() => null), browserErrors, policyErrors }))
  throw error
} finally {
  if (socket?.readyState === WebSocket.OPEN) { try { await command('Browser.close') } catch { /* Owned process is stopped below. */ } socket.close() }
  chrome?.kill()
  preview.closeAllConnections()
  preview.close()
  fixture.closeAllConnections()
  fixture.close()
}
