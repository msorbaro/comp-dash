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
  for (const r of rows) lines.push(columns.map((c) => esc(c.raw ? r[c.raw] : c.value(r))).join(','))
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
      <div style={{ display: 'grid', gridTemplateColumns: columns.map((c) => c.width || '1fr').join(' '), gap: 14 }}>
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

const STATE_COLUMNS = [
  { label: 'STATE', width: '2fr', sortKey: 'state_name', value: (r) => r.state_name },
  { label: 'MAVIS RATING', width: '1.2fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '1fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'MAVIS REVIEWS', width: '1.1fr', sortKey: 'total_mavis_reviews', value: (r) => fmtNum(r.total_mavis_reviews) },
  { label: 'STATUS', width: '1.2fr', sortKey: null, value: (r) => (!r.has_data ? 'No pilot data' : r.suppressed ? 'Insufficient data' : 'OK') },
]

const TOWN_COLUMNS = [
  { label: 'TOWN', width: '2fr', sortKey: 'city', value: (r) => r.city },
  { label: 'MAVIS RATING', width: '1.2fr', sortKey: 'mavis_rating', value: (r) => fmtRating(r.mavis_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_rating', value: (r) => fmtRating(r.comp_rating) },
  { label: 'DELTA', width: '1fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'MAVIS REVIEWS', width: '1.1fr', sortKey: 'total_mavis_reviews', value: (r) => fmtNum(r.total_mavis_reviews) },
  { label: 'STATUS', width: '1.2fr', sortKey: null, value: (r) => (r.suppressed ? 'Insufficient data' : 'OK') },
]

const STORE_COLUMNS = [
  { label: 'STORE', width: '2fr', sortKey: 'name', value: (r) => r.name },
  { label: 'BRAND', width: '1.4fr', sortKey: 'brand', value: (r) => r.brand },
  { label: 'MAVIS ADJ. RATING', width: '1.1fr', sortKey: 'mavis_adj_rating', value: (r) => fmtRating(r.mavis_adj_rating) },
  { label: 'COMPETITOR BENCHMARK', width: '1.2fr', sortKey: 'comp_benchmark_rating', value: (r) => fmtRating(r.comp_benchmark_rating) },
  { label: 'DELTA', width: '0.9fr', sortKey: 'delta', value: (r) => fmtDelta(r.delta) },
  { label: 'MAVIS REVIEWS', width: '1fr', sortKey: 'mavis_review_count', value: (r) => fmtNum(r.mavis_review_count) },
  { label: 'COMP. REVIEWS', width: '1fr', sortKey: 'comp_review_count', value: (r) => fmtNum(r.comp_review_count) },
  { label: 'COMPARABILITY', width: '1.2fr', sortKey: null, value: (r) => (r.low_comparability ? `Low (${r.n_competitors_in_ring} in ring)` : `OK (${r.n_competitors_in_ring} in ring)`) },
]

export default function VoiceTable({ states, initialState, onDrillChange }) {
  const [drill, setDrill] = useState(() => (initialState ? { level: 'town', state: initialState } : { level: 'state' }))
  const [towns, setTowns] = useState(null)
  const [stores, setStores] = useState(null)
  const [error, setError] = useState(null)
  const [sortKey, setSortKey] = useState('delta')
  const [sortDir, setSortDir] = useState('desc')
  const [brandFilter, setBrandFilter] = useState('')

  useEffect(() => {
    if (initialState) setDrill({ level: 'town', state: initialState })
  }, [initialState])

  useEffect(() => {
    onDrillChange?.(drill)
  }, [drill, onDrillChange])

  useEffect(() => {
    if (drill.level === 'town') {
      setTowns(null); setError(null)
      api.voiceTowns(drill.state).then(setTowns).catch((e) => setError(e.message))
    }
    if (drill.level === 'store') {
      setStores(null); setError(null)
      api.voiceStores(drill.state, drill.city).then(setStores).catch((e) => setError(e.message))
    }
  }, [drill.level, drill.state, drill.city])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const rawStateName = states.find((s) => s.state === drill.state)?.state_name

  let columns, rows, filename, breadcrumb

  if (drill.level === 'state') {
    columns = STATE_COLUMNS
    rows = states.filter((s) => s.has_data)
    filename = 'voice-states.csv'
    breadcrumb = ['All states']
  } else if (drill.level === 'town') {
    columns = TOWN_COLUMNS
    rows = towns || []
    filename = `voice-${drill.state}-towns.csv`
    breadcrumb = ['All states', rawStateName || drill.state]
  } else {
    columns = STORE_COLUMNS
    rows = (stores || []).filter((r) => !brandFilter || r.brand === brandFilter)
    filename = `voice-${drill.state}${drill.city ? `-${drill.city}` : ''}-stores.csv`
    breadcrumb = ['All states', rawStateName || drill.state, drill.city || 'All towns']
  }

  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir])
  const brandOptions = useMemo(() => {
    if (drill.level !== 'store' || !stores) return []
    return [...new Set(stores.map((r) => r.brand))].sort()
  }, [drill.level, stores])

  const loading = (drill.level === 'town' && !towns && !error) || (drill.level === 'store' && !stores && !error)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: MUTED }}>
          {breadcrumb.map((b, i) => (
            <span key={i}>
              {i > 0 && <span style={{ margin: '0 6px' }}>›</span>}
              {i < breadcrumb.length - 1 ? (
                <span
                  onClick={() => {
                    if (i === 0) setDrill({ level: 'state' })
                    else if (i === 1) setDrill({ level: 'town', state: drill.state })
                  }}
                  style={{ cursor: 'pointer', textDecoration: 'underline', color: TEAL_700 }}
                >
                  {b}
                </span>
              ) : (
                <span style={{ fontWeight: 600, color: INK_TEXT }}>{b}</span>
              )}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
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
          <div style={{ minWidth: 760 }}>
            <SortableHead columns={columns} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            {sorted.map((r, i) => {
              const clickable = drill.level === 'state' ? !r.suppressed : drill.level === 'town' ? !r.suppressed : false
              const key = drill.level === 'state' ? r.state : drill.level === 'town' ? r.city : r.name + i
              return (
                <div key={key}>
                  <div
                    onClick={() => {
                      if (drill.level === 'state' && clickable) setDrill({ level: 'town', state: r.state })
                      else if (drill.level === 'town' && clickable) setDrill({ level: 'store', state: drill.state, city: r.city })
                    }}
                    style={{
                      display: 'grid', gridTemplateColumns: columns.map((c) => c.width || '1fr').join(' '), gap: 14,
                      padding: '9px 0', cursor: clickable ? 'pointer' : 'default', fontSize: 12,
                    }}
                  >
                    {columns.map((c) => (
                      <div
                        key={c.label}
                        style={{
                          color: c.sortKey === 'delta' ? deltaColor(r.delta) : INK_TEXT,
                          fontFamily: c.sortKey === 'delta' || c.label.includes('RATING') ? MONO : undefined,
                          fontWeight: c.sortKey === 'delta' ? 600 : 400,
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
