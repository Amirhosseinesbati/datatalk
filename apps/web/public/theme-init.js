/* Blocking same-origin script: runs before CSS/React, with no inline CSP exception. */
(function () {
  if (window.datatalkTheme) return;
  var key = 'datatalk.theme';
  var valid = function (value) { return value === 'light' || value === 'dark' || value === 'system'; };
  var preference = 'dark';
  try { var stored = localStorage.getItem(key); if (valid(stored)) preference = stored; } catch (_) { /* In-memory preference still works. */ }
  var media;
  try { media = window.matchMedia('(prefers-color-scheme: dark)'); } catch (_) { media = { matches: true }; }
  var listeners = new Set();
  var snapshot = '';
  function apply() {
    var resolved = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    var next = preference + ':' + resolved;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = preference;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', resolved === 'dark' ? '#0b111c' : '#eef3f9');
    if (next !== snapshot) { snapshot = next; listeners.forEach(function (listener) { listener(); }); }
  }
  function setPreference(value) {
    if (!valid(value)) return;
    preference = value;
    try { localStorage.setItem(key, value); } catch (_) { /* Keep active work usable when storage is blocked/full. */ }
    apply();
  }
  var onSystemChange = function () { if (preference === 'system') apply(); };
  if (media.addEventListener) media.addEventListener('change', onSystemChange);
  else if (media.addListener) media.addListener(onSystemChange);
  window.addEventListener('storage', function (event) {
    if (event.key === key && valid(event.newValue)) { preference = event.newValue; apply(); }
  });
  window.datatalkTheme = {
    getSnapshot: function () { return snapshot; },
    subscribe: function (listener) { listeners.add(listener); return function () { listeners.delete(listener); }; },
    setPreference: setPreference
  };
  apply();
})();
