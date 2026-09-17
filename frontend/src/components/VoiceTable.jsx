import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import { MUTED, INK_TEXT, SLATE_200, SLATE_600, DEEP_TEAL, TEAL_700, GREEN, ROSE, MONO, fmtNum } from '../styles'

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

function deltaColor(v) {
  if (v === null || v === undefined) return MUTED
  return v >= 0 ? GREEN : ROSE
}

function fmtRating(v) {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

function fmtDelta(v) {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
}

// Review-count-weighted average, matching the convention every rollup in
// this app already uses (state_delta, town_delta, etc: sum(n*x)/sum(n)) -
// so a brand's one 400-review flagship store isn't diluted by three
// 10-review locations the way a plain average would.
function weightedAvg(items, valueKey, weightKey) {
  let sumWeight = 0, sumWeightedValue = 0
  for (const it of items) {
    const v = it[valueKey]
    const w = it[weightKey]
    if (v === null || v === undefined || !w) continue
    sumWeight += w
    sumWeightedValue += w * v
  }
  return sumWeight ? sumWeightedValue / sumWeight : null
}

function sortRows(rows, key, dir) {
  if (!key) return rows
  return [...rows].sort((a, b) => {
    const av = a[key], bv = b[key]
    if (av === null || av === undefined) return 1
    if (bv === null || bv === undefined) return -1
    if (av === bv) return 0
    const cmp = av > bv ? 1 : -1
    return dir === 'asc' ? cmp : -cmp
  })
}

function downloadCsv(rows, columns, filename) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [columns.map((c) => esc(c.label)).join(',')]
  for (const r of rows) lines.push(columns.map((c) => esc(c.value(r))).join(','))
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function SortableHead({ columns, sortKey, sortDir, onSort }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: columns.map((c) => c.width || '1fr').join(' '), gap: 12 }}>
        {columns.map((c) => (
          <div
            key={c.label}
            onClick={() => c.sortKey && onSort(c.sortKey)}
            style={{ fontSize: 9.5, letterSpacing: '.1em', color: sortKey === c.sortKey ? DEEP_TEAL : MUTED, fontWeight: 600, cursor: c.sortKey ? 'pointer' : 'default', userSelect: 'none' }}
          >
            {c.label}{sortKey === c.sortKey ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
          </div>
        ))}
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
    </>
  )
}

function comparabilityNote(r) {
  if (!r.n_low_comparability_locations) return ''
  const n = r.n_low_comparability_locations
  return ` (${n} store${n === 1 ? '' : 's'} w/ <3 nearby competitors)`
}

function areaStatus(r, { noDataLabel } = {}) {
  if (noDataLabel && !r.has_data) return noDataLabel
  return r.suppressed ? 'Insufficient data' : `OK${comparabilityNote(r)}`
}

// State/county/town rollups all share this shape (has_data only applies at
// state level - county/town rows only ever exist because they have data).
const STATE_COLUMNS = [
  { label: 'STATE', width: '1.7fr', sortKey: 'state_name', value: (r) => r.state_name },
  { label: 'MAVIS RATING', width: '1fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.1fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '0.8fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'AVG REVIEWS/STORE', width: '1.1fr', sortKey: 'avgReviewsPerStore', value: (r) => fmtNum(r.avgReviewsPerStore) },
  { label: 'STATUS', width: '1.4fr', sortKey: null, value: (r) => areaStatus(r, { noDataLabel: 'No pilot data' }) },
  { label: 'BY BRAND', width: '0.8fr', sortKey: null, action: 'brand', value: () => 'View ▸' },
  { label: 'BY COMPETITOR', width: '0.9fr', sortKey: null, action: 'competitors', value: () => 'View ▸' },
]

