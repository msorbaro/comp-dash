import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtNum, STAGES, ATTRIBUTE_COLORS, ATTRIBUTE_ORDER, MUTED, INK_TEXT, SLATE_600, SLATE_200, DEEP_TEAL, TRACK } from '../styles'

const BAR_HEIGHT = 170
const DAY_OPTIONS = [30, 90, 180]

function median(nums) {
  if (!nums.length) return 0
  const sorted = [...nums].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
        background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
        border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
      }}
    >
      {children}
    </button>
  )
}

// One bar per company, stacked and colored by either funnel stage or real
// classified message attribute - "count" stacks to each company's actual
// volume (so cadence differences are visible in bar height); "pct" stacks
// every bar to a shared 100% (so composition is comparable regardless of
// how often a company posts at all).
function VolumeByCompanyChart({ rows, mode, view }) {
  const order = mode === 'stage' ? STAGES.map((s) => s.name) : ATTRIBUTE_ORDER
  const colorFor = (key) => (mode === 'stage' ? STAGES.find((s) => s.name === key)?.color : ATTRIBUTE_COLORS[key])
  const byKey = (r) => (mode === 'stage' ? r.by_stage : r.by_attribute)
  const maxTotal = Math.max(...rows.map((r) => r.total), 1)
  const presentKeys = order.filter((k) => rows.some((r) => (byKey(r)[k] || 0) > 0))

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 14, fontSize: 10, color: MUTED }}>
        {presentKeys.map((k) => (
          <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: colorFor(k), display: 'inline-block', flex: 'none' }} />
            {k}
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, overflowX: 'auto', paddingBottom: 2 }}>
        {rows.map((r) => {
          const keyed = byKey(r)
          const classifiedTotal = order.reduce((s, k) => s + (keyed[k] || 0), 0)
          const segments = order.map((k) => ({ key: k, count: keyed[k] || 0 })).filter((s) => s.count > 0)
          return (
            <div key={r.company} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 78, flex: 'none' }}>
              <div style={{ display: 'flex', flexDirection: 'column-reverse', width: 38, height: BAR_HEIGHT, borderRadius: 4, overflow: 'hidden', background: TRACK }}>
                {segments.map((s) => {
                  const heightPx = view === 'pct'
                    ? (classifiedTotal ? (s.count / classifiedTotal) * BAR_HEIGHT : 0)
                    : (maxTotal ? (s.count / maxTotal) * BAR_HEIGHT : 0)
                  const pct = classifiedTotal ? Math.round((s.count / classifiedTotal) * 100) : 0
                  return (
                    <div
                      key={s.key}
                      title={`${r.company} — ${s.key}: ${s.count} (${pct}% of classified output)`}
                      style={{ height: `${heightPx}px`, background: colorFor(s.key), borderTop: '2px solid #FFFFFF' }}
                    />
                  )
                })}
              </div>
              <div style={{ fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace', marginTop: 6 }}>{fmtNum(r.total)}</div>
              <div style={{ fontSize: 9.5, color: INK_TEXT, textAlign: 'center', marginTop: 3, lineHeight: 1.25, overflowWrap: 'break-word' }}>{r.company}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// A different cut of the same data: cadence (how often) against See-share
// (what for) in one view, so "posts a lot but leans Do" and "posts rarely
// but has a decent See mix" are both visible as distinct quadrants rather
// than two separate numbers you have to hold in your head at once.
function CadenceScatter({ rows, accent }) {
  const W = 640, H = 240, PAD_L = 34, PAD_R = 16, PAD_T = 14, PAD_B = 26
  const plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B

  const points = rows.map((r) => {
    const classified = STAGES.reduce((s, st) => s + (r.by_stage[st.name] || 0), 0)
    const seePct = classified ? Math.round(((r.by_stage.See || 0) / classified) * 100) : 0
    return { company: r.company, total: r.total, seePct }
  })
  const maxX = Math.max(...points.map((p) => p.total), 1)
  const x = (v) => PAD_L + (v / maxX) * plotW
  const y = (v) => PAD_T + plotH - (v / 100) * plotH
  const medianX = median(points.map((p) => p.total))
  const medianY = median(points.map((p) => p.seePct))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block', maxWidth: 640 }}>
      <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={H - PAD_B} stroke={SLATE_200} strokeWidth={1} />
      <line x1={PAD_L} y1={H - PAD_B} x2={W - PAD_R} y2={H - PAD_B} stroke={SLATE_200} strokeWidth={1} />
      <line x1={x(medianX)} y1={PAD_T} x2={x(medianX)} y2={H - PAD_B} stroke={SLATE_200} strokeWidth={1} strokeDasharray="3,3" />
      <line x1={PAD_L} y1={y(medianY)} x2={W - PAD_R} y2={y(medianY)} stroke={SLATE_200} strokeWidth={1} strokeDasharray="3,3" />
      <text x={PAD_L} y={H - 8} fontSize="9" fill={MUTED}>0 posts</text>
      <text x={W - PAD_R} y={H - 8} fontSize="9" fill={MUTED} textAnchor="end">{fmtNum(maxX)} posts</text>
      <text x={4} y={PAD_T + 8} fontSize="9" fill={MUTED}>100% See</text>
      <text x={4} y={H - PAD_B} fontSize="9" fill={MUTED}>0% See</text>
      {points.map((p) => (
        <g key={p.company}>
          <circle cx={x(p.total)} cy={y(p.seePct)} r={5} fill={accent} fillOpacity={0.88} stroke="#FFFFFF" strokeWidth={1.5}>
            <title>{`${p.company}: ${p.total} posts in the period, ${p.seePct}% of classified output is See-stage`}</title>
          </circle>
          <text x={x(p.total) + 8} y={y(p.seePct) + 3} fontSize="9.5" fill={INK_TEXT}>{p.company}</text>
        </g>
      ))}
    </svg>
  )
}

function GroupPanel({ title, rows, mode, view, accent }) {
  if (!rows?.length) return <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>No data for this group yet.</div>
  return (
    <div>
      <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 10 }}>{title}</div>
      <VolumeByCompanyChart rows={rows} mode={mode} view={view} />
      <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, margin: '18px 0 8px' }}>
        CADENCE VS. SEE-SHARE
      </div>
      <CadenceScatter rows={rows} accent={accent} />
    </div>
  )
}

