import { useSyncExternalStore } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'

type Preference = 'dark' | 'light' | 'system'
interface ThemeController {
  getSnapshot: () => string
  subscribe: (listener: () => void) => () => void
  setPreference: (value: Preference) => void
}
declare global { interface Window { datatalkTheme?: ThemeController } }
const subscribe = (listener: () => void) => window.datatalkTheme?.subscribe(listener) || (() => {})
const getSnapshot = () => window.datatalkTheme?.getSnapshot() || 'dark:dark'

export function ThemeControl() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => 'dark:dark')
  const [preference, resolved] = snapshot.split(':')
  const Icon = preference === 'system' ? Monitor : resolved === 'dark' ? Moon : Sun
  return <label className="theme-control" title={`Appearance: ${preference}${preference === 'system' ? ` (${resolved})` : ''}`}>
    <Icon size={15} aria-hidden="true" /><span className="sr-only">Appearance</span>
    <select aria-label="Appearance" value={preference} disabled={!window.datatalkTheme} onChange={event => window.datatalkTheme?.setPreference(event.target.value as Preference)}>
      <option value="dark">Dark</option><option value="light">Light</option><option value="system">System</option>
    </select>
  </label>
}