const COUNTY_COLUMNS = [
  { label: 'COUNTY', width: '1.7fr', sortKey: 'county_name', value: (r) => r.county_name },
  { label: 'MAVIS RATING', width: '1fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.1fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '0.8fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'AVG REVIEWS/STORE', width: '1.1fr', sortKey: 'avgReviewsPerStore', value: (r) => fmtNum(r.avgReviewsPerStore) },
  { label: 'STATUS', width: '1.3fr', sortKey: null, value: (r) => areaStatus(r) },
  { label: 'BY COMPETITOR', width: '0.9fr', sortKey: null, action: 'competitors', value: () => 'View ▸' },
]

const TOWN_COLUMNS = [
  { label: 'TOWN', width: '2fr', sortKey: 'city', value: (r) => r.city },
  { label: 'MAVIS RATING', width: '1.1fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '0.9fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'AVG REVIEWS/STORE', width: '1.2fr', sortKey: 'avgReviewsPerStore', value: (r) => fmtNum(r.avgReviewsPerStore) },
  { label: 'STATUS', width: '1.6fr', sortKey: null, value: (r) => areaStatus(r) },
]

const BRAND_COLUMNS = [
  { label: 'MAVIS BRAND', width: '2fr', sortKey: 'brand', value: (r) => r.brand },
  { label: 'MAVIS RATING', width: '1.2fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '1fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'AVG REVIEWS/STORE', width: '1.2fr', sortKey: 'avgReviewsPerStore', value: (r) => fmtNum(r.avgReviewsPerStore) },
  { label: 'LOCATIONS', width: '0.9fr', sortKey: 'n_mavis_locations', value: (r) => fmtNum(r.n_mavis_locations) },
  { label: 'STATUS', width: '1.6fr', sortKey: null, value: (r) => areaStatus(r) },
]

// Every named competitor's own footprint - no delta/benchmark column since
// that's specifically "Mavis vs. its nearby competitors," not something a
// competitor has relative to itself.
const COMPETITOR_COLUMNS = [
  { label: 'COMPETITOR BRAND', width: '2fr', sortKey: 'brand', value: (r) => r.brand },
  { label: 'AVG RATING', width: '1.1fr', sortKey: 'avg_raw_rating', value: (r) => fmtRating(r.avg_raw_rating) },
  { label: 'ADJ. RATING', width: '1.1fr', sortKey: 'avg_adj_rating', value: (r) => fmtRating(r.avg_adj_rating) },
  { label: 'LOCATIONS', width: '0.9fr', sortKey: 'n_locations', value: (r) => fmtNum(r.n_locations) },
  { label: 'AVG REVIEWS/STORE', width: '1.2fr', sortKey: 'avgReviewsPerStore', value: (r) => fmtNum(r.avgReviewsPerStore) },
]

// Table's "always on" brand dropdown at state/county/town level - live,
// works for any brand (Mavis or competitor) since it's just "this brand vs.
// the area it's in," not the Mavis-vs-local-competitors delta concept.
function brandFilteredColumns(level, stateNameByCode) {
  const nameColumn =
    level === 'state' ? { label: 'STATE', width: '1.7fr', sortKey: 'state', value: (r) => stateNameByCode[r.state] || r.state } :
    level === 'county' ? { label: 'COUNTY', width: '1.7fr', sortKey: 'county_name', value: (r) => r.county_name } :
    { label: 'TOWN', width: '2fr', sortKey: 'city', value: (r) => r.city }
  return [
    nameColumn,
    { label: 'AVG RATING', width: '1fr', sortKey: 'avg_rating', value: (r) => fmtRating(r.avg_rating) },
    { label: 'AREA AVG (ALL BRANDS)', width: '1.3fr', sortKey: null, value: (r) => fmtRating(r.area_avg_rating) },
    {
      label: '% LOCATIONS ABOVE AREA AVG', width: '1.5fr', sortKey: 'pct_above_area_avg',
      value: (r) => (r.pct_above_area_avg === null || r.pct_above_area_avg === undefined ? '—' : `${Math.round(r.pct_above_area_avg * 100)}%`),
    },
    { label: 'AVG REVIEWS/STORE', width: '1.2fr', sortKey: 'avg_reviews_per_store', value: (r) => fmtNum(r.avg_reviews_per_store) },
    { label: 'LOCATIONS', width: '0.8fr', sortKey: 'n_locations', value: (r) => fmtNum(r.n_locations) },
  ]
}