// Self-contained: fetches its own two datasets (Our Brands + Automotive
// Full Service, the two groups asked for) and owns the toggle state, so
// Landscape.jsx just drops this section in.
export default function PostingCadence() {
  const [days, setDays] = useState(90)
  const [mode, setMode] = useState('stage')
  const [view, setView] = useState('count')
  const [ours, setOurs] = useState(null)
  const [theirs, setTheirs] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    setError(null)
    Promise.all([
      api.landscapeVolume('Our Brands', days),
      api.landscapeVolume('Automotive Full Service', days),
    ]).then(([a, b]) => { setOurs(a); setTheirs(b) }).catch((e) => setError(e.message))
  }
  useEffect(load, [days])

  return (
    <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 4 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Posting cadence by company</div>
          <div style={{ fontSize: 11, color: MUTED, maxWidth: 560 }}>
            How often each company posts, and what that output is made of - the Mavis family against Automotive Full
            Service, the closest direct-competitor set.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 5 }}>
            {DAY_OPTIONS.map((d) => (
              <Pill key={d} active={days === d} onClick={() => setDays(d)}>{d}d</Pill>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            <Pill active={mode === 'stage'} onClick={() => setMode('stage')}>By stage</Pill>
            <Pill active={mode === 'attribute'} onClick={() => setMode('attribute')}>By attribute</Pill>
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            <Pill active={view === 'count'} onClick={() => setView('count')}>Volume</Pill>
            <Pill active={view === 'pct'} onClick={() => setView('pct')}>Mix %</Pill>
          </div>
        </div>
      </div>

      {error ? (
        <div style={{ padding: '30px 0', color: MUTED }}>
          Couldn't load this section ({error}).{' '}
          <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
        </div>
      ) : !ours || !theirs ? (
        <div style={{ padding: '30px 0', color: MUTED }}>Loading…</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 28, marginTop: 18 }}>
          <GroupPanel title="Mavis family of brands" rows={ours.rows} mode={mode} view={view} accent={DEEP_TEAL} />
          <GroupPanel title="Automotive Full Service" rows={theirs.rows} mode={mode} view={view} accent={SLATE_600} />
        </div>
      )}
    </div>
  )
}
