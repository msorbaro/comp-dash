import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import {
  MUTED, INK_TEXT, SLATE_200, SLATE_600, DEEP_TEAL, TEAL_700, TEAL_WASH, MONO,
  RATING_MIX_COLORS, RATING_MIX_LABELS, deltaBarStyle, fmtNum,
} from '../styles'

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

function fmtRating(v) {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

function fmtDelta(v) {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
}

function downloadCsv(rows, categoryAvg, filename) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = ['brand,mavis,avg,vs_category_avg,stores,reviews']
  for (const r of rows) {
    lines.push([r.name, r.mavis ? 'yes' : 'no', r.avg, r.avg - categoryAvg, r.locs, r.reviews].map(esc).join(','))
  }
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

const COLUMN_WIDTHS = ['34px', '2fr', '80px', '1.4fr', '1.1fr', '80px', '90px']

function Head({ sortKey, sortDir, onSort }) {
  const cols = [
    { label: '#', key: null },
    { label: 'BRAND', key: 'name' },
    { label: 'AVG', key: 'avg' },
    { label: 'VS CATEGORY AVG', key: 'delta' },
    { label: 'RATING MIX', key: null },
    { label: 'STORES', key: 'locs' },
    { label: 'REVIEWS', key: 'reviews' },
  ]
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: COLUMN_WIDTHS.join(' '), gap: 12 }}>
        {cols.map((c) => (
          <div
            key={c.label}
            onClick={() => c.key && onSort(c.key)}
            style={{ fontSize: 9.5, letterSpacing: '.1em', color: sortKey === c.key ? DEEP_TEAL : MUTED, fontWeight: 600, cursor: c.key ? 'pointer' : 'default', userSelect: 'none' }}
          >
            {c.label}{sortKey === c.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
          </div>
        ))}
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
    </>
  )
}

function GapBar({ gap }) {
  const s = deltaBarStyle(gap, { scale: 1, center: 50 })
  return (
    <div style={{ position: 'relative', height: 16 }}>
      <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: SLATE_200 }} />
      <div style={{ position: 'absolute', top: 3, height: 10, borderRadius: 1, left: s.barLeft, width: s.barW, background: s.barColor }} />
      <div style={{ position: 'absolute', top: 0, lineHeight: '16px', fontFamily: MONO, fontSize: 11, fontWeight: 500, color: s.barColor, left: s.labelLeft, transform: s.labelTx, padding: s.labelPad, whiteSpace: 'nowrap' }}>
        {fmtDelta(gap)}
      </div>
    </div>
  )
}

function MixBar({ dist }) {
  const total = dist.reduce((a, b) => a + b, 0)
  const title = RATING_MIX_LABELS.map((l, i) => `${l}: ${dist[i]}`).join(' · ')
  return (
    <div style={{ display: 'flex', height: 10, borderRadius: 1, overflow: 'hidden' }} title={title}>
      {total > 0 && dist.map((n, i) => n > 0 && (
        <div key={i} style={{ width: `${(n / total) * 100}%`, background: RATING_MIX_COLORS[i] }} />
      ))}
    </div>
  )
}

export default function VoiceRollup({ states, source = 'google_maps' }) {
  const [stateFilter, setStateFilter] = useState('')
  const [cityFilter, setCityFilter] = useState('')
  const [towns, setTowns] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [sortKey, setSortKey] = useState('avg')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    // Guards against an in-flight nationwide fetch (slower - it scans every
    // location) resolving after a subsequent filtered one and clobbering it
    // with stale, wrongly-scoped data.
    let cancelled = false
    setData(null); setError(null)
    api.voiceRollup(stateFilter || null, cityFilter || null, source)
      .then((d) => { if (!cancelled) setData(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [stateFilter, cityFilter, source])

  // A town choice only makes sense once a state narrows which "Springfield"
  // is meant, so the town select is disabled (and reset) until a state is
  // picked, and re-fetched whenever the state changes.
  useEffect(() => {
    let cancelled = false
    setCityFilter('')
    if (!stateFilter) { setTowns([]); return }
    api.voiceStateTowns(stateFilter, source).then((t) => { if (!cancelled) setTowns(t) }).catch(() => { if (!cancelled) setTowns([]) })
    return () => { cancelled = true }
  }, [stateFilter, source])

  const stateOptions = useMemo(
    () => (states || []).filter((s) => s.has_data).sort((a, b) => a.state_name.localeCompare(b.state_name)),
    [states]
  )

  const rows = data?.brands || []
  const categoryAvg = data?.category_avg ?? null

  const sorted = useMemo(() => {
    const withDelta = rows.map((r) => ({ ...r, delta: categoryAvg === null || r.avg === null ? null : r.avg - categoryAvg }))
    return [...withDelta].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      if (av === null || av === undefined) return 1
      if (bv === null || bv === undefined) return -1
      if (av === bv) return 0
      const cmp = av > bv ? 1 : -1
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, categoryAvg, sortKey, sortDir])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const scopeLabel = stateFilter
    ? `${cityFilter || 'all towns'}, ${stateOptions.find((s) => s.state === stateFilter)?.state_name || stateFilter}`
    : 'nationwide'
  const filename = stateFilter
    ? `voice-rollup-${stateFilter}${cityFilter ? `-${cityFilter}` : ''}.csv`
    : 'voice-rollup-nationwide.csv'

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: MUTED }}>
          Ranked {scopeLabel}{categoryAvg !== null ? ` · category avg ${fmtRating(categoryAvg)}` : ''}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }}
          >
            <option value="">All states</option>
            {stateOptions.map((s) => <option key={s.state} value={s.state}>{s.state_name}</option>)}
          </select>
          <select
            value={cityFilter}
            onChange={(e) => setCityFilter(e.target.value)}
            disabled={!stateFilter}
            style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: stateFilter ? INK_TEXT : MUTED }}
          >
            <option value="">All towns</option>
            {towns.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={() => downloadCsv(sorted, categoryAvg, filename)} style={pillStyle(false)}>Export CSV</button>
        </div>
      </div>

      {error ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>
      ) : data === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : sorted.length === 0 ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>No rated locations in this scope.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: 820 }}>
            <Head sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            {sorted.map((r, i) => (
              <div key={r.brand_id}>
                <div style={{
                  display: 'grid', gridTemplateColumns: COLUMN_WIDTHS.join(' '), gap: 12,
                  padding: '9px 0', fontSize: 12, background: r.mavis ? TEAL_WASH : 'transparent',
                }}>
                  <div style={{ fontFamily: MONO, color: MUTED }}>{i + 1}</div>
                  <div style={{ fontWeight: r.mavis ? 600 : 400 }}>
                    {r.name}
                    {r.mavis && (
                      <span style={{ color: TEAL_700, fontSize: 10, fontFamily: MONO, fontWeight: 600, paddingLeft: 8, letterSpacing: '.05em' }}>MAVIS</span>
                    )}
                  </div>
                  <div style={{ fontFamily: MONO, fontSize: 14, fontWeight: 600 }}>{fmtRating(r.avg)}</div>
                  <div><GapBar gap={r.delta} /></div>
                  <div><MixBar dist={r.dist} /></div>
                  <div style={{ fontFamily: MONO, color: MUTED }}>{fmtNum(r.locs)}</div>
                  <div style={{ fontFamily: MONO, color: MUTED }}>{fmtNum(r.reviews)}</div>
                </div>
                <RowDivider />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 4, flexWrap: 'wrap' }}>
            <span>Rating mix, left→right:</span>
            {RATING_MIX_LABELS.map((l, i) => (
              <span key={l} style={{ color: RATING_MIX_COLORS[i] }}>■ {l}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
