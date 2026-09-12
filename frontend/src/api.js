const BASE = '/api'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${path} -> ${res.status}`)
  return res.json()
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
