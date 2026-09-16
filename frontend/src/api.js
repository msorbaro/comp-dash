const BASE = '/api'

// A 503 means the page is warming up in the background on the server (see
// backend/main.py's _page_cache) - retry quietly instead of surfacing an
// error. The warm loop computes pages one at a time (landscape, then the
// Our Brands rollup, then each own brand in turn), so right after a cold
// start/restart a brand near the end of that queue can take several
// minutes to be ready - the retry budget below is sized for that worst
// case, not just the fast/common case of an already-warm cache.
async function get(path, { retries = 60, retryDelayMs = 5000 } = {}) {
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
  // name/category are query params, not path segments: some brand and
  // category names contain a literal "/" (e.g. "Mavis Discount Tire /
  // Mavis Tires and Brakes", "Low Interest / Functional Categories"), and
  // Cloudflare normalizes an encoded slash in a path segment into a real
  // one before it reaches the app, breaking path-based routing for those.
  brand: (name) => get(`/brand?name=${encodeURIComponent(name)}`),
  channel: (name, channelId, n = 8, typeFilter = '') =>
    get(`/brand/channel?name=${encodeURIComponent(name)}&channel_id=${encodeURIComponent(channelId)}&n_creatives=${n}&type_filter=${encodeURIComponent(typeFilter)}`),
  category: (name, focusBrand) => get(`/category?name=${encodeURIComponent(name)}&focus_brand=${encodeURIComponent(focusBrand || '')}`),
  landscapeVolume: (category, days = 90) => get(`/landscape/volume?category=${encodeURIComponent(category)}&days=${days}`),
  messagingStudy: () => get('/landscape/messaging-study'),
  compare: (a, b) => get(`/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  refresh: () => fetch(BASE + '/refresh', { method: 'POST' }),
  voiceStates: () => get('/voice/states'),
  voiceTowns: (state) => get(`/voice/towns?state=${encodeURIComponent(state)}`),
  voiceStores: (state, city) => get(`/voice/stores?state=${encodeURIComponent(state)}${city ? `&city=${encodeURIComponent(city)}` : ''}`),
  voiceBrands: (state) => get(`/voice/brands?state=${encodeURIComponent(state)}`),
}
