const BASE = '/api'

// A 503 means the page is warming up in the background on the server (see
// backend/main.py's _page_cache) - retry quietly instead of surfacing an
// error, since it resolves itself within a couple of minutes at most.
async function get(path, { retries = 20, retryDelayMs = 5000 } = {}) {
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(BASE + path)
    if (res.ok) return res.json()
    if (res.status === 503 && attempt < retries) {
      await new Promise((r) => setTimeout(r, retryDelayMs))
      continue
    }
    throw new Error(`${path} -> ${res.status}`)
  }
}

export const api = {
  meta: () => get('/meta'),
  landscape: () => get('/landscape'),
  brand: (name) => get(`/brand/${encodeURIComponent(name)}`),
  channel: (name, channelId, n = 8, typeFilter = '') =>
    get(`/brand/${encodeURIComponent(name)}/channel/${channelId}?n_creatives=${n}&type_filter=${encodeURIComponent(typeFilter)}`),
  category: (name, focusBrand) => get(`/category/${encodeURIComponent(name)}?focus_brand=${encodeURIComponent(focusBrand || '')}`),
  compare: (a, b) => get(`/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  refresh: () => fetch(BASE + '/refresh', { method: 'POST' }),
}