// Store level is grouped by brand (one row per brand in this town, not per
// location) - a brand with multiple locations here shows a review-weighted
// aggregate with an expand toggle to see the individual stores, rather than
// a flat list where the same brand appears N times. Mavis rows carry a
// delta/comparability vs. nearby competitors; competitor rows don't.
const STORE_AGG_COLUMNS = [
  { label: 'BRAND', width: '1.8fr', sortKey: 'brand', value: (r) => r.brand },
  { label: 'TYPE', width: '0.9fr', sortKey: 'family', value: (r) => (r.family === 'mavis' ? 'Mavis' : 'Competitor') },
  { label: 'AVG RATING', width: '1fr', sortKey: 'avgRating', value: (r) => fmtRating(r.avgRating) },
  { label: 'ADJ. RATING', width: '1fr', sortKey: 'avgAdjRating', value: (r) => fmtRating(r.avgAdjRating) },
  { label: 'DELTA', width: '0.9fr', sortKey: 'avgDelta', value: (r) => (r.family === 'mavis' ? fmtDelta(r.avgDelta) : '—') },
  { label: 'AVG REVIEWS/STORE', width: '1.1fr', sortKey: 'avgReviewsPerStore', value: (r) => fmtNum(r.avgReviewsPerStore) },
  { label: 'LOCATIONS', width: '0.8fr', sortKey: 'n_locations', value: (r) => fmtNum(r.n_locations) },
  { label: 'NEIGHBORHOOD AVG', width: '1.2fr', sortKey: null, value: (r) => fmtRating(r.neighborhoodAvg) },
  {
    label: '% LOCATIONS ABOVE AVG', width: '1.4fr', sortKey: 'pctAboveAvg',
    value: (r) => (r.pctAboveAvg === null || r.pctAboveAvg === undefined ? '—' : `${Math.round(r.pctAboveAvg * 100)}%`),
  },
]

// One row per individual store, shown indented under an expanded brand row.
const STORE_CHILD_COLUMNS = [
  { label: '', width: '1.8fr', sortKey: null, value: (r) => r.name },
  { label: '', width: '0.9fr', sortKey: null, value: () => '' },
  { label: '', width: '1fr', sortKey: null, value: (r) => fmtRating(r.raw_rating) },
  { label: '', width: '1fr', sortKey: null, value: (r) => fmtRating(r.adj_rating) },
  { label: '', width: '0.9fr', sortKey: null, value: (r) => (r.family === 'mavis' ? fmtDelta(r.delta) : '—') },
  { label: '', width: '0.9fr', sortKey: null, value: (r) => fmtNum(r.review_count) },
  { label: '', width: '0.8fr', sortKey: null, value: () => '' },
  { label: '', width: '1.2fr', sortKey: null, value: () => '' },
  {
    label: '', width: '1.4fr', sortKey: null,
    value: (r) => {
      if (r.family !== 'mavis') return '—'
      if (r.delta === null || r.delta === undefined) return 'No competitors in this town'
      return r.low_comparability ? `Low comparability (${r.n_competitors_in_ring} in town)` : `OK (${r.n_competitors_in_ring} in town)`
    },
  },
]

const COLUMNS_BY_LEVEL = {
  state: STATE_COLUMNS, county: COUNTY_COLUMNS, town: TOWN_COLUMNS,
  store: STORE_AGG_COLUMNS, brand: BRAND_COLUMNS, competitors: COMPETITOR_COLUMNS,
}
const DEFAULT_SORT_BY_LEVEL = {
  state: 'delta', county: 'delta', town: 'delta', store: 'avgRating',
  brand: 'delta', competitors: 'avg_adj_rating',
}

