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
  // `source` ('google_maps' | 'apple_maps') is appended to every call that
  // reads the ratings materialized-view chain, defaulted so existing call
  // sites that don't pass it keep working (matches the backend's own
  // `source: str = "google_maps"` defaults).
  voiceStates: (source = 'google_maps') => get(`/voice/states?source=${source}`),
  voiceBrands: (state, source = 'google_maps') => get(`/voice/brands?state=${encodeURIComponent(state)}&source=${source}`),
  voiceCounties: (state, source = 'google_maps') => get(`/voice/counties?state=${encodeURIComponent(state)}&source=${source}`),
  voiceCountyLocations: (state, countyFips, city, source = 'google_maps') =>
    get(`/voice/county-locations?state=${encodeURIComponent(state)}&county_fips=${encodeURIComponent(countyFips)}${city ? `&city=${encodeURIComponent(city)}` : ''}&source=${source}`),
  voiceCountyTowns: (state, countyFips, source = 'google_maps') =>
    get(`/voice/county-towns?state=${encodeURIComponent(state)}&county_fips=${encodeURIComponent(countyFips)}&source=${source}`),
  voiceCompetitorsByState: (state, source = 'google_maps') => get(`/voice/competitors-by-state?state=${encodeURIComponent(state)}&source=${source}`),
  voiceCompetitorsByCounty: (state, countyFips, source = 'google_maps') =>
    get(`/voice/competitors-by-county?state=${encodeURIComponent(state)}&county_fips=${encodeURIComponent(countyFips)}&source=${source}`),
  voiceBrandOptions: () => get('/voice/brand-options'),
  voiceMainBrandStates: (brandId, source = 'google_maps') => get(`/voice/main-brand/states?brand_id=${brandId}&source=${source}`),
  voiceMainBrandCounties: (brandId, state, source = 'google_maps') =>
    get(`/voice/main-brand/counties?brand_id=${brandId}&state=${encodeURIComponent(state)}&source=${source}`),
  voiceMainBrandTowns: (brandId, state, countyFips, source = 'google_maps') =>
    get(`/voice/main-brand/towns?brand_id=${brandId}&state=${encodeURIComponent(state)}${countyFips ? `&county_fips=${encodeURIComponent(countyFips)}` : ''}&source=${source}`),
  voiceMainBrandNationalSummary: (source = 'google_maps') => get(`/voice/main-brand/national-summary?source=${source}`),
  voiceMainBrandLocations: (brandId, source = 'google_maps') => get(`/voice/main-brand/locations?brand_id=${brandId}&source=${source}`),
  voiceCountyBrandMatrix: (state, source = 'google_maps') => get(`/voice/county-brand-matrix?state=${encodeURIComponent(state)}&source=${source}`),
  voiceCountyTownBrandMatrix: (state, countyFips, source = 'google_maps') =>
    get(`/voice/county-town-brand-matrix?state=${encodeURIComponent(state)}&county_fips=${encodeURIComponent(countyFips)}&source=${source}`),
  voiceStateTowns: (state, source = 'google_maps') => get(`/voice/state-towns?state=${encodeURIComponent(state)}&source=${source}`),
  voiceRollup: (state, city, source = 'google_maps') =>
    get(`/voice/rollup?${state ? `state=${encodeURIComponent(state)}` : ''}${city ? `&city=${encodeURIComponent(city)}` : ''}&source=${source}`),
  voiceHeadToHead: (state, city, source = 'google_maps') =>
    get(`/voice/head-to-head?${state ? `state=${encodeURIComponent(state)}` : ''}${city ? `&city=${encodeURIComponent(city)}` : ''}&source=${source}`),
  voiceReviewStates: () => get('/voice/review-states'),
  voiceReviewTowns: (state = 'TX') => get(`/voice/review-towns?state=${encodeURIComponent(state)}`),
  voiceReviewTrend: (state = 'TX', city, splitCompetitors = false) =>
    get(`/voice/review-trend?state=${encodeURIComponent(state)}` +
      (city ? `&city=${encodeURIComponent(city)}` : '') +
      `&split_competitors=${splitCompetitors}`),
  voiceReviewYoy: (state = 'TX', city, splitCompetitors = false) =>
    get(`/voice/review-yoy?state=${encodeURIComponent(state)}` +
      (city ? `&city=${encodeURIComponent(city)}` : '') +
      `&split_competitors=${splitCompetitors}`),
  voiceReviewThemeMix: (state = 'TX', { city, brand } = {}) =>
    get(`/voice/review-theme-mix?state=${encodeURIComponent(state)}` +
      (city ? `&city=${encodeURIComponent(city)}` : '') +
      (brand ? `&brand=${encodeURIComponent(brand)}` : '')),
  voiceReviewNegativeThemeMix: (state = 'TX', { city, ratings = [1, 2, 3] } = {}) =>
    get(`/voice/review-negative-theme-mix?state=${encodeURIComponent(state)}&ratings=${ratings.join(',')}` +
      (city ? `&city=${encodeURIComponent(city)}` : '')),
  // A live per-call summary (not precomputed), so give it a longer retry
  // budget than the default get() - it's a real-time Haiku call, not a
  // cached page, and 503s here would just mean "still starting up."
  voiceReviewThemeComplaints: (theme, state = 'TX', { city, brand, sentiment = 'negative' } = {}) =>
    get(`/voice/review-theme-complaints?theme=${encodeURIComponent(theme)}&state=${encodeURIComponent(state)}&sentiment=${sentiment}` +
      (city ? `&city=${encodeURIComponent(city)}` : '') +
      (brand ? `&brand=${encodeURIComponent(brand)}` : ''), { retries: 3, retryDelayMs: 1500 }),
  voiceReviewSample: (state, { city, brand, sentiment, month, theme, rating, limit = 30 } = {}) =>
    get(`/voice/review-sample?state=${encodeURIComponent(state)}` +
      (city ? `&city=${encodeURIComponent(city)}` : '') +
      (brand ? `&brand=${encodeURIComponent(brand)}` : '') +
      (sentiment ? `&sentiment=${encodeURIComponent(sentiment)}` : '') +
      (month ? `&month=${encodeURIComponent(month)}` : '') +
      (theme ? `&theme=${encodeURIComponent(theme)}` : '') +
      (rating ? `&rating=${rating}` : '') +
      `&limit=${limit}`),
  voiceRedditSummary: () => get('/voice/reddit-summary'),
  voiceRedditSample: ({ brand, sentiment, theme, aspect, limit = 30 } = {}) =>
    get(`/voice/reddit-sample?` +
      (brand ? `brand=${encodeURIComponent(brand)}&` : '') +
      (sentiment ? `sentiment=${encodeURIComponent(sentiment)}&` : '') +
      (theme ? `theme=${encodeURIComponent(theme)}&` : '') +
      (aspect ? `aspect=${encodeURIComponent(aspect)}&` : '') +
      `limit=${limit}`),
  voiceRedditThemeMix: (brand) => get(`/voice/reddit-theme-mix${brand ? `?brand=${encodeURIComponent(brand)}` : ''}`),
  voiceRedditNegativeThemeMix: (sentiment = 'negative') => get(`/voice/reddit-negative-theme-mix?sentiment=${sentiment}`),
  voiceRedditThemeComplaints: (theme, brand, sentiment = 'negative') =>
    get(`/voice/reddit-theme-complaints?theme=${encodeURIComponent(theme)}&sentiment=${sentiment}${brand ? `&brand=${encodeURIComponent(brand)}` : ''}`, { retries: 3, retryDelayMs: 1500 }),
}
