import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import test from 'node:test'

const source = readFileSync(new URL('../public/theme-init.js', import.meta.url), 'utf8')
function boot(stored?: string, osDark = false, blocked = false) {
  const dataset: Record<string, string> = {}
  let mediaChange = () => {}
  let storageChange = (_: { key: string; newValue: string }) => {}
  const media = { matches: osDark, addEventListener: (_: string, fn: () => void) => { mediaChange = fn } }
  const writes: string[] = []
  const window: Record<string, any> = { matchMedia: () => media, addEventListener: (_: string, fn: typeof storageChange) => { storageChange = fn } }
  const document = { documentElement: { dataset }, querySelector: () => ({ setAttribute() {} }) }
  runInNewContext(source, { window, document, Set, localStorage: {
    getItem() { if (blocked) throw Error('blocked'); return stored },
    setItem(_key: string, value: string) { if (blocked) throw Error('blocked'); writes.push(value) },
  } })
  return { dataset, media, writes, controller: window.datatalkTheme, os: (dark: boolean) => { media.matches = dark; mediaChange() }, storage: storageChange }
}
test('fresh and invalid preferences use Dark before React, even on a light OS', () => {
  assert.equal(boot().dataset.theme, 'dark')
  assert.equal(boot('invalid').dataset.theme, 'dark')
  assert.equal(boot('light', true).dataset.theme, 'light')
})
test('explicit preference survives OS changes; System follows them live', () => {
  const state = boot('dark', false)
  state.os(false); assert.equal(state.dataset.theme, 'dark')
  state.controller.setPreference('system'); assert.equal(state.dataset.theme, 'light')
  state.os(true); assert.equal(state.dataset.theme, 'dark')
  state.controller.setPreference('light'); state.os(true); assert.equal(state.dataset.theme, 'light')
  assert.deepEqual(state.writes, ['system', 'light'])
})
test('blocked storage does not prevent switching or System behavior', () => {
  const state = boot(undefined, false, true)
  state.controller.setPreference('light'); assert.equal(state.dataset.theme, 'light')
  state.controller.setPreference('system'); state.os(true); assert.equal(state.dataset.theme, 'dark')
})
test('notifications ignore irrelevant OS changes; cross-tab preference is validated', () => {
  const state = boot('dark', true); let calls = 0
  const unsubscribe = state.controller.subscribe(() => calls++)
  state.os(false); assert.equal(calls, 0)
  state.storage({ key: 'datatalk.theme', newValue: 'light' }); assert.equal(calls, 1)
  state.storage({ key: 'datatalk.theme', newValue: 'bad' }); assert.equal(state.dataset.theme, 'light')
  unsubscribe(); state.controller.setPreference('dark'); assert.equal(calls, 1)
})
test('HTML bootstrap is external and blocking before styles and application entry', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  assert.match(html, /<script src="\/theme-init.js"><\/script>/)
  assert.ok(html.indexOf('/theme-init.js') < html.indexOf('/theme-base.css'))
  assert.ok(html.indexOf('/theme-init.js') < html.indexOf('/src/main.tsx'))
})
