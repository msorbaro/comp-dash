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
  { label: 'MAVIS REVIEWS', width: '1fr', sortKey: 'total_mavis_reviews', value: (r) => fmtNum(r.total_mavis_reviews) },
  { label: 'STATUS', width: '1.4fr', sortKey: null, value: (r) => areaStatus(r, { noDataLabel: 'No pilot data' }) },
  { label: 'BY BRAND', width: '0.8fr', sortKey: null, action: 'brand', value: () => 'View ▸' },
  { label: 'BY COMPETITOR', width: '0.9fr', sortKey: null, action: 'competitors', value: () => 'View ▸' },
]

const COUNTY_COLUMNS = [
  { label: 'COUNTY', width: '1.7fr', sortKey: 'county_name', value: (r) => r.county_name },
  { label: 'MAVIS RATING', width: '1fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.1fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '0.8fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'MAVIS REVIEWS', width: '1fr', sortKey: 'total_mavis_reviews', value: (r) => fmtNum(r.total_mavis_reviews) },
  { label: 'STATUS', width: '1.3fr', sortKey: null, value: (r) => areaStatus(r) },
  { label: 'BY COMPETITOR', width: '0.9fr', sortKey: null, action: 'competitors', value: () => 'View ▸' },
]

const TOWN_COLUMNS = [
  { label: 'TOWN', width: '2fr', sortKey: 'city', value: (r) => r.city },
  { label: 'MAVIS RATING', width: '1.1fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '0.9fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'MAVIS REVIEWS', width: '1.1fr', sortKey: 'total_mavis_reviews', value: (r) => fmtNum(r.total_mavis_reviews) },
  { label: 'STATUS', width: '1.6fr', sortKey: null, value: (r) => areaStatus(r) },
]

const BRAND_COLUMNS = [
  { label: 'MAVIS BRAND', width: '2fr', sortKey: 'brand', value: (r) => r.brand },
  { label: 'MAVIS RATING', width: '1.2fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '1fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'MAVIS REVIEWS', width: '1.1fr', sortKey: 'total_mavis_reviews', value: (r) => fmtNum(r.total_mavis_reviews) },
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
  { label: 'REVIEWS', width: '1fr', sortKey: 'total_reviews', value: (r) => fmtNum(r.total_reviews) },
]

// Individual locations, both families - Mavis rows carry a delta/comparability
// vs. nearby competitors; competitor rows don't (same reasoning as above).
const STORE_COLUMNS = [
  { label: 'STORE', width: '1.6fr', sortKey: 'name', value: (r) => r.name },
  { label: 'BRAND', width: '1.3fr', sortKey: 'brand', value: (r) => r.brand },
  { label: 'TYPE', width: '0.8fr', sortKey: 'family', value: (r) => (r.family === 'mavis' ? 'Mavis' : 'Competitor') },
  { label: 'RATING', width: '0.8fr', sortKey: 'raw_rating', value: (r) => fmtRating(r.raw_rating) },
  { label: 'ADJ. RATING', width: '0.9fr', sortKey: 'adj_rating', value: (r) => fmtRating(r.adj_rating) },
  { label: 'DELTA', width: '0.8fr', sortKey: 'delta', value: (r) => (r.family === 'mavis' ? fmtDelta(r.delta) : '—') },
  { label: 'REVIEWS', width: '0.8fr', sortKey: 'review_count', value: (r) => fmtNum(r.review_count) },
  {
    label: 'COMPARABILITY', width: '1.3fr', sortKey: null,
    value: (r) => {
      if (r.family !== 'mavis') return '—'
      if (r.delta === null || r.delta === undefined) return 'No competitors within 15mi'
      return r.low_comparability ? `Low (${r.n_competitors_in_ring} in ring)` : `OK (${r.n_competitors_in_ring} in ring)`
    },
  },
]

