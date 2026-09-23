import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { MUTED, INK_TEXT, SLATE_200, SLATE_600, MONO, divergingColor, fmtNum } from '../styles'

function fmtRating(v) {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

function fmtGap(v) {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
}

const ROW_LABEL_WIDTH = 200
const COL_WIDTH = 108
const GAP_MAX_ABS = 0.6

function cellDetail(cell, granularity) {
  if (granularity === 'none') return `${fmtNum(cell.n_mavis_locations)} vs ${fmtNum(cell.n_comp_locations)} stores`
  return `${cell.n_shared} shared ${granularity === 'state' ? 'states' : 'towns'}`
}

function Cell({ cell, granularity }) {
  if (!cell || cell.gap === null || cell.gap === undefined) {
    return (
      <div style={{ padding: '9px 6px', textAlign: 'center', color: '#B9C2CB', fontSize: 11, fontFamily: MONO }}>
        no overlap
      </div>
    )
  }
  const thin = granularity !== 'none' && cell.n_shared < 3
  const bg = divergingColor(cell.gap, GAP_MAX_ABS)
  // A saturated fill needs white text; a light tint needs the app's normal
  // dark/muted pair - same threshold divergingColor's own clamp uses, so
  // the switch lands right where the background actually gets dark enough
  // to matter (near/at the +/-0.6 clamp on the strongest cells).
  const strong = Math.abs(cell.gap) / GAP_MAX_ABS > 0.55
  const mainColor = strong ? '#FFFFFF' : thin ? MUTED : INK_TEXT
  const detailColor = strong ? 'rgba(255,255,255,.82)' : MUTED
  return (
    <div
      title={`${fmtRating(cell.mavis_avg)} vs ${fmtRating(cell.comp_avg)}`}
      style={{ padding: '9px 6px', textAlign: 'center', borderRadius: 3, background: bg }}
    >
      <div style={{ fontFamily: MONO, fontSize: 14, fontWeight: 600, color: mainColor }}>{fmtGap(cell.gap)}</div>
      <div style={{ fontFamily: MONO, fontSize: 10, color: detailColor }}>
        {cellDetail(cell, granularity)}{thin ? ' · thin' : ''}
      </div>
    </div>
  )
}

export default function VoiceHeadToHead({ states, source = 'google_maps' }) {
  const [stateFilter, setStateFilter] = useState('')
  const [cityFilter, setCityFilter] = useState('')
  const [towns, setTowns] = useState([])
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Guards against an in-flight nationwide fetch (slower - it scans every
    // location) resolving after a subsequent filtered one and clobbering it
    // with stale, wrongly-scoped data.
    let cancelled = false
    setData(null); setError(null)
    api.voiceHeadToHead(stateFilter || null, cityFilter || null, source)
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

  const columns = data?.columns || []
  const rows = data?.rows || []
  const granularity = data?.granularity || 'state'

  const scopeLabel = stateFilter
    ? `${cityFilter || 'all towns'}, ${stateOptions.find((s) => s.state === stateFilter)?.state_name || stateFilter}`
    : 'nationwide'
  const shareLine = granularity === 'none'
    ? `both measured inside ${cityFilter}`
    : `both measured only inside shared ${granularity === 'state' ? 'states' : 'towns'}`
  const headerAvgLabel = stateFilter ? `avg in this scope` : 'nationwide avg'

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: MUTED }}>
          Ranked {scopeLabel}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
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
        </div>
      </div>

      {error ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>
      ) : data === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : rows.length === 0 ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>No data to show in this scope.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: ROW_LABEL_WIDTH + columns.length * COL_WIDTH }}>
            <div style={{ display: 'grid', gridTemplateColumns: `${ROW_LABEL_WIDTH}px repeat(${columns.length}, ${COL_WIDTH}px)`, gap: 3 }}>
              <div />
              {columns.map((c) => (
                <div key={c.brand_id} style={{ paddingBottom: 8, alignSelf: 'end' }}>
                  <div style={{ fontSize: 10.5, fontWeight: 600, lineHeight: 1.25, color: SLATE_600, textAlign: 'center' }}>{c.name}</div>
                  <div style={{ fontFamily: MONO, fontSize: 10, color: MUTED, textAlign: 'center', paddingTop: 2 }}>{fmtRating(c.avg)}</div>
                </div>
              ))}
            </div>
            <hr style={{ margin: '2px 0 6px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
            {rows.map((r) => (
              <div key={r.brand_id} style={{ display: 'grid', gridTemplateColumns: `${ROW_LABEL_WIDTH}px repeat(${columns.length}, ${COL_WIDTH}px)`, gap: 3, marginBottom: 3 }}>
                <div style={{ paddingRight: 14, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{r.name}</div>
                  <div style={{ fontFamily: MONO, fontSize: 10.5, color: MUTED }}>{scopeLabel === 'nationwide' ? 'all-market' : 'in scope'} {fmtRating(r.avg)}</div>
                </div>
                {columns.map((c) => (
                  <Cell key={c.brand_id} cell={r.cells[String(c.brand_id)]} granularity={granularity} />
                ))}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 8 }}>
            Cell = Mavis banner avg − competitor avg, {shareLine}. The header avg is each competitor's own {headerAvgLabel}, shown for context, not the shared-area one. {fmtNum(rows.length)} Mavis banners × {fmtNum(columns.length)} competitors.
          </div>
        </div>
      )}
    </div>
  )
}