export default function VoiceTable({ states }) {
  const [drill, setDrillRaw] = useState({ level: 'state' })
  const [counties, setCounties] = useState(null)
  const [towns, setTowns] = useState(null)
  const [locations, setLocations] = useState(null)
  const [brands, setBrands] = useState(null)
  const [competitors, setCompetitors] = useState(null)
  const [error, setError] = useState(null)
  const [sortKey, setSortKey] = useState('delta')
  const [sortDir, setSortDir] = useState('desc')
  const [familyFilter, setFamilyFilter] = useState('')
  const [expandedBrands, setExpandedBrands] = useState(() => new Set())

  // The "always on" brand dropdown - persists across drill navigation
  // (unlike familyFilter/expandedBrands, which are reset per-level in
  // goDrill below), since picking a brand and then clicking through
  // state -> county -> town should keep showing that same brand's numbers.
  const [allBrandOptions, setAllBrandOptions] = useState([])
  const [selectedBrandId, setSelectedBrandId] = useState('')
  const [bfStates, setBfStates] = useState(null)
  const [bfCounties, setBfCounties] = useState(null)
  const [bfTowns, setBfTowns] = useState(null)

  const selectedBrandName = allBrandOptions.find((b) => String(b.brand_id) === String(selectedBrandId))?.name || null

  // Centralizes every navigation: resets sort to a sensible default for the
  // new level's columns (the old sortKey often doesn't exist there) and
  // clears filters that don't apply at the destination.
  const goDrill = (target) => {
    setDrillRaw(target)
    setSortKey(selectedBrandId ? 'avg_rating' : DEFAULT_SORT_BY_LEVEL[target.level] || null)
    setSortDir('desc')
    setFamilyFilter('')
    setExpandedBrands(new Set())
  }

  const toggleBrandExpanded = (brand) => {
    setExpandedBrands((prev) => {
      const next = new Set(prev)
      if (next.has(brand)) next.delete(brand)
      else next.add(brand)
      return next
    })
  }

  useEffect(() => {
    api.voiceBrandOptions().then(setAllBrandOptions).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (drill.level === 'county') {
      setCounties(null); setError(null)
      api.voiceCounties(drill.state).then(setCounties).catch((e) => setError(e.message))
    }
    if (drill.level === 'town') {
      setTowns(null); setError(null)
      api.voiceCountyTowns(drill.state, drill.county_fips).then(setTowns).catch((e) => setError(e.message))
    }
    if (drill.level === 'store') {
      setLocations(null); setError(null)
      api.voiceCountyLocations(drill.state, drill.county_fips, drill.city).then(setLocations).catch((e) => setError(e.message))
    }
    if (drill.level === 'brand') {
      setBrands(null); setError(null)
      api.voiceBrands(drill.state).then(setBrands).catch((e) => setError(e.message))
    }
    if (drill.level === 'competitors') {
      setCompetitors(null); setError(null)
      const call = drill.county_fips
        ? api.voiceCompetitorsByCounty(drill.state, drill.county_fips)
        : api.voiceCompetitorsByState(drill.state)
      call.then(setCompetitors).catch((e) => setError(e.message))
    }
  }, [drill])

  useEffect(() => {
    if (!selectedBrandId || drill.level !== 'state') return
    setBfStates(null); setError(null)
    api.voiceBrandFilteredStates(selectedBrandId).then(setBfStates).catch((e) => setError(e.message))
  }, [selectedBrandId, drill.level])

  useEffect(() => {
    if (!selectedBrandId || drill.level !== 'county') return
    setBfCounties(null); setError(null)
    api.voiceBrandFilteredCounties(selectedBrandId, drill.state).then(setBfCounties).catch((e) => setError(e.message))
  }, [selectedBrandId, drill.level, drill.state])

  useEffect(() => {
    if (!selectedBrandId || drill.level !== 'town') return
    setBfTowns(null); setError(null)
    api.voiceBrandFilteredTowns(selectedBrandId, drill.state, drill.county_fips).then(setBfTowns).catch((e) => setError(e.message))
  }, [selectedBrandId, drill.level, drill.state, drill.county_fips])

  const rawStateName = states.find((s) => s.state === drill.state)?.state_name
  const stateNameByCode = useMemo(() => Object.fromEntries(states.map((s) => [s.state, s.state_name])), [states])
  const brandFilterActive = !!selectedBrandId && ['state', 'county', 'town'].includes(drill.level)

  let columns, rows, filename
  if (brandFilterActive) {
    columns = brandFilteredColumns(drill.level, stateNameByCode)
    if (drill.level === 'state') {
      rows = bfStates || []
      filename = `voice-brand${selectedBrandId}-states.csv`
    } else if (drill.level === 'county') {
      rows = bfCounties || []
      filename = `voice-brand${selectedBrandId}-${drill.state}-counties.csv`
    } else {
      rows = bfTowns || []
      filename = `voice-brand${selectedBrandId}-${drill.state}-${drill.county_fips}-towns.csv`
    }
  } else {
    columns = COLUMNS_BY_LEVEL[drill.level]
    if (drill.level === 'state') {
      rows = states.filter((s) => s.has_data).map((r) => ({ ...r, avgReviewsPerStore: r.n_mavis_locations ? r.total_mavis_reviews / r.n_mavis_locations : null }))
      filename = 'voice-states.csv'
    } else if (drill.level === 'county') {
      rows = (counties || []).map((r) => ({ ...r, avgReviewsPerStore: r.n_mavis_locations ? r.total_mavis_reviews / r.n_mavis_locations : null }))
      filename = `voice-${drill.state}-counties.csv`
    } else if (drill.level === 'town') {
      rows = (towns || []).map((r) => ({ ...r, avgReviewsPerStore: r.n_mavis_locations ? r.total_mavis_reviews / r.n_mavis_locations : null }))
      filename = `voice-${drill.state}-${drill.county_fips}-towns.csv`
    } else if (drill.level === 'store') {
      // "Neighborhood average" is the whole town's own weighted-average
      // rating (every location, every brand, before any filter) - a fixed
      // benchmark that shouldn't shift depending on what the user has
      // filtered the table down to.
      const neighborhoodAvg = weightedAvg(locations || [], 'raw_rating', 'review_count')
      const filteredLocations = (locations || [])
        .filter((r) => !selectedBrandName || r.brand === selectedBrandName)
        .filter((r) => !familyFilter || r.family === familyFilter)
      const byBrand = new Map()
      for (const loc of filteredLocations) {
        if (!byBrand.has(loc.brand)) byBrand.set(loc.brand, [])
        byBrand.get(loc.brand).push(loc)
      }
      rows = [...byBrand.entries()].map(([brand, locs]) => {
        const nAbove = neighborhoodAvg === null
          ? null
          : locs.filter((l) => l.raw_rating !== null && l.raw_rating !== undefined && l.raw_rating > neighborhoodAvg).length
        const totalReviews = locs.reduce((sum, l) => sum + (l.review_count || 0), 0)
        return {
          brand, family: locs[0].family, locations: locs, n_locations: locs.length,
          totalReviews, avgReviewsPerStore: totalReviews / locs.length,
          avgRating: weightedAvg(locs, 'raw_rating', 'review_count'),
          avgAdjRating: weightedAvg(locs, 'adj_rating', 'review_count'),
          avgDelta: weightedAvg(locs, 'delta', 'review_count'),
          neighborhoodAvg,
          pctAboveAvg: nAbove === null ? null : nAbove / locs.length,
        }
      })
      filename = `voice-${drill.state}-${drill.county_fips}-${drill.city || 'all'}-stores.csv`
    } else if (drill.level === 'brand') {
      rows = (brands || []).map((r) => ({ ...r, avgReviewsPerStore: r.n_mavis_locations ? r.total_mavis_reviews / r.n_mavis_locations : null }))
      filename = `voice-${drill.state}-brands.csv`
    } else {
      rows = (competitors || []).map((r) => ({ ...r, avgReviewsPerStore: r.n_locations ? r.total_reviews / r.n_locations : null }))
      filename = drill.county_fips
        ? `voice-${drill.state}-${drill.county_fips}-competitors.csv`
        : `voice-${drill.state}-competitors.csv`
    }
  }

  const loading = brandFilterActive
    ? (drill.level === 'state' && bfStates === null) ||
      (drill.level === 'county' && bfCounties === null) ||
      (drill.level === 'town' && bfTowns === null)
    : (
      (drill.level === 'county' && !error && counties === null) ||
      (drill.level === 'town' && !error && towns === null) ||
      (drill.level === 'store' && !error && locations === null) ||
      (drill.level === 'brand' && !error && brands === null) ||
      (drill.level === 'competitors' && !error && competitors === null)
    )

  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const ALL_STATES_CRUMB = { label: 'All states', target: { level: 'state' } }
  const STATE_CRUMB = () => ({ label: rawStateName || drill.state, target: { level: 'county', state: drill.state } })
  let crumbs
  if (drill.level === 'state') {
    crumbs = [{ label: 'All states', target: null }]
  } else if (drill.level === 'county') {
    crumbs = [ALL_STATES_CRUMB, { label: rawStateName || drill.state, target: null }]
  } else if (drill.level === 'town') {
    crumbs = [ALL_STATES_CRUMB, STATE_CRUMB(), { label: `${drill.county_name} County`, target: null }]
  } else if (drill.level === 'store') {
    crumbs = [
      ALL_STATES_CRUMB, STATE_CRUMB(),
      { label: `${drill.county_name} County`, target: { level: 'town', state: drill.state, county_fips: drill.county_fips, county_name: drill.county_name } },
      { label: drill.city || 'All towns', target: null },
    ]
  } else if (drill.level === 'brand') {
    crumbs = [ALL_STATES_CRUMB, { label: `${rawStateName || drill.state} — by brand`, target: null }]
  } else {
    crumbs = drill.county_fips
      ? [ALL_STATES_CRUMB, STATE_CRUMB(), { label: `${drill.county_name} County — by competitor`, target: null }]
      : [ALL_STATES_CRUMB, { label: `${rawStateName || drill.state} — by competitor`, target: null }]
  }

  const showFamilyFilter = drill.level === 'store'

  const mavisOptions = allBrandOptions.filter((b) => b.family === 'mavis')
  const competitorOptions = allBrandOptions.filter((b) => b.family === 'competitor')

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, paddingBottom: 10, borderBottom: `1px solid ${SLATE_200}` }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: MUTED }}>BRAND</span>
        <select
          value={selectedBrandId}
          onChange={(e) => {
            const val = e.target.value
            setSelectedBrandId(val)
            setSortKey(val ? 'avg_rating' : DEFAULT_SORT_BY_LEVEL[drill.level] || null)
            setSortDir('desc')
          }}
          style={{ fontSize: 12, padding: '6px 10px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT, minWidth: 220 }}
        >
          <option value="">All Mavis brands combined</option>
          <optgroup label="Mavis brands">
            {mavisOptions.map((b) => <option key={b.brand_id} value={b.brand_id}>{b.name}</option>)}
          </optgroup>
          <optgroup label="Competitors">
            {competitorOptions.map((b) => <option key={b.brand_id} value={b.brand_id}>{b.name}</option>)}
          </optgroup>
        </select>
        {selectedBrandId && (
          <span style={{ fontSize: 11, color: MUTED }}>
            Showing {selectedBrandName} vs. the area it's in - not the portfolio-vs-competitors view.
          </span>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: MUTED }}>
          {crumbs.map((c, i) => (
            <span key={i}>
              {i > 0 && <span style={{ margin: '0 6px' }}>›</span>}
              {c.target ? (
                <span onClick={() => goDrill(c.target)} style={{ cursor: 'pointer', textDecoration: 'underline', color: TEAL_700 }}>
                  {c.label}
                </span>
              ) : (
                <span style={{ fontWeight: 600, color: INK_TEXT }}>{c.label}</span>
              )}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {showFamilyFilter && (
            <select
              value={familyFilter}
              onChange={(e) => setFamilyFilter(e.target.value)}
              style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }}
            >
              <option value="">Mavis + competitors</option>
              <option value="mavis">Mavis only</option>
              <option value="competitor">Competitors only</option>
            </select>
          )}
          <button onClick={() => downloadCsv(sorted, columns, filename)} style={pillStyle(false)}>Export CSV</button>
        </div>
      </div>

      {error ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>
      ) : loading ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : sorted.length === 0 ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>No rows to show.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: drill.level === 'store' ? 1080 : 820 }}>
            <SortableHead columns={columns} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            {sorted.map((r, i) => {
              const clickable =
                drill.level === 'state' ? !r.suppressed :
                drill.level === 'county' ? true :
                drill.level === 'town' ? true : false
              const key =
                drill.level === 'state' ? r.state :
                drill.level === 'county' ? r.county_fips :
                drill.level === 'town' ? r.city :
                r.brand
              const isDeltaCol = (c) => c.sortKey === 'delta' || c.sortKey === 'avgDelta'
              const expandable = drill.level === 'store' && r.n_locations > 1
              const expanded = expandable && expandedBrands.has(r.brand)
              return (
                <div key={key}>
                  <div
                    onClick={() => {
                      if (!clickable) return
                      if (drill.level === 'state') goDrill({ level: 'county', state: r.state })
                      else if (drill.level === 'county') goDrill({ level: 'town', state: drill.state, county_fips: r.county_fips, county_name: r.county_name })
                      else if (drill.level === 'town') goDrill({ level: 'store', state: drill.state, county_fips: drill.county_fips, county_name: drill.county_name, city: r.city })
                    }}
                    style={{
                      display: 'grid', gridTemplateColumns: columns.map((c) => c.width || '1fr').join(' '), gap: 12,
                      padding: '9px 0', cursor: clickable ? 'pointer' : 'default', fontSize: 12,
                    }}
                  >
                    {columns.map((c, ci) => (
                      <div
                        key={c.label || ci}
                        onClick={
                          c.action ? (e) => {
                            e.stopPropagation()
                            if (drill.level === 'state') goDrill({ level: c.action, state: r.state })
                            else if (drill.level === 'county') goDrill({ level: c.action, state: drill.state, county_fips: r.county_fips, county_name: r.county_name })
                          } : expandable && ci === 0 ? (e) => { e.stopPropagation(); toggleBrandExpanded(r.brand) } : undefined
                        }
                        style={{
                          color: c.action ? TEAL_700 : isDeltaCol(c) ? deltaColor(r.delta ?? r.avgDelta) : INK_TEXT,
                          fontFamily: isDeltaCol(c) || c.label.includes('RATING') ? MONO : undefined,
                          fontWeight: isDeltaCol(c) ? 600 : 400,
                          cursor: c.action || (expandable && ci === 0) ? 'pointer' : undefined,
                          textDecoration: c.action ? 'underline' : undefined,
                          userSelect: expandable && ci === 0 ? 'none' : undefined,
                        }}
                      >
                        {expandable && ci === 0 && (
                          <span style={{ display: 'inline-block', width: 14, fontWeight: 700, color: DEEP_TEAL }}>
                            {expanded ? '−' : '+'}
                          </span>
                        )}
                        {c.value(r)}
                      </div>
                    ))}
                  </div>
                  <RowDivider />
                  {expanded && r.locations.map((loc) => (
                    <div key={loc.location_id}>
                      <div
                        style={{
                          display: 'grid', gridTemplateColumns: STORE_CHILD_COLUMNS.map((c) => c.width || '1fr').join(' '), gap: 12,
                          padding: '7px 0', fontSize: 11.5, background: '#FAFBFC',
                        }}
                      >
                        {STORE_CHILD_COLUMNS.map((c, ci) => (
                          <div
                            key={ci}
                            style={{
                              paddingLeft: ci === 0 ? 22 : 0, color: MUTED,
                              fontFamily: ci === 2 || ci === 3 || ci === 4 ? MONO : undefined,
                            }}
                          >
                            {c.value(loc)}
                          </div>
                        ))}
                      </div>
                      <RowDivider />
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