const COLUMNS_BY_LEVEL = {
  state: STATE_COLUMNS, county: COUNTY_COLUMNS, town: TOWN_COLUMNS,
  store: STORE_COLUMNS, brand: BRAND_COLUMNS, competitors: COMPETITOR_COLUMNS,
}
const DEFAULT_SORT_BY_LEVEL = {
  state: 'delta', county: 'delta', town: 'delta', store: 'delta',
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
  const [brandFilter, setBrandFilter] = useState('')
  const [familyFilter, setFamilyFilter] = useState('')

  // Centralizes every navigation: resets sort to a sensible default for the
  // new level's columns (the old sortKey often doesn't exist there) and
  // clears filters that don't apply at the destination.
  const goDrill = (target) => {
    setDrillRaw(target)
    setSortKey(DEFAULT_SORT_BY_LEVEL[target.level] || null)
    setSortDir('desc')
    setBrandFilter('')
    setFamilyFilter('')
  }

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

  const rawStateName = states.find((s) => s.state === drill.state)?.state_name

  const columns = COLUMNS_BY_LEVEL[drill.level]
  let rows, filename
  if (drill.level === 'state') {
    rows = states.filter((s) => s.has_data)
    filename = 'voice-states.csv'
  } else if (drill.level === 'county') {
    rows = counties || []
    filename = `voice-${drill.state}-counties.csv`
  } else if (drill.level === 'town') {
    rows = towns || []
    filename = `voice-${drill.state}-${drill.county_fips}-towns.csv`
  } else if (drill.level === 'store') {
    rows = (locations || [])
      .filter((r) => !brandFilter || r.brand === brandFilter)
      .filter((r) => !familyFilter || r.family === familyFilter)
    filename = `voice-${drill.state}-${drill.county_fips}-${drill.city || 'all'}-stores.csv`
  } else if (drill.level === 'brand') {
    rows = brands || []
    filename = `voice-${drill.state}-brands.csv`
  } else {
    rows = competitors || []
    filename = drill.county_fips
      ? `voice-${drill.state}-${drill.county_fips}-competitors.csv`
      : `voice-${drill.state}-competitors.csv`
  }

  const loading = (
    (drill.level === 'county' && !error && counties === null) ||
    (drill.level === 'town' && !error && towns === null) ||
    (drill.level === 'store' && !error && locations === null) ||
    (drill.level === 'brand' && !error && brands === null) ||
    (drill.level === 'competitors' && !error && competitors === null)
  )

  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir])
  const brandOptions = useMemo(() => {
    if (drill.level !== 'store' || !locations) return []
    return [...new Set(locations.map((r) => r.brand))].sort()
  }, [drill.level, locations])

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

  return (
    <div>
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
          {drill.level === 'store' && brandOptions.length > 0 && (
            <select
              value={brandFilter}
              onChange={(e) => setBrandFilter(e.target.value)}
              style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }}
            >
              <option value="">All brands</option>
              {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
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
          <div style={{ minWidth: 820 }}>
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
                drill.level === 'store' ? r.location_id :
                r.brand
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
                    {columns.map((c) => (
                      <div
                        key={c.label}
                        onClick={c.action ? (e) => {
                          e.stopPropagation()
                          if (drill.level === 'state') goDrill({ level: c.action, state: r.state })
                          else if (drill.level === 'county') goDrill({ level: c.action, state: drill.state, county_fips: r.county_fips, county_name: r.county_name })
                        } : undefined}
                        style={{
                          color: c.action ? TEAL_700 : c.sortKey === 'delta' ? deltaColor(r.delta) : INK_TEXT,
                          fontFamily: c.sortKey === 'delta' || c.label.includes('RATING') ? MONO : undefined,
                          fontWeight: c.sortKey === 'delta' ? 600 : 400,
                          cursor: c.action ? 'pointer' : undefined,
                          textDecoration: c.action ? 'underline' : undefined,
                        }}
                      >
                        {c.value(r)}
                      </div>
                    ))}
                  </div>
                  <RowDivider />
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
